"""
EGRM API - WatermelonDB Sync Implementation
------------------------------------------
This module implements the official WatermelonDB sync protocol for synchronizing
data between the mobile app and Frappe backend.

Follows the WatermelonDB sync specification:
- pullChanges: GET endpoint that returns changes since last sync
- pushChanges: POST endpoint that accepts and processes client changes
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, get_timestamp, now_datetime
from frappe.utils.caching import request_cache, site_cache

# Import user filtering functions from lookup.py
from egrm.api.lookup import get_user_accessible_regions, get_user_region_assignments

# Project scoping is shared with the desk/web surface on purpose. Mobile sync
# used to keep a private copy that disagreed about which roles bypass scoping,
# which left supervisors seeing issues on the desk and a blank mobile app.
from egrm.utils.project_access import get_user_accessible_projects

# Configure logging
log = logging.getLogger(__name__)


# Drafts (docstatus=0 GRM Issues) are private to their owner. Same bypass
# roles as egrm/server_scripts/grm_issue_permissions.py — these can still
# pull other users' drafts via sync, everyone else cannot.
_DRAFT_BYPASS_ROLES = frozenset({"System Manager", "GRM Platform Administrator", "GRM Supervise"})


def _user_can_see_others_drafts(user):
	if user == "Administrator":
		return True
	return bool(_DRAFT_BYPASS_ROLES.intersection(frappe.get_roles(user)))


def _strip_foreign_drafts(records, user):
	"""Filter out GRM Issue drafts that don't belong to `user`. Records
	here come straight from frappe.get_all(..., fields=['*']) so each
	dict carries `docstatus` and `owner`."""
	if _user_can_see_others_drafts(user):
		return records
	visible = []
	dropped = 0
	for rec in records:
		if (rec.get("docstatus") or 0) == 0 and rec.get("owner") != user:
			dropped += 1
			continue
		visible.append(rec)
	if dropped:
		log.info(f"[SYNC_BACKEND] Hid {dropped} foreign draft(s) from sync output for {user}")
	return visible


# WatermelonDB sync table mappings
SYNC_TABLES = {
	"grm_issues": "GRM Issue",
	"grm_issue_categories": "GRM Issue Category",
	"grm_issue_types": "GRM Issue Type",
	"grm_issue_statuses": "GRM Issue Status",
	"grm_administrative_regions": "GRM Administrative Region",
	# API-4 contract: the mobile client and AQE API-CONTRACT suite expect
	# the level-type catalog to come down via pull_changes so that the
	# client can render region pickers grouped by level. The DocType has
	# existed since the per-project architecture roll-out; it just wasn't
	# wired into SYNC_TABLES.
	"grm_administrative_level_types": "GRM Administrative Level Type",
	"grm_issue_age_groups": "GRM Issue Age Group",
	"grm_issue_citizen_groups": "GRM Issue Citizen Group",
	"grm_issue_departments": "GRM Issue Department",
	"grm_projects": "GRM Project",
	"users": "User",
	"grm_project_links": "GRM Project Link",
	"grm_issue_logs": "GRM Issue Log",
	"grm_issue_comments": "GRM Issue Comment",
	"grm_issue_attachments": "GRM Issue Attachment",
}

# Reverse mapping for table name lookup
DOCTYPE_TO_TABLE = {v: k for k, v in SYNC_TABLES.items()}

# Reference tables reachable through a GRM Project Link child row. Their
# entitled size is a pure function of the user's project set, which is what
# makes a shared count cache correct across users.
CHILD_LINKED_REFERENCE_TABLES = (
	"grm_issue_categories",
	"grm_issue_types",
	"grm_issue_statuses",
	"grm_issue_departments",
)

# Tables the device reconciles against. GRM Issue and the sync child tables are
# deliberately absent: drafts are stripped per-viewer and attachments are
# filtered by synced parent, so their counts legitimately differ from a plain
# COUNT and would make every device look permanently short.
RECONCILED_SYNC_TABLES = ("grm_projects", *CHILD_LINKED_REFERENCE_TABLES)

# Reference data changes on the order of weeks, so a short TTL keeps the grouped
# count query off the hot path entirely. Being briefly stale only delays a
# repair by one interval, or costs one bounded extra replay.
REFERENCE_COUNT_TTL = 300

# Distinct project combinations to keep counts for, per worker process. Users
# cluster onto a handful of combinations, so a small table covers nearly every
# request; the cap only bounds memory if that assumption ever breaks.
REFERENCE_COUNT_CACHE_SIZE = 2048

# A device that stays short no matter what must not be able to demand a replay
# on every pull. Short enough that a replay lost to a dropped connection is
# retried on its own rather than leaving the device broken for an hour.
FULL_SYNC_ESCALATION_COOLDOWN = 900

# Issues per page. A full replay for a district-wide account is otherwise one
# unbounded response: the server holds every row in memory, the phone parses
# megabytes of JSON on the UI thread, and a dropped connection loses all of it
# and starts over. Paging keeps each request's latency and each WatermelonDB
# transaction bounded, and makes progress durable — an interrupted sync resumes
# from the last acknowledged page instead of from zero.
#
# Chosen against measured latency and payload size, not guessed. Measured on
# 50k issues locally (see docs/sync-performance.md for the full table):
#
#     page size   pages   p50      p95      total replay   bytes/page
#     unpaged         1   3242ms   3242ms       3242ms     102.2 MB
#          5000      11    423ms    559ms       4817ms      10.2 MB
#          2000      26    225ms    244ms       6278ms       4.1 MB
#          1000      51    166ms    185ms       8755ms       2.0 MB
#           500     101    135ms    155ms      13888ms       1.0 MB
#           250     201    119ms    152ms      24640ms       0.5 MB
#
# Every size clears the latency budget comfortably, so the binding constraint
# is the phone, not the server: at ~2.1 KB per record the response is what has
# to be transferred over a rural connection and parsed into WatermelonDB. 1000
# is the largest page that keeps that near 2 MB, and it costs 37% less total
# replay time than 500 to get there. There is a ~100ms floor per pull (the 13
# reference tables and the deleted-record lookups are paid per request, not per
# record), which is why halving the page size does not halve page latency.
#
# Set to 0 to disable pagination entirely.
PULL_PAGE_SIZE = 1000


@request_cache
def _sync_scope(user):
	"""Resolve the user's entitlement scope once per request.

	``get_changes_since`` and the reconciliation both need the project list and
	region assignments. Without this memo an escalating pull resolves both
	twice, which at sync volume is the kind of duplicated work that only shows
	up under load.

	Deliberately request-scoped and not cached longer: a revoked assignment has
	to take effect on the very next pull, not after a TTL.
	"""
	assignments = get_user_region_assignments(user)
	return {
		"user": user,
		"projects": get_user_accessible_projects(user),
		"assignments": assignments,
		"region_ids": list({a.administrative_region for a in assignments if a.administrative_region}),
	}


def _entitlement_widened_since(user, last_sync_time):
	"""True when the user's assignments changed after their last pull.

	A newly granted region or project makes older records visible that were
	created before the watermark and never touched since. Those match neither
	the "created" nor the "updated" window, so an incremental pull can never
	deliver them — the device would stay blind to its own new scope until
	somebody edited each record by hand.

	Reads the single newest assignment row for the user rather than filtering
	on ``modified > x``: with the (user, modified) index this is one seek
	whose cost does not depend on how stale the caller's watermark is. The
	range form degenerated into a near-full scan for exactly the devices this
	feature exists to repair.

	Fires at most once per widening. This is not just rate limiting — it is what
	makes the feature terminate. A widening resets the watermark to the
	beginning, and the replay that follows is paginated, so every page after the
	first arrives as an ordinary incremental pull whose watermark is still older
	than the assignment row. Re-escalating on each of those would rewind the
	cursor to zero and the device would fetch page one forever. Keyed on the
	assignment's own ``modified``, so a genuinely new widening still triggers a
	fresh replay.
	"""
	try:
		latest = frappe.get_all(
			"GRM User Project Assignment",
			filters={"user": user},
			fields=["modified"],
			order_by="modified desc",
			limit=1,
		)
		if not latest:
			return False
		widened_at = get_datetime(latest[0].modified)
		if widened_at <= last_sync_time:
			return False

		state = hashlib.sha1(f"{user}|{widened_at.isoformat()}".encode(), usedforsecurity=False).hexdigest()
		cache_key = f"grm_sync_entitlement_replay:{state}"
		if frappe.cache().get_value(cache_key):
			return False
		frappe.cache().set_value(cache_key, 1, expires_in_sec=FULL_SYNC_ESCALATION_COOLDOWN)
		return True
	except Exception as e:
		frappe.log_error(f"[SYNC_BACKEND] Entitlement check failed for {user}: {e!s}")
		return False


@site_cache(ttl=REFERENCE_COUNT_TTL, maxsize=REFERENCE_COUNT_CACHE_SIZE)
def _linked_reference_counts(projects):
	"""Rows of each project-linked reference table the project set entitles.

	``projects`` must be a sorted tuple: it is the cache key, so two users with
	the same entitlements have to hash to the same entry.

	Keyed on the project set rather than the user because millions of users
	share a handful of project combinations — the query runs once per
	combination per TTL instead of once per pull. ``site_cache`` keeps that in
	the worker process, so a hit is a dict lookup with no Redis round-trip and
	no pickling; the trade-off is one miss per worker, which is what the TTL is
	sized for.

	The ``(parenttype, project, parent)`` index added by
	``add_sync_reconciliation_indexes`` is what makes the miss cheap. Column
	order is not incidental — see that patch for the measurements.
	"""
	parenttypes = [SYNC_TABLES[t] for t in CHILD_LINKED_REFERENCE_TABLES]
	rows = frappe.db.sql(
		"""
		select parenttype, count(distinct parent) as n
		from `tabGRM Project Link`
		where parenttype in %(parenttypes)s and project in %(projects)s
		group by parenttype
		""",
		{"projects": list(projects), "parenttypes": parenttypes},
		as_dict=True,
	)
	by_doctype = {r.parenttype: cint(r.n) for r in rows}
	return {t: by_doctype.get(SYNC_TABLES[t], 0) for t in CHILD_LINKED_REFERENCE_TABLES}


def _entitled_counts(projects):
	"""How many rows of each reconciled table the project set entitles."""
	if not projects:
		return {}

	# GRM Project is filtered by name against this very list, so its entitled
	# count is the length of the list. No query at all.
	counts = {"grm_projects": len(projects)}

	# Copy: the cached dict is shared with every other caller in this process.
	counts.update(_linked_reference_counts(tuple(sorted(projects))))
	return counts


def _resolve_full_sync(user, last_sync_time, local_counts):
	"""Decide whether an incremental pull should be upgraded to a full replay.

	Returns ``(should_escalate, reason)``. The caller has already ruled out an
	explicit ``fullSync=1`` and a first-ever sync.
	"""
	if _entitlement_widened_since(user, last_sync_time):
		return True, "entitlement-changed"

	if not local_counts:
		return False, None

	try:
		entitled = _entitled_counts(_sync_scope(user)["projects"])
	except Exception as e:
		# Never let the safety net break the sync it is meant to protect.
		frappe.log_error(f"[SYNC_BACKEND] Reconciliation counts failed for {user}: {e!s}")
		return False, None

	short = {
		table: (cint(local_counts.get(table, 0)), expected)
		for table, expected in entitled.items()
		if cint(local_counts.get(table, 0)) < expected
	}
	if not short:
		return False, None

	detail = ", ".join(f"{t}={have}/{want}" for t, (have, want) in sorted(short.items()))

	# Keyed by the reported state, not just the user, so a device that made
	# progress is allowed another replay immediately while one stuck in the
	# same state waits out the cooldown. Also keeps a second device from being
	# starved by the first one's escalation.
	state = hashlib.sha1(f"{user}|{detail}".encode(), usedforsecurity=False).hexdigest()
	cache_key = f"grm_sync_escalated:{state}"
	if frappe.cache().get_value(cache_key):
		return False, None
	frappe.cache().set_value(cache_key, 1, expires_in_sec=FULL_SYNC_ESCALATION_COOLDOWN)

	frappe.log(f"🔁 [SYNC_BACKEND] Escalating {user} to full sync; device short on {detail}")
	return True, f"missing-records ({detail})"


@frappe.whitelist()
def pull_changes(lastPulledAt=None, fullSync=None, counts=None):
	"""
	WatermelonDB standard pullChanges endpoint - GET with query parameters

	URL: /api/method/egrm.api.sync.pull_changes?lastPulledAt=<timestamp>
	Method: GET

	``fullSync=1`` ignores ``lastPulledAt`` and returns the whole back
	catalogue the user is entitled to see. A device whose local database is
	empty — a fresh install, cleared app data, a restore — still holds a
	watermark in its sync metadata, so an incremental pull would hand it only
	the last few hours of deltas and leave it with no projects to work in.
	The result is still scoped by ``get_changes_since``, so "everything" only
	ever means everything within the user's own assignments.

	``counts`` is an optional JSON object of the row counts the device
	currently holds per table, e.g. ``{"grm_projects": 0}``. The server
	compares it against what the user is entitled to and upgrades the pull to
	a full replay by itself when the device is short — so a device missing old
	records recovers on its next ordinary sync instead of needing someone to
	tap the manual recovery button. The same upgrade happens automatically
	when the user's assignments changed since their last pull, since records
	that entered their scope that way are older than the watermark and would
	otherwise never be sent.

	Returns:
	{
	    "changes": {
	        "grm_issues": {
	            "created": [raw_record, ...],
	            "updated": [raw_record, ...],
	            "deleted": ["id1", "id2", ...]
	        },
	        "grm_issue_categories": {
	            "created": [...],
	            "updated": [...],
	            "deleted": [...]
	        }
	        // ... other tables
	    },
	    "timestamp": 1234567890123,
	    "fullSync": false,
	    "fullSyncReason": null,
	    "hasMore": false
	}

	``hasMore: true`` means the response was capped at a page boundary and
	``timestamp`` is that boundary rather than the current instant. The client
	applies the page, then syncs again straight away to fetch the next one. This
	keeps a full replay for a large account off a single unbounded request, and
	makes an interrupted replay resume from the last page it acknowledged.
	"""
	# Start timing the entire operation
	start_time = time.time()

	try:
		# Parse timestamp parameter. Read the request lazily off frappe.local:
		# `frappe.request` raises RuntimeError when unbound, which made this
		# endpoint impossible to exercise from `bench console` or a unit test.
		request = getattr(frappe.local, "request", None)
		args = request.args if request is not None else None
		last_pulled_at = args.get("lastPulledAt") if args else lastPulledAt
		full_sync = cint(args.get("fullSync") if args else fullSync)
		raw_counts = args.get("counts") if args else counts

		# What the device says it currently holds, per table. Optional: older
		# clients don't send it and simply lose the reconciliation safety net.
		local_counts = {}
		if raw_counts:
			try:
				parsed_counts = json.loads(raw_counts) if isinstance(raw_counts, str) else raw_counts
				if isinstance(parsed_counts, dict):
					local_counts = parsed_counts
			except (ValueError, TypeError) as e:
				frappe.log(f"⚠️ [SYNC_BACKEND] Ignoring unparsable counts payload: {e!s}")

		full_sync_reason = "requested" if full_sync else None

		# Validate and parse timestamp
		if full_sync:
			# Caller has no usable local data: replay history from the beginning.
			last_sync_time = datetime.min
		elif last_pulled_at:
			try:
				# Handle both string and numeric timestamps
				if isinstance(last_pulled_at, int | float):
					# Convert milliseconds to datetime
					last_sync_time = datetime.fromtimestamp(last_pulled_at / 1000)
				elif isinstance(last_pulled_at, str):
					# Handle string timestamps
					if last_pulled_at.isdigit():
						# String contains numeric timestamp
						last_sync_time = datetime.fromtimestamp(int(last_pulled_at) / 1000)
					else:
						# ISO string timestamp
						last_sync_time = get_datetime(last_pulled_at)
				else:
					raise ValueError(f"Unsupported timestamp format: {type(last_pulled_at)}")
			except Exception as e:
				frappe.log_error(f"❌ [SYNC_BACKEND] Invalid timestamp: {last_pulled_at} - {e!s}")
				frappe.throw(f"Invalid lastPulledAt timestamp: {last_pulled_at} - {e!s}")
		else:
			# First sync - get all data from beginning of time
			last_sync_time = datetime.min
			full_sync_reason = "first-sync"

		# An incremental pull only ever describes the window since the
		# watermark, so it cannot repair a device that is missing older
		# records — whether because a bug dropped them, a write failed, or the
		# user's scope just widened. Detect that here rather than waiting for
		# somebody to phone support and be told to tap "Download all my data
		# again".
		if not full_sync and last_sync_time != datetime.min:
			should_escalate, reason = _resolve_full_sync(frappe.session.user, last_sync_time, local_counts)
			if should_escalate:
				last_sync_time = datetime.min
				full_sync = 1
				full_sync_reason = reason

		# Cap this response at a page boundary. Resolved before the payload is
		# built so every table can be clamped to the same instant.
		scope = _sync_scope(frappe.session.user)
		page_boundary, has_more = _resolve_page_boundary(
			last_sync_time, scope["projects"], list(scope["region_ids"]), frappe.session.user
		)

		# Get all changes since last sync
		changes = get_changes_since(last_sync_time, page_boundary)

		# Generate timestamp with validation
		current_dt = now_datetime()
		# WatermelonDB expects timestamp as milliseconds since epoch (number, not
		# string). It stores whatever we return and sends it back as the next
		# lastPulledAt, so this must be the real instant of this pull.
		#
		# frappe.utils.get_timestamp() is NOT usable here: it runs the value
		# through getdate(), which returns a date, so the time component is
		# discarded and every response claimed the client was synced as of
		# midnight. Clients then re-requested from midnight forever and only
		# ever received records touched today — records created earlier matched
		# neither the "created" nor the "updated" filter and were never sent.
		#
		# datetime.timestamp() on a naive datetime resolves it in the process
		# timezone, which is the same convention datetime.fromtimestamp() uses
		# when parsing lastPulledAt above, so the round-trip stays exact.
		#
		# On a paginated page the watermark is the page boundary, not now:
		# advancing to now would silently skip everything after the boundary.
		# The client sends this value straight back as the next lastPulledAt, so
		# it is also the cursor that resumes the next page.
		current_timestamp = int((page_boundary or current_dt).timestamp() * 1000)

		# Validate timestamp format
		if not isinstance(current_timestamp, int) or current_timestamp <= 0:
			frappe.log_error(
				f"❌ [SYNC_BACKEND] Invalid timestamp generated: {current_timestamp} (type: {type(current_timestamp)})"
			)
			raise ValueError(f"Invalid timestamp generated: {current_timestamp}")

		# Single-line completion summary (instead of ~10 chatty lines)
		total_duration = time.time() - start_time
		total_created = sum(len(t.get("created", [])) for t in changes.values())
		total_updated = sum(len(t.get("updated", [])) for t in changes.values())
		total_deleted = sum(len(t.get("deleted", [])) for t in changes.values())
		frappe.log(
			f"✅ [SYNC_BACKEND] pullChanges done: +{total_created} ~{total_updated} -{total_deleted} in {total_duration:.3f}s"
			+ (f" [full: {full_sync_reason}]" if full_sync else "")
			+ (" [page: more]" if has_more else "")
		)

		return {
			"changes": changes,
			"timestamp": current_timestamp,
			# Tells the client this response is a full replay rather than a
			# delta, and why. WatermelonDB ignores extra keys; the app logs it
			# so an escalation is visible in the request log without guessing.
			"fullSync": bool(full_sync),
			"fullSyncReason": full_sync_reason,
			# More pages remain. The client should sync again immediately rather
			# than waiting for its next interval; `timestamp` above is already
			# the cursor to resume from.
			"hasMore": bool(has_more),
		}

	except Exception as e:
		total_duration = time.time() - start_time
		frappe.log_error(f"❌ [SYNC_BACKEND] pullChanges failed after {total_duration:.3f}s: {e!s}")
		frappe.log_error(f"Pull changes failed: {e!s}")
		frappe.throw(_("Sync failed. Please try again."))


@frappe.whitelist()
def push_changes():
	"""
	WatermelonDB standard pushChanges endpoint

	Method: POST
	Body: {
	    "changes": {...},
	    "lastPulledAt": "timestamp"
	}

	Returns: void (204 No Content) on success, HTTP error on failure
	"""
	start_time = time.time()
	frappe.log("🔄 [SYNC_BACKEND] Starting pushChanges operation")

	try:
		# Parse request data with timing
		parse_start = time.time()
		data = frappe.request.get_json(silent=True) or {}
		changes = data.get("changes", {})
		data.get("lastPulledAt")

		# ------------------------------------------------------------------
		# 🔄  Accept Issue Actions sync: grm_issues (created/updated) and
		#      child tables (grm_issue_logs, grm_issue_comments, grm_issue_attachments created only)
		# ------------------------------------------------------------------
		filtered_changes = {}

		# Handle grm_issues table - accept both created and updated records
		if "grm_issues" in changes:
			issue_created = changes["grm_issues"].get("created", [])
			issue_updated = changes["grm_issues"].get("updated", [])

			# Updating an existing GRM Issue requires `write` permission on the
			# doctype. Under the duty-role permission model only roles that map
			# to write on GRM Issue (e.g. GRM Supervise / Platform Administrator
			# plus duty-roles authorised to update issues) can take this path.
			if issue_updated and not frappe.has_permission("GRM Issue", "write"):
				frappe.throw(
					_("You do not have permission to update issues."),
					frappe.PermissionError,
				)

			if issue_created or issue_updated:
				filtered_changes["grm_issues"] = {
					"created": issue_created,
					"updated": issue_updated,
					"deleted": [],
				}

		# Handle grm_issue_logs table - accept created records only
		if "grm_issue_logs" in changes:
			logs_created = changes["grm_issue_logs"].get("created", [])

			if logs_created:
				filtered_changes["grm_issue_logs"] = {
					"created": logs_created,
					"updated": [],
					"deleted": [],
				}

		# Handle grm_issue_comments table - accept created records only
		if "grm_issue_comments" in changes:
			comments_created = changes["grm_issue_comments"].get("created", [])

			if comments_created:
				filtered_changes["grm_issue_comments"] = {
					"created": comments_created,
					"updated": [],
					"deleted": [],
				}

		# Handle grm_issue_attachments table - accept created records only
		if "grm_issue_attachments" in changes:
			attachments_created = changes["grm_issue_attachments"].get("created", [])

			if attachments_created:
				filtered_changes["grm_issue_attachments"] = {
					"created": attachments_created,
					"updated": [],
					"deleted": [],
				}

		# Replace original changes with filtered subset
		changes = filtered_changes

		if not changes:
			# API-5 / EC-1 / SEC-15 contract: even an empty payload must
			# return an HTTP 200 JSON envelope with `file_urls` so the
			# mobile client (and AQE contract suite) can parse the
			# response uniformly. The empty `file_urls` dict signals
			# "nothing to remap".
			frappe.log("📤 [SYNC_BACKEND] No Issue Actions changes to process – returning empty envelope")
			return {"file_urls": {}}

		parse_duration = time.time() - parse_start
		frappe.log(f"⏱️ [SYNC_BACKEND] Request parsing took: {parse_duration:.3f}s")

		# Log push statistics
		total_created = total_updated = total_deleted = 0
		for table_name, table_changes in changes.items():
			created = len(table_changes.get("created", []))
			updated = len(table_changes.get("updated", []))
			deleted = len(table_changes.get("deleted", []))
			total_created += created
			total_updated += updated
			total_deleted += deleted
			frappe.log(f"📋 [SYNC_BACKEND] Push {table_name}: +{created} ~{updated} -{deleted}")

		frappe.log(
			f"📊 [SYNC_BACKEND] Total push changes: +{total_created} ~{total_updated} -{total_deleted}"
		)

		# Process changes in transaction with timing
		transaction_start = time.time()
		try:
			frappe.log("💾 [SYNC_BACKEND] Starting database transaction...")
			frappe.db.begin()

			# Collect file URLs for uploaded attachments
			file_url_mappings = {}

			for table_name, table_changes in changes.items():
				table_start = time.time()
				if table_name == "grm_issue_attachments":
					# Process attachments and collect file URLs
					file_urls = process_table_changes(table_name, table_changes)
					if file_urls:
						file_url_mappings[table_name] = file_urls
				else:
					process_table_changes(table_name, table_changes)
				table_duration = time.time() - table_start
				frappe.log(f"⏱️ [SYNC_BACKEND] Processing {table_name} took: {table_duration:.3f}s")

			frappe.db.commit()
			transaction_duration = time.time() - transaction_start
			frappe.log(f"✅ [SYNC_BACKEND] Database transaction completed in {transaction_duration:.3f}s")

			# API-5 contract: always return a JSON envelope with
			# `file_urls` so the client can do `body.file_urls`
			# unconditionally. When no attachments were processed this is
			# an empty dict (NOT a 204). The mobile client treats an
			# empty dict identically to "no remap needed".
			frappe.log(f"📤 [SYNC_BACKEND] Returning file URLs: {file_url_mappings}")
			return {"file_urls": file_url_mappings}

		except Exception as e:
			frappe.db.rollback()
			transaction_duration = time.time() - transaction_start
			frappe.log_error(f"❌ [SYNC_BACKEND] Transaction failed after {transaction_duration:.3f}s: {e!s}")
			frappe.log_error(f"Push changes failed: {e!s}")
			frappe.throw(_("Failed to save changes. Please try again."))

		total_duration = time.time() - start_time
		frappe.log(f"✅ [SYNC_BACKEND] pushChanges completed successfully in {total_duration:.3f}s")

	except Exception as e:
		total_duration = time.time() - start_time
		frappe.log_error(f"❌ [SYNC_BACKEND] pushChanges failed after {total_duration:.3f}s: {e!s}")
		frappe.log_error(f"Push changes failed: {e!s}")
		frappe.throw(_("Failed to process push changes request."))


def get_deleted_records_by_doctype(doctypes, since_timestamp, until_timestamp=None):
	"""
	Get deleted records for several doctypes in one query.

	Returns ``{doctype: [deleted names]}`` with an entry for every requested
	doctype. ``until_timestamp`` closes the window at a paginated page boundary
	so a deletion is never reported before the page whose watermark covers it —
	otherwise the client would advance past a deletion it had not been told
	about.

	One query, not one per table. ``Deleted Document`` is append-only and never
	pruned, so it is the one table in the pull that grows without bound; asking
	it 15 questions per pull made it 85% of the latency of a week-behind
	incremental sync (486ms of 572ms) on a site with only 39k tombstones.
	"""
	start_time = time.time()
	results = {doctype: [] for doctype in doctypes}

	try:
		filters = [
			["deleted_doctype", "in", list(doctypes)],
			["creation", ">", since_timestamp],
		]
		if until_timestamp is not None:
			filters.append(["creation", "<=", until_timestamp])

		deleted_docs = frappe.get_all(
			"Deleted Document",
			filters=filters,
			fields=["deleted_doctype", "deleted_name"],
			ignore_permissions=True,  # We need to see all deleted records
		)

		for doc in deleted_docs:
			# A tombstone for a doctype we didn't ask about cannot appear given
			# the filter, but guard anyway rather than raising mid-pull.
			if doc.deleted_doctype in results:
				results[doc.deleted_doctype].append(doc.deleted_name)

		return results

	except Exception as e:
		duration = time.time() - start_time
		frappe.log_error(f"❌ [SYNC_BACKEND] Failed to get deleted records after {duration:.3f}s: {e!s}")
		# Return empty lists on error - don't fail the entire sync
		return results


def _resolve_page_boundary(last_sync_time, user_projects, accessible_region_ids, user):
	"""Pick the upper bound of this page, or ``None`` for "everything left".

	Pagination hangs on one property of Frappe's timestamps: ``modified`` is set
	equal to ``creation`` on insert and only ever moves forward, so
	``modified > watermark`` is exactly the union of this pull's "created" and
	"updated" streams. That makes ``modified`` a single ordering key for both,
	which is what lets one watermark page a response that carries two streams
	per table across fourteen tables.

	Deliver ``watermark < modified <= boundary`` everywhere and the client can
	advance its watermark to ``boundary`` with no record skipped and none sent
	twice — the next page picks up at ``> boundary``.

	The boundary is read off GRM Issue alone. Issues are the only table that
	grows without bound; the reference tables are small enough that clamping
	them to the same boundary drains them within the first page or two. Cost is
	one indexed ``limit 2 offset N-1`` seek.

	Returns ``(boundary, has_more)``. ``(None, False)`` means no cap: the caller
	sends the remainder and advances the watermark to now.
	"""
	if not PULL_PAGE_SIZE:
		return None, False

	filters = get_user_filters_for_doctype("GRM Issue", user_projects, accessible_region_ids, user)
	filters.pop("_child_table_filter", None)

	conditions = [["modified", ">", last_sync_time]]
	for key, value in filters.items():
		if isinstance(value, list) and len(value) > 1:
			conditions.append([key, "in", value])
		elif isinstance(value, list) and len(value) == 1:
			conditions.append([key, "=", value[0]])
		else:
			conditions.append([key, "=", value])

	try:
		# offset N-1 with limit 2: the first row is the Nth record and becomes
		# the boundary; a second row proves there is a page after this one. When
		# fewer than N records remain both are absent and there is no cap.
		tail = frappe.get_all(
			"GRM Issue",
			filters=conditions,
			fields=["modified"],
			order_by="modified asc",
			start=PULL_PAGE_SIZE - 1,
			page_length=2,
		)
	except Exception as e:
		# A failure here must not break the pull; fall back to unpaginated.
		frappe.log_error(f"[SYNC_BACKEND] Page boundary probe failed for {user}: {e!s}")
		return None, False

	if len(tail) < 2:
		return None, False

	# The boundary leaves here as a datetime but reaches the client as integer
	# milliseconds, and `modified` carries microseconds. Truncating would leave
	# the boundary record still matching `modified > watermark` on the next
	# request: at best it is re-sent, at worst every record in the page shares
	# that millisecond and the cursor never moves. Round UP to the next whole
	# millisecond instead — the boundary record falls inside this page, and the
	# next page starts strictly after a value the client can represent exactly.
	raw = get_datetime(tail[0].modified)
	boundary = raw.replace(microsecond=0) + timedelta(milliseconds=-(-raw.microsecond // 1000))

	# Records sharing the boundary millisecond are all included, so a page can
	# exceed PULL_PAGE_SIZE after a bulk import. That is deliberate: excluding
	# them would either skip them or, if they filled the whole page, stall the
	# cursor forever.
	return boundary, True


def get_changes_since(last_sync_time, page_boundary=None):
	"""Get all changes since last sync time with user permissions and region filtering

	``page_boundary`` closes the window at the top, so the response carries only
	``last_sync_time < modified <= page_boundary``. ``None`` means no upper
	bound.
	"""
	function_start = time.time()
	user = frappe.session.user

	# Get user accessible projects and region assignments. Memoised per request
	# so the reconciliation check ahead of this call does not pay for the same
	# two lookups a second time.
	scope = _sync_scope(user)
	user_accessible_projects = scope["projects"]
	user_assignments = scope["assignments"]
	assigned_region_ids = list(scope["region_ids"])

	# Pre-compute the BFS-expanded accessible-region set ONCE for the
	# whole pull. Without this, get_user_filters_for_doctype re-runs the
	# full hierarchy walk for every one of the 14 SYNC_TABLES entries
	# even though only GRM Issue actually consumes it. At ~5k regions
	# per project (PF-21 scale) that was ~50ms wasted per pull.
	from egrm.api.lookup import get_user_accessible_regions as _gar

	_accessible_regions_full = _gar(user_assignments) or []
	accessible_region_ids_full = list(
		{r.get("name") or r.get("id") for r in _accessible_regions_full if (r.get("name") or r.get("id"))}
	)
	if not accessible_region_ids_full:
		accessible_region_ids_full = list(assigned_region_ids)
	# Stash on frappe.local.flags so get_user_filters_for_doctype reuses
	# them. The flag is request-scoped so it auto-clears after the pull.
	frappe.local.flags.aqe_sync_user_projects = user_accessible_projects
	frappe.local.flags.aqe_sync_accessible_regions = accessible_region_ids_full

	changes = {}
	total_records_processed = 0

	# Track issues being synced for child table filtering
	synced_issue_ids = set()

	# Resolve every table's tombstones up front, in one query, rather than
	# once per table inside the loop below.
	deleted_by_doctype = get_deleted_records_by_doctype(
		set(SYNC_TABLES.values()), last_sync_time, page_boundary
	)

	for table_name, doctype in SYNC_TABLES.items():
		table_start = time.time()
		try:
			# Build user-specific filters based on doctype
			user_filters = get_user_filters_for_doctype(
				doctype, user_accessible_projects, assigned_region_ids, user
			)

			# Handle child table filtering separately
			child_table_filter = user_filters.pop("_child_table_filter", None)

			# Combine time filters with user filters.
			#
			# Both streams are additionally clamped by `modified <= boundary` on
			# a paginated page. "created" is bounded on modified rather than
			# creation on purpose: modified is the ordering key the watermark
			# advances along, and for a freshly created record the two are
			# equal, so this is the same window expressed once.
			created_filters = {"creation": [">", last_sync_time]}
			updated_filters = [
				["modified", ">", last_sync_time],
				["creation", "<=", last_sync_time],
			]
			if page_boundary is not None:
				created_filters["modified"] = ["<=", page_boundary]
				updated_filters.append(["modified", "<=", page_boundary])

			# Add user-specific filters (now properly formatted)
			if user_filters:
				# For created filters (dict format), add properly formatted filters
				for key, value in user_filters.items():
					if isinstance(value, list) and len(value) > 1:
						created_filters[key] = ["in", value]
					elif isinstance(value, list) and len(value) == 1:
						created_filters[key] = value[0]
					else:
						created_filters[key] = value

				# For updated filters (list format), add properly formatted filters
				for key, value in user_filters.items():
					if isinstance(value, list) and len(value) > 1:
						updated_filters.append([key, "in", value])
					elif isinstance(value, list) and len(value) == 1:
						updated_filters.append([key, "=", value[0]])
					else:
						updated_filters.append([key, "=", value])

			# Add child table filters if present
			if child_table_filter:
				child_doctype = child_table_filter["child_doctype"]
				field = child_table_filter["field"]
				values = child_table_filter["values"]

				if len(values) > 1:
					# Multiple values - use "in" operator
					child_filter = [child_doctype, field, "in", values]
				else:
					# Single value - use "=" operator
					child_filter = [child_doctype, field, "=", values[0]]

				# Convert created_filters to list format and add child filter.
				# Carry the page boundary across the format switch — dropping it
				# here would let the reference tables run past the window the
				# client is about to acknowledge.
				created_filters_list = [["creation", ">", last_sync_time], child_filter]
				if page_boundary is not None:
					created_filters_list.append(["modified", "<=", page_boundary])
				# Replace dict format with list format for child table queries
				created_filters = created_filters_list
				updated_filters.append(child_filter)

			# Get created records with user filtering
			created_records = frappe.get_all(
				doctype,
				filters=created_filters,
				fields=["*"],
			)

			# Mirror the created-records query and use frappe.get_all so the
			# per-DocPerm permission check is bypassed. The sync layer enforces
			# access via get_user_filters_for_doctype + validate_user_record_access
			# + (for attachments) optimize_attachment_sync's parent.isin filter,
			# so deferring to DocPerm here would silently swallow updates for
			# restricted-by-role child doctypes (e.g. GRM Issue Attachment for
			# Intake-only users).
			updated_records = frappe.get_all(
				doctype,
				filters=updated_filters,
				fields=["*"],
			)

			# Deleted records came from the single batched tombstone query above.
			deleted_ids = deleted_by_doctype.get(doctype, [])

			# Hide other users' drafts from the sync payload. Drafts are
			# private to the creator across desk + REST + sync (matches
			# has_permission / permission_query_conditions in
			# server_scripts/grm_issue_permissions.py).
			if doctype == "GRM Issue":
				created_records = _strip_foreign_drafts(created_records, user)
				updated_records = _strip_foreign_drafts(updated_records, user)

			# Track issue IDs for child table filtering
			if doctype == "GRM Issue":
				for record in created_records + updated_records:
					synced_issue_ids.add(record.get("name"))

			# Convert to WatermelonDB format
			created_raw = remove_duplicates_by_id([frappe_to_watermelon_raw(rec) for rec in created_records])
			updated_raw = remove_duplicates_by_id([frappe_to_watermelon_raw(rec) for rec in updated_records])

			changes[table_name] = {
				"created": created_raw,
				"updated": updated_raw,
				"deleted": deleted_ids,
			}

			table_duration = time.time() - table_start

			# Single-line per-table summary (instead of ~10 chatty lines)
			frappe.log(
				f"✅ [SYNC_BACKEND] {table_name}: +{len(created_records)} ~{len(updated_records)} -{len(deleted_ids)} ({table_duration:.3f}s)"
			)

			total_records_processed += len(created_records) + len(updated_records) + len(deleted_ids)

		except Exception as e:
			table_duration = time.time() - table_start
			frappe.log_error(
				f"❌ [SYNC_BACKEND] Error processing {doctype} after {table_duration:.3f}s: {e!s}"
			)
			frappe.log_error(f"Error getting changes for {doctype}: {e!s}")
			# Continue with other tables even if one fails
			continue

	# Optimize attachment fetching with proper parent filtering
	if "grm_issue_attachments" in changes and synced_issue_ids:
		changes["grm_issue_attachments"] = optimize_attachment_sync(
			changes["grm_issue_attachments"], last_sync_time, page_boundary
		)

	function_duration = time.time() - function_start
	frappe.log(
		f"✅ [SYNC_BACKEND] get_changes_since done: {total_records_processed} records in {function_duration:.3f}s"
	)

	return changes


def remove_duplicates_by_id(objects):
	seen = set()
	unique_objects = []
	for obj in objects:
		if obj["id"] not in seen:
			seen.add(obj["id"])
			unique_objects.append(obj)
	return unique_objects


def get_user_filters_for_doctype(doctype, user_projects, accessible_region_ids, user):
	"""
	Get user-specific filters for a given doctype based on their project assignments

	Args:
	    doctype (str): The Frappe doctype to filter
	    user_projects (list): List of project IDs the user has access to (not used, will get fresh)
	    accessible_region_ids (list): List of region IDs the user has access to (not used, will get fresh)
	    user (str): Current user email

	Returns:
	    dict: Filters to apply for the doctype. Values are either single values or lists (without operator wrapping)
	"""

	# Reuse the request-scoped cache populated by get_changes_since to
	# avoid re-resolving the project list 14 times per pull. Falls back
	# to a fresh resolution for callers outside the sync hot path.
	user_accessible_projects = (
		getattr(frappe.local.flags, "aqe_sync_user_projects", None)
		if hasattr(frappe, "local") and getattr(frappe, "local", None) is not None
		else None
	)
	if user_accessible_projects is None:
		user_accessible_projects = get_user_accessible_projects(user)

	# If user has no project access, they get no data
	if not user_accessible_projects:
		log.warning(f"⚠️ [SYNC_BACKEND] User {user} has no project assignments")
		frappe.throw(_("User has no access to any project"))

	filters = {}

	# Define project field mapping for each doctype
	# For child tables, we need to specify the child doctype in filters
	CHILD_TABLE_DOCTYPES = {
		"GRM Issue Category": "GRM Project Link",
		"GRM Issue Type": "GRM Project Link",
		"GRM Issue Status": "GRM Project Link",
		"GRM Issue Age Group": "GRM Project Link",
		"GRM Issue Citizen Group": "GRM Project Link",
		"GRM Issue Department": "GRM Project Link",
	}

	if doctype == "GRM Issue":
		# Special case: Filter issues by both project AND accessible regions.
		filters["project"] = user_accessible_projects  # Return just the list, not wrapped

		# Reuse the BFS-expanded region set computed once in
		# get_changes_since (cached on frappe.local.flags). Falls back to
		# an in-place BFS for callers outside the sync hot path.
		cached_regions = (
			getattr(frappe.local.flags, "aqe_sync_accessible_regions", None)
			if hasattr(frappe, "local") and getattr(frappe, "local", None) is not None
			else None
		)
		if cached_regions is not None:
			accessible_region_ids_local = list(cached_regions)
		else:
			from egrm.api.lookup import get_user_accessible_regions

			user_assignments = get_user_region_assignments(user)
			accessible = get_user_accessible_regions(user_assignments) or []
			accessible_region_ids_local = list(
				{r.get("name") or r.get("id") for r in accessible if (r.get("name") or r.get("id"))}
			)
			# Fall back to direct assignments when hierarchy expansion fails
			# (defensive: never let an empty accessible-set silently leak all
			# issues — keep the strict filter on direct assignments).
			if not accessible_region_ids_local:
				accessible_region_ids_local = list(
					{a.administrative_region for a in user_assignments if a.administrative_region}
				)

		if accessible_region_ids_local:
			filters["administrative_region"] = accessible_region_ids_local  # Return just the list

	elif doctype == "GRM Administrative Region":
		# For regions, the caller's `accessible_region_ids` already holds
		# the user's directly-assigned region set (computed in
		# get_changes_since from get_user_region_assignments). Reuse it
		# to avoid a redundant per-doctype query.
		if accessible_region_ids:
			assigned_region_ids = list(accessible_region_ids)
		else:
			user_assignments = get_user_region_assignments(user)
			assigned_region_ids = list(
				set([a.administrative_region for a in user_assignments if a.administrative_region])
			)

		if assigned_region_ids:
			# Filter regions by both user-assigned regions AND projects
			filters = {
				"name": assigned_region_ids,  # Return just the list
				"project": user_accessible_projects,  # Return just the list
			}
		else:
			# User has no region assignments, return no regions
			filters["name"] = "NONE"

	elif doctype == "GRM Project":
		# Special case - filter by project name itself
		filters["name"] = user_accessible_projects

	elif doctype == "GRM Administrative Level Type":
		# Direct project FK on the level-type DocType; scope to the
		# caller's accessible projects.
		filters["project"] = user_accessible_projects

	elif doctype == "User":
		# Only return the current user's data for privacy
		filters["name"] = user

	elif doctype in CHILD_TABLE_DOCTYPES:
		# For doctypes with child table project links, use special child table filter
		child_doctype = CHILD_TABLE_DOCTYPES[doctype]
		# We'll handle this in get_changes_since with proper child table syntax
		filters["_child_table_filter"] = {
			"child_doctype": child_doctype,
			"field": "project",
			"values": user_accessible_projects,
		}

	else:
		log.warning(f"⚠️ [SYNC_BACKEND] Unknown doctype for filtering: {doctype}")
		# Default to no filtering for unknown doctypes
		return {}

	return filters


def validate_user_record_access(doctype, record_data, user):
	"""
	Validate that a user has permission to access/modify a specific record

	Args:
	    doctype (str): The Frappe doctype
	    record_data (dict): The record data (for validation)
	    user (str): Current user email

	Returns:
	    bool: True if user has access, False otherwise
	"""

	# Get fresh user accessible projects (this handles admin check internally)
	user_accessible_projects = get_user_accessible_projects(user)

	# Check if user is Administrator or has System Manager role (handled in get_user_accessible_projects)
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		frappe.log(f"🔓 [SYNC_BACKEND] User {user} has admin access - allowing record operation")
		return True

	# If user has no project access, deny access
	if not user_accessible_projects:
		log.warning(f"❌ [SYNC_BACKEND] User {user} has no project assignments")
		return False

	if doctype == "GRM Issue":
		# Drafts are private to their owner. record_data may not carry
		# docstatus/owner on every code path (e.g. partial WatermelonDB
		# payloads on update), so re-read them from the DB when the
		# record already exists. New-record creates always run as the
		# current user, so the draft they produce is by definition owned
		# by `user` and falls through the check.
		record_id = record_data.get("id") or record_data.get("name")
		if record_id and frappe.db.exists("GRM Issue", record_id):
			row = frappe.db.get_value(
				"GRM Issue",
				record_id,
				("docstatus", "owner"),
				as_dict=True,
			)
			if (
				row
				and (row.get("docstatus") or 0) == 0
				and row.get("owner") != user
				and not _user_can_see_others_drafts(user)
			):
				log.warning(
					f"❌ [SYNC_BACKEND] User {user} cannot access draft "
					f"GRM Issue {record_id} owned by {row.get('owner')}"
				)
				return False

		# Check if issue belongs to user's accessible project
		issue_project = record_data.get("project")

		if issue_project not in user_accessible_projects:
			log.warning(f"❌ [SYNC_BACKEND] User {user} cannot access project {issue_project}")
			return False

		# Also check region access for issues, but use the user's full
		# accessible-region hierarchy (assigned region + all descendants)
		# — not just the direct assignment row. A user assigned at the
		# Country level should be able to file/process issues in every
		# village under that country, mirroring the lookup envelope the
		# mobile client receives via `lookup.user_context.accessible_regions`.
		issue_region = record_data.get("administrative_region")
		if issue_region:
			from egrm.api.lookup import (
				get_user_accessible_regions,
				get_user_region_assignments,
			)

			user_assignments = get_user_region_assignments(user)
			accessible = get_user_accessible_regions(user_assignments) or []
			accessible_region_ids = {r.get("name") or r.get("id") for r in accessible}
			# Always include direct assignments as a defensive fallback
			for a in user_assignments:
				if a.administrative_region:
					accessible_region_ids.add(a.administrative_region)

			if issue_region not in accessible_region_ids:
				log.warning(
					f"❌ [SYNC_BACKEND] User {user} cannot access region {issue_region} "
					f"(accessible regions: {len(accessible_region_ids)} via hierarchy)"
				)
				return False

	elif doctype == "GRM Administrative Region":
		# Check if region is assigned to user and project is accessible
		region_id = record_data.get("name") or record_data.get("id")
		region_project = record_data.get("project")

		# Check project access first
		if region_project not in user_accessible_projects:
			log.warning(
				f"❌ [SYNC_BACKEND] User {user} cannot access project {region_project} for region {region_id}"
			)
			return False

		# Check region assignment
		user_assignments = get_user_region_assignments(user)
		assigned_region_ids = list(set([assignment.administrative_region for assignment in user_assignments]))

		if region_id not in assigned_region_ids:
			log.warning(f"❌ [SYNC_BACKEND] User {user} is not assigned to region {region_id}")
			return False

	elif doctype == "GRM Project":
		# Check if project is accessible to user
		project_id = record_data.get("name") or record_data.get("id")
		if project_id not in user_accessible_projects:
			log.warning(f"❌ [SYNC_BACKEND] User {user} cannot access project {project_id}")
			return False

	elif doctype in [
		"GRM Issue Category",
		"GRM Issue Type",
		"GRM Issue Status",
		"GRM Issue Age Group",
		"GRM Issue Citizen Group",
		"GRM Issue Department",
	]:
		# For lookup tables, check project access if they have a project field
		record_project = record_data.get("project")
		if record_project and record_project not in user_accessible_projects:
			log.warning(f"❌ [SYNC_BACKEND] User {user} cannot access project {record_project} for {doctype}")
			return False

	elif doctype == "User":
		# Only allow access to current user's own record
		record_user = record_data.get("name") or record_data.get("id")
		if record_user != user:
			log.warning(f"❌ [SYNC_BACKEND] User {user} cannot access other user's record {record_user}")
			return False

	elif doctype in ["GRM Issue Log", "GRM Issue Comment"]:
		# For Issue Actions child tables, validate that the user creating the record
		# is the same as the current user (Issue Actions are always performed by the current user)
		record_user = record_data.get("user")
		if record_user and record_user != user:
			log.warning(
				f"❌ [SYNC_BACKEND] User {user} cannot create {doctype} record for other user {record_user}"
			)
			return False

		# Note: Additional validation for parent issue access is handled by the mobile app
		# before sending the sync request, so we trust that the user has access to the related issue
		frappe.log(f"✅ [SYNC_BACKEND] User {user} can create {doctype} record")

	frappe.log(f"✅ [SYNC_BACKEND] User {user} has access to {doctype} record")
	return True


def process_table_changes(table_name, table_changes):
	"""Process changes for a specific table with detailed logging"""
	start_time = time.time()
	frappe.log(f"📋 [SYNC_BACKEND] Processing changes for table: {table_name}")

	# Convert table name back to DocType
	doctype = SYNC_TABLES.get(table_name)
	if not doctype:
		frappe.log_error(f"❌ [SYNC_BACKEND] Unknown table name: {table_name}")
		raise ValueError(f"Unknown table name: {table_name}")

	frappe.log(f"📋 [SYNC_BACKEND] Mapped {table_name} -> {doctype}")

	# Track file URLs for attachments
	file_urls = {}

	# Process created records
	created_records = table_changes.get("created", [])
	if created_records:
		created_start = time.time()
		frappe.log(f"📝 [SYNC_BACKEND] Processing {len(created_records)} created records...")

		for i, raw_record in enumerate(created_records):
			try:
				record_start = time.time()
				frappe.log(f"✏️ [SYNC_BACKEND] raw_record record {raw_record}")

				# Special handling for attachments to collect file URLs
				if doctype == "GRM Issue Attachment":
					file_url = create_record(doctype, raw_record, return_file_url=True)
					if file_url and raw_record.get("id"):
						file_urls[raw_record["id"]] = file_url
				else:
					create_record(doctype, raw_record)

				record_duration = time.time() - record_start
				frappe.log(
					f"📝 [SYNC_BACKEND] Created record {i+1}/{len(created_records)} in {record_duration:.3f}s"
				)
			except Exception as e:
				frappe.log_error(f"❌ [SYNC_BACKEND] Failed to create {doctype} record {i+1}: {e!s}")
				raise

		created_duration = time.time() - created_start
		frappe.log(f"✅ [SYNC_BACKEND] Created {len(created_records)} records in {created_duration:.3f}s")

	# Process updated records
	updated_records = table_changes.get("updated", [])
	if updated_records:
		updated_start = time.time()
		frappe.log(f"✏️ [SYNC_BACKEND] Processing {len(updated_records)} updated records...")

		for i, raw_record in enumerate(updated_records):
			try:
				record_start = time.time()
				update_record(doctype, raw_record)
				record_duration = time.time() - record_start
				frappe.log(
					f"✏️ [SYNC_BACKEND] Updated record {i+1}/{len(updated_records)} in {record_duration:.3f}s"
				)
			except Exception as e:
				frappe.log_error(f"❌ [SYNC_BACKEND] Failed to update {doctype} record {i+1}: {e!s}")
				raise

		updated_duration = time.time() - updated_start
		frappe.log(f"✅ [SYNC_BACKEND] Updated {len(updated_records)} records in {updated_duration:.3f}s")

	# Process deleted records
	deleted_ids = table_changes.get("deleted", [])
	if deleted_ids:
		deleted_start = time.time()
		frappe.log(f"🗑️ [SYNC_BACKEND] Processing {len(deleted_ids)} deleted records...")

		for i, record_id in enumerate(deleted_ids):
			try:
				record_start = time.time()
				delete_record(doctype, record_id)
				record_duration = time.time() - record_start
				frappe.log(
					f"🗑️ [SYNC_BACKEND] Deleted record {i+1}/{len(deleted_ids)} in {record_duration:.3f}s"
				)
			except Exception as e:
				log.warning(f"⚠️ [SYNC_BACKEND] Failed to delete {doctype} record {record_id}: {e!s}")
				# Don't raise for delete failures - record might already be deleted

		deleted_duration = time.time() - deleted_start
		frappe.log(f"✅ [SYNC_BACKEND] Processed {len(deleted_ids)} deletions in {deleted_duration:.3f}s")

	total_duration = time.time() - start_time
	total_records = len(created_records) + len(updated_records) + len(deleted_ids)
	frappe.log(
		f"✅ [SYNC_BACKEND] Completed {table_name} processing: {total_records} total records in {total_duration:.3f}s"
	)

	# Return file URLs for attachments
	if doctype == "GRM Issue Attachment" and file_urls:
		frappe.log(f"📎 [SYNC_BACKEND] Returning file URLs for {len(file_urls)} attachments")
		return file_urls

	return None


def create_record(doctype, raw_record, return_file_url=False):
	"""Create new record from WatermelonDB data with enhanced logging"""
	create_start = time.time()
	record_id = raw_record.get("id")
	user = frappe.session.user
	frappe.log(f"📝 [SYNC_BACKEND] Creating {doctype} record with ID: {record_id} by user: {user}")

	if not record_id:
		frappe.log_error(f"❌ [SYNC_BACKEND] Missing ID in raw record for {doctype}")
		raise ValueError("Missing record ID for creation")

	# Validate user has permission to create this record
	validation_start = time.time()
	if not validate_user_record_access(doctype, raw_record, user):
		validation_duration = time.time() - validation_start
		frappe.log_error(
			f"❌ [SYNC_BACKEND] User {user} lacks permission to create {doctype} record {record_id} (validation took {validation_duration:.4f}s)"
		)
		raise frappe.PermissionError(f"Permission denied to create {doctype} record")
	validation_duration = time.time() - validation_start
	frappe.log(f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s")

	# Handle child table creation differently
	if doctype in ["GRM Issue Log", "GRM Issue Comment", "GRM Issue Attachment"]:
		return create_child_record(doctype, raw_record, return_file_url=return_file_url)

	# Check if record already exists
	existence_check_start = time.time()
	record_exists = frappe.db.exists(doctype, record_id)
	existence_check_duration = time.time() - existence_check_start
	frappe.log(f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s")

	if record_exists:
		log.warning(f"⚠️ [SYNC_BACKEND] Record {record_id} already exists, updating instead")
		return update_record(doctype, raw_record)

	# Convert WatermelonDB data to Frappe format
	conversion_start = time.time()
	frappe_data = watermelon_to_frappe_data(raw_record)
	conversion_duration = time.time() - conversion_start
	frappe.log(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

	# Create new document
	doc_creation_start = time.time()
	doc = frappe.new_doc(doctype)
	doc_creation_duration = time.time() - doc_creation_start
	frappe.log(f"Final frappe_data {frappe_data}")
	frappe.log(f"📄 [SYNC_BACKEND] Document creation took: {doc_creation_duration:.4f}s")

	# Set the name for sync records - store the desired name in a temporary attribute
	doc._sync_name = record_id

	# Set all fields
	field_setting_start = time.time()
	field_count = 0
	for field, value in frappe_data.items():
		print("Field validation", field, hasattr(doc, field))
		if hasattr(doc, field) and field not in [
			"creation",
			"modified",
			"amended_from",
		]:
			setattr(doc, field, value)
			field_count += 1
	field_setting_duration = time.time() - field_setting_start
	frappe.log(f"Final fields after conversion {doc.__dict__}")
	frappe.log(f"🏗️ [SYNC_BACKEND] Field setting took: {field_setting_duration:.4f}s ({field_count} fields)")

	# Insert the document
	insert_start = time.time()
	doc.insert(ignore_permissions=False)  # Respect permissions
	# Auto-submit a freshly-created GRM Issue so the mobile-app contract
	# holds: by the time CitizenReportStep4 (success screen) is shown the
	# offline draft has been promoted to a submitted record on the
	# backend. The permission to *create* was already verified by
	# validate_user_record_access(); the duty matrix only exposes
	# `write`/`submit` to Review/Assignment/Investigate&Resolve users,
	# but Intake-only field officers (the canonical mobile actor) own
	# the records they file. Field-level mutation guards in
	# GRMIssue._enforce_duty_field_constraints still apply on every save,
	# so this elevation is bounded to the submit step only.
	if doctype == "GRM Issue":
		if doc.docstatus == 0:
			doc.flags.ignore_permissions = True
			doc.submit()
	insert_duration = time.time() - insert_start
	frappe.log(f"💾 [SYNC_BACKEND] Document insertion took: {insert_duration:.4f}s")

	create_duration = time.time() - create_start
	frappe.log(f"✅ [SYNC_BACKEND] Created {doctype} record {record_id} in {create_duration:.4f}s")
	frappe.log("📊 [SYNC_BACKEND] Create breakdown:")
	frappe.log(f"  - Permission validation: {validation_duration:.4f}s")
	frappe.log(f"  - Existence check: {existence_check_duration:.4f}s")
	frappe.log(f"  - Data conversion: {conversion_duration:.4f}s")
	frappe.log(f"  - Doc creation: {doc_creation_duration:.4f}s")
	frappe.log(f"  - Field setting: {field_setting_duration:.4f}s")
	frappe.log(f"  - Document insert: {insert_duration:.4f}s")


def create_child_record(doctype, raw_record, return_file_url=False):
	"""Create child table record by adding it to parent document"""
	create_start = time.time()
	record_id = raw_record.get("id")
	user = frappe.session.user
	frappe.log(
		f"📝 [SYNC_BACKEND] Creating child table {doctype} record with ID: {record_id} by user: {user}"
	)

	# Get parent issue ID from raw record
	parent_issue_id = raw_record.get("grm_issue")
	if not parent_issue_id:
		frappe.log_error(f"❌ [SYNC_BACKEND] Missing parent issue ID in {doctype} record {record_id}")
		raise ValueError(f"Missing parent issue ID for {doctype} child record")

	# Check if parent issue exists
	parent_exists = frappe.db.exists("GRM Issue", parent_issue_id)
	if not parent_exists:
		frappe.log_error(
			f"❌ [SYNC_BACKEND] Parent issue {parent_issue_id} does not exist for {doctype} record {record_id}"
		)
		raise ValueError(f"Parent issue {parent_issue_id} does not exist")

	# Get parent document
	parent_doc = frappe.get_doc("GRM Issue", parent_issue_id)
	frappe.log(f"📋 [SYNC_BACKEND] Retrieved parent issue {parent_issue_id}")

	# Convert WatermelonDB data to Frappe format
	conversion_start = time.time()
	frappe_data = watermelon_to_frappe_data(raw_record)
	conversion_duration = time.time() - conversion_start
	frappe.log(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

	# Special handling for GRM Issue Attachment with file data
	created_file_url = None
	if doctype == "GRM Issue Attachment" and raw_record.get("file_data") and raw_record.get("needs_upload"):
		frappe.log(f"📎 [SYNC_BACKEND] Processing file upload for attachment {record_id}")
		frappe.log(
			f"📎 [SYNC_BACKEND] File details: name={raw_record.get('file_name')}, has_data={bool(raw_record.get('file_data'))}"
		)

		file_url = create_file_from_base64(raw_record, parent_issue_id)
		if file_url:
			frappe_data["attachment"] = file_url
			created_file_url = file_url
			frappe.log(f"📎 [SYNC_BACKEND] Created file attachment: {file_url}")
		else:
			frappe.log_error(f"❌ [SYNC_BACKEND] Failed to create file for attachment {record_id}")
			frappe.log_error(f"❌ [SYNC_BACKEND] Raw record debug info: {raw_record}")
			# Don't raise error - continue without file, let attachment record be created
			frappe.log(f"⚠️ [SYNC_BACKEND] Continuing without file for attachment {record_id}")
			# Set attachment field to the original attachment value if it exists, or file_name as fallback
			if raw_record.get("attachment"):
				frappe_data["attachment"] = raw_record.get("attachment")
			else:
				frappe_data["attachment"] = raw_record.get("file_name", "unknown_file")

	# Determine the child table field name dynamically using Frappe meta
	child_table_field = get_child_table_field_name("GRM Issue", doctype)
	if not child_table_field:
		frappe.log_error(f"❌ [SYNC_BACKEND] Cannot find child table field for {doctype} in GRM Issue")
		raise ValueError(f"Cannot find child table field for {doctype} in GRM Issue")

	frappe.log(f"🔍 [SYNC_BACKEND] Using child table field: {child_table_field}")

	# WatermelonDB <-> Frappe field-name mapping for issue child rows.
	#
	# The mobile app's WatermelonDB schema spells the comment author
	# `comment_by` and the body `comment_text`, but the Frappe child
	# doctype `GRM Issue Comment` declares `user` and `comment` as the
	# mandatory canonical fields (see grm_issue_comment.json). Without
	# this translation the push lands on the parent and only sets
	# `comment_date`, leaving `user` and `comment` blank — Frappe then
	# raises `MandatoryError: [GRM Issue, ...]: user, comment` on
	# parent_doc.save(). The mapping is one-way (push only) and matches
	# the AQE IL-2 contract verbatim.
	_CHILD_FIELD_ALIASES = {
		"GRM Issue Comment": {
			"comment_text": "comment",
			"comment_by": "user",
		},
	}
	aliases = _CHILD_FIELD_ALIASES.get(doctype, {})
	if aliases:
		for src, dst in aliases.items():
			if src in frappe_data and dst not in frappe_data:
				frappe_data[dst] = frappe_data.pop(src)
			elif src in frappe_data:
				# Both spellings present: drop the WatermelonDB one so we
				# don't try to setattr a non-existent field on the
				# canonical doctype later.
				frappe_data.pop(src, None)

	# Create child record as proper Document object
	child_doc = frappe.new_doc(doctype)
	child_doc.name = record_id  # Use WatermelonDB ID
	child_doc.parent = parent_issue_id
	child_doc.parenttype = "GRM Issue"
	child_doc.parentfield = child_table_field

	# Add all fields from frappe_data except the parent reference
	for field, value in frappe_data.items():
		if field not in ["grm_issue", "name", "parent", "parenttype", "parentfield"]:
			if hasattr(child_doc, field):
				setattr(child_doc, field, value)

	frappe.log(f"📝 [SYNC_BACKEND] Child record data: {child_doc.as_dict()}")

	# Add child record to parent document
	if not hasattr(parent_doc, child_table_field):
		# If the child table field doesn't exist, create it as empty list
		setattr(parent_doc, child_table_field, [])

	child_table = getattr(parent_doc, child_table_field, [])

	# Check if child record already exists
	for existing_record in child_table:
		if existing_record.get("name") == record_id:
			break

	# Add new child record as Document object
	child_table.append(child_doc)
	frappe.log(f"📝 [SYNC_BACKEND] Added child record {record_id} to parent {parent_issue_id}")

	# Save parent document. The L1 'write' duty is restricted to
	# Review/Assignment/Investigate&Resolve users, but the canonical
	# mobile actor is Intake-only and must still be able to attach
	# files to issues they own (the offline-first contract). Access to
	# *this* child row was already validated by
	# validate_user_record_access(GRM Issue Attachment, ...). The parent
	# save is just the persistence mechanism for an `allow_on_submit=1`
	# child table — the Intake user does not gain free-form write
	# access to the parent issue's restricted fields because
	# GRMIssue._enforce_duty_field_constraints fires on every save and
	# short-circuits only on flags.ignore_permissions, which the field
	# set above does not change.
	save_start = time.time()
	parent_doc.flags.ignore_permissions = True
	try:
		parent_doc.save(ignore_permissions=True)
	except frappe.exceptions.UpdateAfterSubmitError:
		# Issue is already submitted, we need to allow updates to child table
		frappe.log("⚠️ [SYNC_BACKEND] Issue is submitted, allowing child table updates")
		parent_doc.flags.ignore_validate_update_after_submit = True
		parent_doc.save(ignore_permissions=True)
	save_duration = time.time() - save_start
	frappe.log(f"💾 [SYNC_BACKEND] Parent document save took: {save_duration:.4f}s")

	create_duration = time.time() - create_start
	frappe.log(
		f"✅ [SYNC_BACKEND] Created child table {doctype} record {record_id} in {create_duration:.4f}s"
	)
	frappe.log("📊 [SYNC_BACKEND] Child create breakdown:")
	frappe.log(f"  - Data conversion: {conversion_duration:.4f}s")
	frappe.log(f"  - Parent document save: {save_duration:.4f}s")

	# Return file URL if requested and available
	if return_file_url and created_file_url:
		return created_file_url

	return None


def update_record(doctype, raw_record):
	"""
	Update existing record using WatermelonDB's _changed property for optimized field updates.
	Uses direct database updates to avoid TimestampMismatchError.
	"""
	update_start = time.time()
	record_id = raw_record.get("id")
	user = frappe.session.user
	frappe.log(f"✏️ [SYNC_BACKEND] Updating {doctype} record with ID: {record_id} by user: {user}")
	frappe.log(f"✏️ [SYNC_BACKEND] Update raw data {raw_record}")

	if not record_id:
		frappe.log_error(f"❌ [SYNC_BACKEND] Missing ID in raw record for {doctype}")
		raise ValueError("Missing record ID for update")

	# Validate user has permission to update this record
	time.time()
	if not validate_user_record_access(doctype, raw_record, user):
		raise frappe.PermissionError(f"Permission denied to update {doctype} record")

	# Verify record exists
	if not frappe.db.exists(doctype, record_id):
		raise ValueError(f"Record {record_id} not found")

	# Parse changed fields from WatermelonDB
	changed_fields_raw = raw_record.get("_changed", "")
	if not changed_fields_raw:
		frappe.log_error(f"No _changed property in record {record_id}")
		return

	changed_fields = [field.strip() for field in changed_fields_raw.split(",") if field.strip()]
	if not changed_fields:
		return

	# Convert and filter data
	frappe_data = watermelon_to_frappe_data(raw_record)
	fields_to_update = {field: frappe_data[field] for field in changed_fields if field in frappe_data}

	if not fields_to_update:
		return

	# Update fields directly in database
	for field_name, field_value in fields_to_update.items():
		if field_name != "updated_at":
			frappe.db.set_value(doctype, record_id, field_name, field_value, update_modified=False)

	frappe.db.commit()

	update_duration = time.time() - update_start
	frappe.log(
		f"✅ [SYNC_BACKEND] Updated {doctype} record {record_id} "
		f"with {len(fields_to_update)} fields in {update_duration:.4f}s"
	)


def delete_record(doctype, record_id):
	"""Delete record (soft delete) with enhanced logging"""
	delete_start = time.time()
	user = frappe.session.user
	frappe.log(f"🗑️ [SYNC_BACKEND] Deleting {doctype} record: {record_id} by user: {user}")

	# Check if record exists
	existence_check_start = time.time()
	record_exists = frappe.db.exists(doctype, record_id)
	existence_check_duration = time.time() - existence_check_start
	frappe.log(f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s")

	if not record_exists:
		frappe.log(f"🗑️ [SYNC_BACKEND] Record {record_id} already deleted or doesn't exist")
		return

	try:
		# Get document for permission validation
		doc_fetch_start = time.time()
		doc = frappe.get_doc(doctype, record_id)
		doc_fetch_duration = time.time() - doc_fetch_start
		frappe.log(f"📄 [SYNC_BACKEND] Document fetch took: {doc_fetch_duration:.4f}s")

		# Validate user has permission to delete this record
		validation_start = time.time()
		record_data = doc.as_dict()
		if not validate_user_record_access(doctype, record_data, user):
			validation_duration = time.time() - validation_start
			frappe.log_error(
				f"❌ [SYNC_BACKEND] User {user} lacks permission to delete {doctype} record {record_id} (validation took {validation_duration:.4f}s)"
			)
			return  # Don't raise exception, just skip this delete
		validation_duration = time.time() - validation_start
		frappe.log(f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s")

		# Delete document
		delete_operation_start = time.time()
		doc.delete()
		delete_operation_duration = time.time() - delete_operation_start
		frappe.log(f"🗑️ [SYNC_BACKEND] Delete operation took: {delete_operation_duration:.4f}s")

		delete_duration = time.time() - delete_start
		frappe.log(f"✅ [SYNC_BACKEND] Deleted {doctype} record {record_id} in {delete_duration:.4f}s")
		frappe.log("📊 [SYNC_BACKEND] Delete breakdown:")
		frappe.log(f"  - Existence check: {existence_check_duration:.4f}s")
		frappe.log(f"  - Document fetch: {doc_fetch_duration:.4f}s")
		frappe.log(f"  - Permission validation: {validation_duration:.4f}s")
		frappe.log(f"  - Delete operation: {delete_operation_duration:.4f}s")

	except frappe.PermissionError:
		delete_duration = time.time() - delete_start
		log.warning(
			f"⚠️ [SYNC_BACKEND] No permission to delete {doctype} {record_id} (took {delete_duration:.4f}s)"
		)
		# Don't raise - just log the issue
	except Exception as e:
		delete_duration = time.time() - delete_start
		frappe.log_error(
			f"❌ [SYNC_BACKEND] Failed to delete {doctype} {record_id} after {delete_duration:.4f}s: {e!s}"
		)
		# Don't raise - continue with other operations


def frappe_to_watermelon_raw(frappe_doc):
	"""
	Convert Frappe document to WatermelonDB raw format

	CRITICAL: WatermelonDB raw records MUST NOT contain _status or _changed fields.
	These are internal WatermelonDB fields managed by the mobile app only.

	According to WatermelonDB docs:
	- Records MUST have an 'id' field (mapped from Frappe's 'name' field)
	- Records MUST NOT have '_status' or '_changed' fields

	Performance: this is a HOT loop — `get_changes_since` calls it once per
	record, so a typical full pull invokes it 5k–10k times. The previous
	implementation emitted ~9 `frappe.log()` lines per invocation; under
	Frappe's developer mode every log line is appended to `debug_log` and
	serialized into the response body, costing >800ms on a 9.5k-record
	pull. The hot-loop log emissions have been deleted; the function now
	only allocates what it needs to return.
	"""
	# Handle both dict and Document objects
	if isinstance(frappe_doc, Document):
		doc_dict = frappe_doc.as_dict()
	else:
		doc_dict = frappe_doc

	# CRITICAL: Start with clean record - NO _status or _changed fields
	# Both `id` (WatermelonDB convention) and `name` (Frappe convention)
	# carry the document name. Inner-workflow consumers reference it by
	# `name`; mobile clients reference it by `id`. Return both.
	doc_name = doc_dict.get("name")
	if not doc_name:
		frappe.log_error(f"❌ [SYNC_BACKEND] Missing 'name' field in Frappe document: {doc_dict}")
		raise ValueError("Frappe document missing 'name' field - cannot create WatermelonDB record")
	raw_record = {"id": doc_name, "name": doc_name}

	# Hot-path constants: keep field-name lookups O(1) and out of the
	# iteration overhead.
	_TIMESTAMP_FIELDS = frozenset(
		(
			"creation",
			"modified",
			"issue_date",
			"intake_date",
			"resolution_date",
			"accepted_date",
			"rejected_date",
			"escalated_date",
			"rated_date",
			"appeal_date",
		)
	)

	# Hot-path timestamp conversion: Frappe's `get_timestamp` is
	# `time.mktime(getdate(date).timetuple())` which is ~5x slower than
	# calling `.timestamp()` directly on a datetime object. With ~3.5k
	# GRM Issues + ~4.5k GRM Issue Logs being serialized per pull (each
	# touching 2-8 timestamp fields) this is the second-largest hot
	# spot in the warm pull. Use the fast path for datetime instances
	# and only fall back to `get_timestamp` for strings/dates.
	from datetime import date as _date
	from datetime import datetime as _dt

	def _ts_ms(v):
		if isinstance(v, _dt):
			return int(v.timestamp() * 1000)
		# date-only or string — use Frappe's parser as the slow fallback
		return int(get_timestamp(v) * 1000)

	# Direct field copy - no transformation needed after schema alignment
	for field_name, value in doc_dict.items():
		# Skip internal fields and the name field (already mapped to id)
		if field_name.startswith("_") or field_name == "name":
			continue

		# Only convert timestamps - everything else copies directly
		if value and field_name in _TIMESTAMP_FIELDS:
			raw_record[field_name] = _ts_ms(value)
		else:
			# Direct assignment - fields already aligned
			raw_record[field_name] = value

	# Special field mapping for attachments: map 'parent' to 'grm_issue'
	if doc_dict.get("doctype") == "GRM Issue Attachment" and doc_dict.get("parent"):
		raw_record["grm_issue"] = doc_dict.get("parent")
	elif doc_dict.get("parent") and doc_dict.get("parenttype") == "GRM Issue":
		raw_record["grm_issue"] = doc_dict.get("parent")

	# Add standard timestamps for WatermelonDB and sync tracking. The
	# creation/modified fields were already converted in the loop above
	# when present — reuse those values to avoid double-converting.
	if "creation" in raw_record:
		raw_record["created_at"] = raw_record["creation"]
	else:
		creation_time = doc_dict.get("creation")
		if creation_time:
			created_at_ms = _ts_ms(creation_time)
			raw_record["created_at"] = created_at_ms
			raw_record["creation"] = created_at_ms

	if "modified" in raw_record:
		raw_record["updated_at"] = raw_record["modified"]
	else:
		modified_time = doc_dict.get("modified")
		if modified_time:
			updated_at_ms = _ts_ms(modified_time)
			raw_record["updated_at"] = updated_at_ms
			raw_record["modified"] = updated_at_ms

	# Final validation - ensure no WatermelonDB internal fields. These
	# should never appear (we never set them), but the original code
	# asserted on them defensively, so keep the assertion.
	raw_record.pop("_status", None)
	raw_record.pop("_changed", None)

	return raw_record


def watermelon_to_frappe_data(raw_record):
	"""Convert WatermelonDB raw record to Frappe data - MINIMAL TRANSFORMATION"""
	conversion_start = time.time()
	frappe.log("🔄 [SYNC_BACKEND] Converting WatermelonDB raw record to Frappe data")

	frappe_data = {}
	processed_fields = 0
	timestamp_conversions = 0

	# Direct field copy - no complex transformation needed
	field_processing_start = time.time()

	for key, value in raw_record.items():
		if key.startswith("_"):  # Skip WatermelonDB internal fields
			continue

		processed_fields += 1

		# Only convert timestamp fields back to datetime
		if key in [
			"creation",
			"modified",
			"issue_date",
			"intake_date",
			"resolution_date",
			"accepted_date",
			"rejected_date",
			"escalated_date",
			"rated_date",
			"appeal_date",
			"timestamp",
		]:
			if value and isinstance(value, int | float):
				# Convert from milliseconds to datetime
				timestamp_start = time.time()
				frappe_data[key] = datetime.fromtimestamp(value / 1000)
				timestamp_duration = time.time() - timestamp_start
				timestamp_conversions += 1
				frappe.log(
					f"🕐 [SYNC_BACKEND] Converted {key} timestamp in {timestamp_duration:.4f}s: {value} -> {frappe_data[key]}"
				)
		else:
			# Direct assignment - fields already aligned
			frappe_data[key] = value

	# Special field mapping for attachments: map 'grm_issue' back to 'parent'
	if raw_record.get("grm_issue"):
		frappe_data["parent"] = raw_record.get("grm_issue")
		frappe.log(f"📎 [SYNC_BACKEND] Mapped grm_issue field to parent: {raw_record.get('grm_issue')}")

	frappe_data["name"] = raw_record["id"]

	field_processing_duration = time.time() - field_processing_start
	conversion_duration = time.time() - conversion_start

	frappe.log(f"✅ [SYNC_BACKEND] WatermelonDB-to-Frappe conversion completed in {conversion_duration:.4f}s")
	frappe.log("🔍 [SYNC_BACKEND] Conversion breakdown:")
	frappe.log(f"  - Field processing: {field_processing_duration:.4f}s ({processed_fields} fields)")
	frappe.log(f"  - Timestamp conversions: {timestamp_conversions} conversions")

	return frappe_data


# Legacy endpoint compatibility (optional - can be removed later)
@frappe.whitelist()
def get_user_data(project_id=None):
	"""
	Legacy compatibility endpoint - delegates to WatermelonDB sync
	This can be removed once all clients are updated to use WatermelonDB sync
	"""
	try:
		# Trigger a full sync by calling pullChanges with no timestamp
		result = pull_changes(lastPulledAt=None)

		# Transform the response to match legacy format if needed
		legacy_data = {}
		if result and result.get("changes"):
			for table_name, table_changes in result["changes"].items():
				# Combine created and updated records
				all_records = table_changes.get("created", []) + table_changes.get("updated", [])
				legacy_data[table_name] = all_records

		return {
			"status": "success",
			"data": legacy_data,
			"timestamp": result.get("timestamp"),
		}

	except Exception as e:
		frappe.log_error(f"Legacy get_user_data failed: {e!s}")
		return {"status": "error", "message": str(e)}


def get_child_table_field_name(parent_doctype, child_doctype):
	"""
	Dynamically determine the field name for a child table in the parent DocType

	Args:
	    parent_doctype (str): The parent DocType name (e.g., "GRM Issue")
	    child_doctype (str): The child DocType name (e.g., "GRM Issue Log")

	Returns:
	    str: Field name in parent DocType, or None if not found
	"""
	try:
		# Get parent DocType meta
		parent_meta = frappe.get_meta(parent_doctype)

		# Find table fields that link to the child doctype
		for field in parent_meta.fields:
			if field.fieldtype == "Table" and field.options == child_doctype:
				frappe.log(
					f"🔍 [SYNC_BACKEND] Found child table field: {field.fieldname} for {child_doctype}"
				)
				return field.fieldname

		frappe.log_error(f"❌ [SYNC_BACKEND] No table field found for {child_doctype} in {parent_doctype}")
		return None

	except Exception as e:
		frappe.log_error(f"❌ [SYNC_BACKEND] Error finding child table field: {e!s}")
		return None


def create_file_from_base64(raw_record, parent_issue_id):
	"""
	Create a Frappe File record from Base64 data sent by mobile app

	Args:
	    raw_record (dict): Raw record containing file data
	    parent_issue_id (str): Parent issue ID for file organization

	Returns:
	    str: File URL if successful, None if failed
	"""
	try:
		file_data = raw_record.get("file_data")
		file_name = raw_record.get("file_name")

		if not file_data or not file_name:
			frappe.log_error("❌ [SYNC_BACKEND] Missing file data or filename")
			return None

		frappe.log(f"📎 [SYNC_BACKEND] Creating file from Base64 data: {file_name}")

		# Import necessary modules
		import base64
		import os

		from frappe.utils.file_manager import save_file

		# Validate file name and extension
		frappe.log(f"📎 [SYNC_BACKEND] Validating file name: {file_name}")
		if not validate_file_name(file_name):
			frappe.log_error(f"❌ [SYNC_BACKEND] Invalid file name: {file_name}")
			return None
		frappe.log("📎 [SYNC_BACKEND] File name validation passed")

		# Decode Base64 data
		frappe.log(f"📎 [SYNC_BACKEND] Decoding Base64 data (length: {len(file_data)})")
		try:
			file_content = base64.b64decode(file_data)
		except Exception as decode_error:
			frappe.log_error(f"❌ [SYNC_BACKEND] Invalid Base64 data: {decode_error!s}")
			return None
		frappe.log("📎 [SYNC_BACKEND] Base64 decoding successful")

		# Validate file size
		file_size = len(file_content)
		max_size = get_max_file_size()
		frappe.log(f"📎 [SYNC_BACKEND] File size check: {file_size} bytes (max: {max_size} bytes)")
		if file_size > max_size:
			frappe.log_error(f"❌ [SYNC_BACKEND] File too large: {file_size} bytes > {max_size} bytes")
			return None
		frappe.log("📎 [SYNC_BACKEND] File size validation passed")

		# Validate file type
		frappe.log(f"📎 [SYNC_BACKEND] Validating file type for: {file_name}")
		if not validate_file_type(file_name, file_content):
			frappe.log_error(f"❌ [SYNC_BACKEND] Invalid file type: {file_name}")
			return None
		frappe.log("📎 [SYNC_BACKEND] File type validation passed")

		frappe.log(f"📎 [SYNC_BACKEND] File validation passed: {file_name} ({file_size} bytes)")

		# Create file using Frappe's file manager
		frappe.log(
			f"📎 [SYNC_BACKEND] Calling save_file with fname={file_name}, dt=GRM Issue, dn={parent_issue_id}"
		)
		try:
			file_doc = save_file(
				fname=file_name,
				content=file_content,
				dt="GRM Issue",
				dn=parent_issue_id,
				folder=None,
				is_private=0,  # Public files for issue attachments
			)
			frappe.log(f"📎 [SYNC_BACKEND] save_file returned: {file_doc}")
			frappe.log(f"📎 [SYNC_BACKEND] File doc type: {type(file_doc)}")
			frappe.log(f"📎 [SYNC_BACKEND] File doc attributes: {dir(file_doc) if file_doc else 'None'}")

			if file_doc and hasattr(file_doc, "file_url"):
				file_url = file_doc.file_url
				frappe.log(f"📎 [SYNC_BACKEND] Successfully created file: {file_url}")
				return file_url
			else:
				frappe.log_error(f"❌ [SYNC_BACKEND] save_file returned invalid result: {file_doc}")
				return None
		except Exception as save_error:
			frappe.log_error(f"❌ [SYNC_BACKEND] save_file failed: {save_error!s}")
			return None

	except Exception as e:
		frappe.log_error(f"❌ [SYNC_BACKEND] Error creating file from Base64: {e!s}")
		return None


def validate_file_name(file_name):
	"""
	Validate file name for security and compatibility

	Args:
	    file_name (str): File name to validate

	Returns:
	    bool: True if valid, False otherwise
	"""
	import os
	import re

	# Check for empty or None
	if not file_name or not file_name.strip():
		return False

	# Check length
	if len(file_name) > 255:
		return False

	# Check for dangerous characters
	dangerous_chars = ["..", "/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"]
	for char in dangerous_chars:
		if char in file_name:
			frappe.log_error(
				f"❌ [SYNC_BACKEND] File name contains dangerous character '{char}': {file_name}"
			)
			return False

	# Check for valid extension
	allowed_extensions = [
		".jpg",
		".jpeg",
		".png",
		".gif",
		".bmp",
		".svg",  # Images
		".pdf",
		".doc",
		".docx",
		".txt",
		".rtf",  # Documents
		".3gp",
		".mp3",
		".wav",
		".ogg",
		".aac",
		".flac",  # Audio
		".mp4",
		".avi",
		".mov",
		".wmv",
		".mkv",  # Video
	]

	file_ext = os.path.splitext(file_name)[1].lower()
	frappe.log(f"📎 [SYNC_BACKEND] File extension: '{file_ext}' (allowed: {allowed_extensions})")
	if file_ext not in allowed_extensions:
		frappe.log_error(f"❌ [SYNC_BACKEND] File extension '{file_ext}' not allowed for file: {file_name}")
		return False

	frappe.log(f"📎 [SYNC_BACKEND] File name validation successful: {file_name}")
	return True


def validate_file_type(file_name, file_content):
	"""
	Validate file type based on content (magic bytes)

	Args:
	    file_name (str): File name
	    file_content (bytes): File content

	Returns:
	    bool: True if valid, False otherwise
	"""
	import os

	# Get file extension
	file_ext = os.path.splitext(file_name)[1].lower()

	# Check minimum file size
	if len(file_content) < 4:
		return False

	# Magic byte signatures for common file types
	magic_bytes = {
		".jpg": [b"\xff\xd8\xff"],
		".jpeg": [b"\xff\xd8\xff"],
		".png": [b"\x89PNG\r\n\x1a\n"],
		".gif": [b"GIF87a", b"GIF89a"],
		".pdf": [b"%PDF"],
		".mp3": [b"ID3", b"\xff\xfb"],
		".mp4": [b"ftyp"],
		".3gp": [b"ftyp3g"],  # 3GP files have 'ftyp3g' signature
		".avi": [b"RIFF"],
		".wav": [b"RIFF"],
	}

	# Check if file has expected magic bytes
	if file_ext in magic_bytes:
		expected_signatures = magic_bytes[file_ext]
		file_header = file_content[:16]  # Check first 16 bytes

		frappe.log(f"📎 [SYNC_BACKEND] Checking magic bytes for {file_ext}")
		frappe.log(f"📎 [SYNC_BACKEND] File header: {file_header.hex()}")
		frappe.log(f"📎 [SYNC_BACKEND] Expected signatures: {[sig.hex() for sig in expected_signatures]}")

		for signature in expected_signatures:
			if file_header.startswith(signature):
				frappe.log(f"📎 [SYNC_BACKEND] Magic bytes match for {file_ext}")
				return True

		# Check if it's actually a different image type with wrong extension
		all_image_signatures = {
			"PNG": b"\x89PNG\r\n\x1a\n",
			"JPEG": b"\xff\xd8\xff",
			"GIF87a": b"GIF87a",
			"GIF89a": b"GIF89a",
		}

		detected_type = None
		for img_type, signature in all_image_signatures.items():
			if file_header.startswith(signature):
				detected_type = img_type
				break

		if detected_type and file_ext in [".jpg", ".jpeg", ".png", ".gif"]:
			frappe.log(
				f"⚠️ [SYNC_BACKEND] File extension mismatch: {file_name} has {file_ext} extension but is actually {detected_type}"
			)
			frappe.log("⚠️ [SYNC_BACKEND] Allowing image with mismatched extension")
			return True

		# For audio files, be more lenient with validation
		audio_extensions = [".3gp", ".mp3", ".wav", ".ogg", ".aac", ".flac"]
		if file_ext in audio_extensions:
			frappe.log(
				f"📎 [SYNC_BACKEND] Audio file with potential signature mismatch, allowing: {file_name}"
			)
			return True

		# If no magic bytes match for non-audio files, it's suspicious
		frappe.log_error(
			f"❌ [SYNC_BACKEND] File type mismatch: {file_name} does not match expected signature"
		)
		return False

	# For file types without magic byte checking, allow them
	frappe.log(f"📎 [SYNC_BACKEND] No magic byte check for {file_ext}, allowing")
	return True


def get_max_file_size():
	"""
	Get maximum allowed file size in bytes

	Returns:
	    int: Maximum file size in bytes
	"""
	# Default to 25MB, can be configured in site config
	default_size = 25 * 1024 * 1024  # 25MB

	try:
		# Check if configured in site settings
		max_size = frappe.conf.get("max_file_size", default_size)
		return int(max_size)
	except (ValueError, TypeError):
		return default_size


def optimize_attachment_sync(attachment_changes, last_sync_time, page_boundary=None):
	"""
	Optimize attachment sync using Frappe QB for better performance

	Args:
	    attachment_changes (dict): Current attachment changes from regular sync
	    last_sync_time (datetime): Last sync timestamp
	    page_boundary (datetime | None): Upper bound of the current page. This
	        function re-queries attachments itself, so it has to honour the same
	        window as the rest of the response — attachments are the heaviest
	        rows in the payload (they carry base64 file data), so letting them
	        ignore the cap would defeat the pagination.

	Returns:
	    dict: Optimized attachment changes with file data
	"""
	start_time = time.time()
	frappe.log("📎 [SYNC_BACKEND] Starting optimized attachment sync")

	try:
		# Use Frappe QB for efficient attachment querying
		attachment_table = frappe.qb.DocType("GRM Issue Attachment")
		accessible_issues = accessible_issue_subquery(frappe.session.user)
		if accessible_issues is None:
			frappe.log("⚠️ [SYNC_BACKEND] No accessible issues found for attachment filtering")
			return {"created": [], "updated": [], "deleted": attachment_changes.get("deleted", [])}

		# Only GRM Issue uses this child table; naming the parenttype lets the
		# standard (parent, parenttype) child index carry the semi-join.
		in_scope = (attachment_table.parenttype == "GRM Issue") & attachment_table.parent.isin(
			accessible_issues
		)

		# Query for created attachments
		created_query = (
			frappe.qb.from_(attachment_table)
			.select("*")
			.where(in_scope)
			.where(attachment_table.creation > last_sync_time)
		)

		# Query for updated attachments
		updated_query = (
			frappe.qb.from_(attachment_table)
			.select("*")
			.where(in_scope)
			.where(attachment_table.modified > last_sync_time)
			.where(attachment_table.creation <= last_sync_time)
		)

		if page_boundary is not None:
			created_query = created_query.where(attachment_table.modified <= page_boundary)
			updated_query = updated_query.where(attachment_table.modified <= page_boundary)

		# Execute queries
		created_attachments = created_query.run(as_dict=True)
		updated_attachments = updated_query.run(as_dict=True)

		frappe.log(
			f"📎 [SYNC_BACKEND] Found {len(created_attachments)} created, {len(updated_attachments)} updated attachments"
		)

		# Process created attachments with file data
		processed_created = []
		for attachment in created_attachments:
			raw_record = frappe_to_watermelon_raw(attachment)

			# Always add file data for created attachments
			if attachment.get("attachment"):
				file_data = get_attachment_file_data(attachment.get("attachment"))
				if file_data:
					raw_record["file_data"] = file_data
					frappe.log(
						f"📎 [SYNC_BACKEND] Added file data for created attachment: {attachment.get('name')}"
					)

			processed_created.append(raw_record)

		# Process updated attachments with file data
		processed_updated = []
		for attachment in updated_attachments:
			raw_record = frappe_to_watermelon_raw(attachment)

			# Add file data for updated attachments to ensure mobile app has the file
			if attachment.get("attachment"):
				file_data = get_attachment_file_data(attachment.get("attachment"))
				if file_data:
					raw_record["file_data"] = file_data
					frappe.log(
						f"📎 [SYNC_BACKEND] Added file data for updated attachment: {attachment.get('name')}"
					)

			processed_updated.append(raw_record)

		duration = time.time() - start_time
		frappe.log(f"📎 [SYNC_BACKEND] Optimized attachment sync completed in {duration:.3f}s")

		return {
			"created": processed_created,
			"updated": processed_updated,
			"deleted": attachment_changes.get("deleted", []),
		}

	except Exception as e:
		frappe.log_error(f"❌ [SYNC_BACKEND] Error in optimized attachment sync: {e!s}")
		# Fallback to original data
		return attachment_changes


def accessible_issue_subquery(user):
	"""Build a subquery selecting every GRM Issue ``user`` may see.

	Attachments are filtered by their parent issue's scope. The obvious way to
	do that is to materialise the accessible issue IDs and hand them to
	``parent.isin([...])`` — which is what this used to do, and it does not
	survive contact with real data. pypika renders every element of an ``IN``
	list through a Python call, so a user entitled to 50k issues burned ~1s
	building the SQL string before MariaDB saw the query, twice per pull:
	cProfile put 2.588s of a 2.731s pull inside this one function. A subquery
	keeps the ID set server-side, where it is an indexed semi-join, and the
	cost stops scaling with the user's entitlement.

	Scope is taken from ``get_user_filters_for_doctype`` rather than rebuilt
	here, so attachments can never be scoped differently from the issues that
	carry them — the previous hand-rolled filter used directly-assigned
	regions while the issue query used the BFS-expanded set, and only the
	union with the synced IDs papered over the difference.

	Returns ``None`` when the user is entitled to nothing.
	"""
	issue_table = frappe.qb.DocType("GRM Issue")
	filters = get_user_filters_for_doctype("GRM Issue", None, None, user)
	filters.pop("_child_table_filter", None)
	if not filters:
		return None

	query = frappe.qb.from_(issue_table).select(issue_table.name)
	for field, value in filters.items():
		column = getattr(issue_table, field)
		if isinstance(value, list | tuple | set):
			if not value:
				return None
			query = query.where(column.isin(list(value)))
		else:
			query = query.where(column == value)

	# Mirror _strip_foreign_drafts: a draft is private to its creator, so its
	# attachments are too. The old ID-list build-up skipped this check and
	# leaked foreign drafts' attachments for any issue that predated the
	# watermark.
	if not _user_can_see_others_drafts(user):
		query = query.where((issue_table.docstatus != 0) | (issue_table.owner == user))

	return query


def get_attachment_file_data(file_url):
	"""
	Get file data as base64 from Frappe file system

	Args:
	    file_url (str): File URL from Frappe (e.g., '/files/filename.ext')

	Returns:
	    str: Base64 encoded file data, or None if file not found/error
	"""
	if not file_url:
		return None

	try:
		import base64
		import os

		# Get the file path from Frappe's file system
		if file_url.startswith("/files/"):
			# Remove the '/files/' prefix to get the actual filename
			filename = file_url[7:]  # Remove '/files/' (7 characters)

			# Get the full file path using Frappe's file utilities
			file_path = frappe.get_site_path("public", "files", filename)

			frappe.log(f"📎 [SYNC_BACKEND] Reading file from path: {file_path}")

			# Check if file exists
			if not os.path.exists(file_path):
				frappe.log(f"⚠️ [SYNC_BACKEND] File not found: {file_path}")
				return None

			# Read file and encode as base64
			with open(file_path, "rb") as file:
				file_content = file.read()
				file_base64 = base64.b64encode(file_content).decode("utf-8")

				frappe.log(
					f"📎 [SYNC_BACKEND] Successfully read file: {filename} ({len(file_content)} bytes)"
				)
				return file_base64

		else:
			frappe.log(f"⚠️ [SYNC_BACKEND] Unsupported file URL format: {file_url}")
			return None

	except Exception as e:
		frappe.log_error(f"❌ [SYNC_BACKEND] Error reading file {file_url}: {e!s}")
		return None
