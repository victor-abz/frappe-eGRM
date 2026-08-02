"""Project-scoped user-import preprocessor for the Step 9 wizard.

This module is the server-side core of the Step 9 bulk-import flow. It is
called from the wizard RPC layer (``prepare_user_import``) and from the
forthcoming ``import-users`` CLI; it does NOT execute the import itself —
that is delegated to Frappe's built-in ``Data Import`` engine. Our job is
to make the user's CSV/XLSX *look like* a normal Data Import file by:

1. Resolving multiple admin-level columns (e.g. Province / District / Sector
   — names defined per project) into the single ``administrative_region``
   Link the doctype expects (``resolve_region``).
2. Auto-detecting a sane initial mapping from source headers to target
   doctype fields (``auto_detect_mapping``) — the user can override every
   guess in the UI.
3. Validating that mapping against the doctype's ``reqd: 1`` markers
   (``validate_mapping``) — never hard-coding "what must be in the CSV".
4. Materialising a staged CSV with one column per resolved target field,
   ready to be attached to a ``Data Import`` record
   (``materialize_staged_csv``).

Style mirrors ``admin_region_importer.py``: pure Python, structured
``dict`` returns, ``logger = logging.getLogger(__name__)``, errors
accumulated rather than raised (except for the documented
``auto_create=False`` path in ``resolve_region``).
"""

from __future__ import annotations

import csv
import logging
import os
import re
from typing import Any

import frappe

logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 50

# Target tokens used in the mapping dict's ``target`` field. The "skip"
# sentinel is exposed to JS so the user can explicitly drop a column.
TARGET_SKIP = "(skip)"
TARGET_REGION = "administrative_region"

# Excel formula-error tokens that leak into XLSX cells when the source
# spreadsheet has a broken/unsupported formula. We treat them as empty
# strings so synthesis fallbacks (e.g. email derivation from first/last
# name) can kick in instead of writing literal "#NAME?" into the DB.
_EXCEL_ERROR_TOKENS = frozenset(
	{
		"#NAME?",
		"#REF!",
		"#DIV/0!",
		"#VALUE!",
		"#N/A",
		"#NULL!",
		"#NUM!",
	}
)


def _clean_cell(val: str) -> str:
	"""Strip Excel formula-error tokens — return ``""`` for those cells."""
	s = (val or "").strip()
	return "" if s in _EXCEL_ERROR_TOKENS else s


# Smart-quote → ASCII map. Excel and Word frequently autocorrect typed
# apostrophes/double quotes into curly variants (U+2018/2019/201C/201D).
# When the operator types a role like "Digital ambassador's supervisor"
# into Step 3 with a straight quote and the imported file contains the
# curly variant (or vice versa), naive lower-cased equality misses the
# match and the row gets dropped as an unknown role. Normalize both
# directions through the same transform before comparing.
_QUOTE_NORMALIZE = str.maketrans(
	{
		"‘": "'",  # left single quotation mark
		"’": "'",  # right single quotation mark / curly apostrophe
		"‚": "'",  # single low-9 quotation mark
		"‛": "'",  # single high-reversed-9 quotation mark
		"“": '"',  # left double quotation mark
		"”": '"',  # right double quotation mark
		"„": '"',  # double low-9 quotation mark
		"‟": '"',  # double high-reversed-9 quotation mark
	}
)


def _normalize_label(s: str) -> str:
	"""Case-fold, trim, and ASCII-fold curly quotes for label comparisons."""
	return (s or "").translate(_QUOTE_NORMALIZE).strip().lower()


def _synthesize_email(first: str, last: str, domain: str) -> str:
	"""Build ``firstname.lastname@<domain>`` for rows missing emails.

	Used when the source file had an empty / errored email cell AND the
	operator opted in to synthesis. ``domain`` is operator-supplied (e.g.
	``yopmail.com``); no implicit default — callers must provide one.
	"""
	import re as _re

	def _slug(s: str) -> str:
		s = (s or "").strip().lower()
		s = _re.sub(r"[^a-z0-9]+", "", s)
		return s

	fn, ln = _slug(first), _slug(last)
	local = ".".join([p for p in (fn, ln) if p]) or "user"
	return f"{local}@{(domain or '').strip()}"


# Default email domain used to synthesise a Frappe-acceptable User.name
# when the operator opted into phone-as-username AND a row has no real
# email. Frappe's User.autoname hardcodes ``name = email`` and User.email
# has ``options: "Email"`` format validation (user.py:198 + user.json), so
# a User document literally cannot exist without an email-shaped PK. The
# end user never types this — they log in with their phone via Frappe's
# allow_login_using_mobile_number setting. The operator can override the
# domain in the wizard's Step 9 form.
DEFAULT_PHONE_EMAIL_DOMAIN = "yopmail.com"


def _phone_digits(raw: str) -> str:
	"""Strip everything except digits from a phone string.

	Source XLSX cells are messy: leading apostrophes (Excel's text-coercion
	artifact), spaces, dashes, parentheses, ``+`` prefixes. Returns the
	bare digit string. No country-code prepending — we store the operator's
	source format and use the digits as both ``username`` and ``mobile_no``.
	"""
	if not raw:
		return ""
	return re.sub(r"\D+", "", str(raw))


def _synthesize_phone_email(phone: str, domain: str) -> str:
	"""Build ``<phone-digits>@<domain>`` for rows missing emails in
	phone-as-username mode.

	Used instead of ``_synthesize_email`` (firstname.lastname) when the
	operator opted into phone-as-username: keying the placeholder PK on
	the unique phone digits avoids collisions between users who share a
	first/last-name pair, and lines up the email local-part with the
	username so operators can correlate them at a glance.

	Empty / digit-less phone → ``""`` (caller skips the row); empty
	domain → ``""`` too (caller must supply one — defaults to
	``yopmail.com`` at the wizard/RPC boundary).
	"""
	digits = _phone_digits(phone)
	dom = (domain or "").strip()
	if not digits or not dom:
		return ""
	return f"{digits}@{dom}"


def _duty_roles_for_project_role(project_role: str) -> list[str]:
	"""Return the Frappe Role names mapped to the given GRM Project Role's duties.

	Duty rows live on ``GRM Project Role.duties`` (Link to ``Duty``); the
	corresponding Frappe Role follows the convention ``"GRM <duty>"`` (mirrors
	``_frappe_role_for_duty`` in the assignment doctype). Only roles that
	actually exist in ``tabRole`` are returned — silently skipping any that
	haven't been created yet keeps user-creation forgiving when a project's
	duty taxonomy outpaces its role provisioning.
	"""
	if not project_role or not frappe.db.exists("GRM Project Role", project_role):
		return []
	duties = frappe.get_all(
		"GRM Project Role Duty",
		filters={"parent": project_role},
		pluck="duty",
	)
	out: list[str] = []
	for duty in duties:
		target = f"GRM {duty}"
		if frappe.db.exists("Role", target):
			out.append(target)
	return out


def _ensure_user(
	email: str,
	first_name: str,
	last_name: str,
	gender: str = "",
	phone: str = "",
	project_role: str = "",
	phone_as_username: bool = False,
	mobile_no: str = "",
	language: str = "",
) -> tuple[str, bool]:
	"""Find-or-create a Frappe User keyed by email; return ``(name, created)``.

	Frappe Users are auto-named to their email, so ``frappe.db.exists`` on the
	email gives O(1) presence detection. New users are inserted with welcome
	emails muted (this is a bulk import path) and ``send_welcome_email=0`` so
	the wizard does not flood inboxes during a 24-row test run.

	``project_role`` (when supplied) is the resolved ``GRM Project Role.name``
	for the assignment that needs this user. We map its duties to the
	convention-named Frappe Roles (``GRM <duty>``) and seed the User's
	``roles`` child table at insert time so Frappe's ``before_insert`` hook
	does not raise the "No Roles Specified" msgprint. As a baseline (e.g.
	when no duties resolve), we always grant ``Desk User`` so the warning
	never fires and the user can authenticate against the desk.

	When ``phone_as_username`` is True, we additionally stamp the User's
	``username`` and ``mobile_no`` with the digit-only phone so the end
	user can authenticate with their raw phone number (Frappe System
	Settings: ``allow_login_using_mobile_number`` /
	``allow_login_using_user_name``). The ``email`` argument may be empty
	in this mode — the caller already synthesised ``<phone>@phone.local``.
	"""
	email = (email or "").strip().lower()
	if not email:
		raise frappe.ValidationError("Email is required to create a User")
	if frappe.db.exists("User", email):
		return email, False
	# Gender is a Link to Gender doctype. Normalize ALLCAPS source values
	# ("FEMALE") to title case ("Female") and silently drop unknown values
	# rather than failing the whole row — gender is non-essential metadata
	# and the rest of the user record (email/name/phone) is what we care
	# about for the wizard's bulk import.
	gender_norm = (gender or "").strip()
	if gender_norm:
		gender_norm = gender_norm.title()
		if not frappe.db.exists("Gender", gender_norm):
			gender_norm = ""

	duty_roles = _duty_roles_for_project_role(project_role)
	# Always seed at least one role so Frappe's "No Roles Specified" warning
	# does not block the import. ``Desk User`` is the standard zero-permission
	# baseline; duty roles below add the actual GRM access the user needs.
	role_set: list[str] = []
	if frappe.db.exists("Role", "Desk User"):
		role_set.append("Desk User")
	for role in duty_roles:
		if role not in role_set:
			role_set.append(role)

	# Phone-as-username: surface the digit-canonical form on both
	# ``username`` and ``mobile_no``. Frappe's auth find_by_credentials
	# (frappe/core/doctype/user/user.py:852) does an equality match against
	# those fields when ``allow_login_using_mobile_number`` /
	# ``allow_login_using_user_name`` are enabled in System Settings.
	phone_clean = (phone or "").strip()
	mobile_clean = (mobile_no or phone or "").strip()
	phone_digits = _phone_digits(mobile_clean) if phone_as_username else ""

	# Default language: stamp the project's default_language onto the
	# User row so that new operators see the desk in the project's
	# configured language on first login. ``language`` is the resolved
	# code (e.g. "rw", "fr", "en"); blank means "leave Frappe's default".
	lang_value = (language or "").strip()
	if lang_value and not frappe.db.exists("Language", lang_value):
		lang_value = ""  # silently ignore an unknown language code

	user_doc: dict[str, Any] = {
		"doctype": "User",
		"email": email,
		"first_name": (first_name or "").strip() or email.split("@", 1)[0],
		"last_name": (last_name or "").strip(),
		"gender": gender_norm or None,
		"phone": phone_clean,
		"language": lang_value or None,
		"send_welcome_email": 0,
		"user_type": "System User",
		"enabled": 1,
		"roles": [{"role": r} for r in role_set],
	}
	if phone_as_username and phone_digits:
		user_doc["username"] = phone_digits
		user_doc["mobile_no"] = phone_digits
	elif mobile_clean:
		# Even outside phone-as-username, persist mobile_no when the source
		# mapped a Phone column so the column is not silently dropped.
		user_doc["mobile_no"] = _phone_digits(mobile_clean) or mobile_clean

	doc = frappe.get_doc(user_doc)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name, True


def _region_breadcrumb(region_id: str, cache: dict[str, str]) -> str:
	"""Return ``"Country / Province / District / ..."`` for a region.

	Walks ``parent_region`` recursively until the root. Memoizes via the
	caller-supplied ``cache`` so a deeply-nested hierarchy costs O(depth)
	queries the first time, O(1) thereafter.
	"""
	if not region_id:
		return ""
	if region_id in cache:
		return cache[region_id]

	chain: list[str] = []
	current: str | None = region_id
	seen: set[str] = set()  # cycle guard, just in case
	while current and current not in seen:
		seen.add(current)
		if current in cache:
			chain.insert(0, cache[current])
			current = None
			break
		row = frappe.db.get_value(
			"GRM Administrative Region",
			current,
			["region_name", "parent_region"],
			as_dict=True,
		)
		if not row:
			break
		chain.insert(0, row.region_name or current)
		current = row.parent_region

	label = " / ".join(chain) if chain else region_id
	cache[region_id] = label
	return label


# ---------------------------------------------------------------------------
# A.1 — resolve_region
# ---------------------------------------------------------------------------


def resolve_region(
	row: dict,
	level_columns_ordered: list[tuple[str, str]],
	project: str,
	auto_create: bool = True,
	level_lookup: dict[str, str] | None = None,
) -> tuple[str | None, list[tuple[str, str, str]]]:
	"""Resolve a list of admin-level cells into a single region id.

	Args:
	    row: Original row dict (kept for API symmetry — not currently used,
	        but downstream callers may want it for richer error messages).
	    level_columns_ordered: ``[(level_type_name, source_value), ...]``
	        ordered highest level first (Province → District → Sector …).
	        ``level_type_name`` is the ``level_name`` of a
	        ``GRM Administrative Level Type`` row scoped to ``project``.
	    project: ``GRM Project.name``.
	    auto_create: When ``True``, missing regions are inserted; when
	        ``False``, a missing region raises ``frappe.ValidationError``.
	    level_lookup: Optional pre-built ``{level_name: level_doc_name}``
	        cache (one ``GRM Administrative Level Type`` row per entry).
	        When provided, avoids a per-row × per-level DB roundtrip.
	        When ``None``, falls back to per-row ``frappe.db.get_value``
	        so direct callers don't need to know about the cache.

	Returns:
	    ``(administrative_region_id, created)`` where ``created`` is the
	    list of ``(level_type, value, new_region_id)`` tuples for any
	    regions inserted along the way. Empty cells are skipped — region
	    resolution stops at the last non-empty level (partial paths are
	    legal).
	"""
	del row  # currently unused; kept for forward compatibility.

	parent: str | None = None
	created: list[tuple[str, str, str]] = []

	for level_type, raw_value in level_columns_ordered:
		value = (raw_value or "").strip()
		if not value:
			# Empty cell ends resolution at the deepest non-empty ancestor.
			continue

		if level_lookup is not None:
			level_doc_name = level_lookup.get(level_type)
		else:
			level_doc_name = frappe.db.get_value(
				"GRM Administrative Level Type",
				{"project": project, "level_name": level_type},
				"name",
			)
		if not level_doc_name:
			# Level *types* are pre-seeded by Step 2; their absence is
			# always fatal — ``auto_create`` only governs region rows,
			# not level-type rows.
			raise frappe.ValidationError(
				f"Administrative level type not found: {level_type} (project={project}). "
				f"Run Step 2 first or seed the level type."
			)

		existing = frappe.db.exists(
			"GRM Administrative Region",
			{
				"project": project,
				"administrative_level": level_doc_name,
				"region_name": value,
				"parent_region": parent,
			},
		)
		if existing:
			parent = existing
			continue

		if not auto_create:
			raise frappe.ValidationError(f"Region not found: {level_type}={value} (project={project})")

		new_doc = frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"project": project,
				"administrative_level": level_doc_name,
				"region_name": value,
				"parent_region": parent,
			}
		).insert(ignore_permissions=False)
		created.append((level_type, value, new_doc.name))
		parent = new_doc.name

	return parent, created


# ---------------------------------------------------------------------------
# A.1 — auto_detect_mapping
# ---------------------------------------------------------------------------


def _normalize(label: str) -> str:
	"""Lower, strip whitespace/underscores/non-alnum — for fuzzy matching."""
	return re.sub(r"[^a-z0-9]+", "", (label or "").lower())


def _user_field_lookup() -> dict[str, str]:
	"""Map normalized User-doctype label/fieldname -> ``User.<fieldname>``.

	Excludes ``full_name`` — Frappe computes it from ``first_name`` +
	``last_name`` at save time, so importing into it is a no-op. We also
	exclude it so a header literally named "Full Name" falls through to
	the name-split heuristic (which flags it for user confirmation).
	"""
	out: dict[str, str] = {}
	for f in frappe.get_meta("User").fields:
		if not f.fieldname or f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
			continue
		if f.fieldname == "full_name":
			continue
		out[_normalize(f.fieldname)] = f"User.{f.fieldname}"
		if f.label:
			out[_normalize(f.label)] = f"User.{f.fieldname}"
	return out


def _assignment_field_lookup() -> dict[str, str]:
	"""Map normalized Assignment-doctype label/fieldname -> ``Assignment.<fieldname>``.

	Excludes the ``administrative_region`` field — that target is reached
	via the dedicated TARGET_REGION sentinel (because it requires a
	sub-picker for *which* level type the source column represents).
	"""
	out: dict[str, str] = {}
	for f in frappe.get_meta("GRM User Project Assignment").fields:
		if not f.fieldname or f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
			continue
		if f.fieldname == "administrative_region":
			continue
		out[_normalize(f.fieldname)] = f"Assignment.{f.fieldname}"
		if f.label:
			out[_normalize(f.label)] = f"Assignment.{f.fieldname}"
	return out


def _project_level_lookup(project_meta: dict) -> dict[str, str]:
	"""Map normalized level-type name -> raw level-type name (for region sub-picker)."""
	out: dict[str, str] = {}
	for lvl in project_meta.get("project_levels") or []:
		name = (lvl.get("level_name") or "").strip()
		if not name:
			continue
		out[_normalize(name)] = name
	return out


def auto_detect_mapping(headers: list[str], project_meta: dict) -> dict:
	"""Best-effort mapping ``{source_header: {target, level_type, ...}}``.

	Heuristic (matches plan §"Auto-detect heuristic" lines 111-115 in
	``docs/superpowers/plans/2026-05-10-step9-users-redesign.md`` — that
	plan is the authoritative order):

	1. Header fuzzy match against ``User``-doctype field labels/fieldnames,
	   then against ``GRM User Project Assignment`` field labels/fieldnames
	   (case-insensitive, strip spaces/underscores).
	2. For unmatched columns, fuzzy match against
	   ``GRM Administrative Level Type.level_name`` rows for the project —
	   if matched, propose ``administrative_region`` + that level.
	3. Headers containing "name" → ``User.first_name`` / ``User.last_name``
	   (split-needed when the header is just "name" or "full name" — we
	   attach ``needs_split: True`` + a ``warning`` string so the UI can
	   render a confirm-or-split prompt; user confirms in Phase E).

	Rationale for doctype-first ordering: plan order. The current
	User/Assignment doctypes have no field whose label matches a common
	admin-level name ("Province", "District", "Sector", "County", "Cell"),
	so today there is no collision. If a future project ever defines a
	level type whose name shadows a real doctype field label, the user
	can override the auto-detected target in the mapper UI.

	Unrecognized headers get ``target == TARGET_SKIP``.
	"""
	user_fields = _user_field_lookup()
	asgn_fields = _assignment_field_lookup()
	level_lookup = _project_level_lookup(project_meta)

	mapping: dict[str, dict[str, Any]] = {}
	for header in headers:
		norm = _normalize(header)
		if not norm:
			mapping[header] = {"target": TARGET_SKIP, "level_type": None}
			continue

		# 1a. User field match (prefer User.email / User.first_name etc.)
		if norm in user_fields:
			mapping[header] = {"target": user_fields[norm], "level_type": None}
			continue

		# 1b. Assignment field match
		if norm in asgn_fields:
			mapping[header] = {"target": asgn_fields[norm], "level_type": None}
			continue

		# 2. Admin-level match for unmatched columns
		if norm in level_lookup:
			mapping[header] = {"target": TARGET_REGION, "level_type": level_lookup[norm]}
			continue

		# 3. "name"-bearing header heuristic. If the header is just "name"
		# or "full name", we can't tell first vs last — flag for the UI.
		if norm in {"fullname", "name"}:
			mapping[header] = {
				"target": "User.first_name",
				"level_type": None,
				"needs_split": True,
				"warning": (
					"May contain full name — confirm this maps to first name only, "
					"or split into two columns"
				),
			}
			continue
		if "first" in norm and "name" in norm:
			mapping[header] = {"target": "User.first_name", "level_type": None}
			continue
		if "last" in norm and "name" in norm:
			mapping[header] = {"target": "User.last_name", "level_type": None}
			continue

		mapping[header] = {"target": TARGET_SKIP, "level_type": None}

	return mapping


# ---------------------------------------------------------------------------
# A.1 — validate_mapping
# ---------------------------------------------------------------------------


def _required_targets(phone_as_username: bool = False) -> list[tuple[str, str]]:
	"""Return ``[(target_token, label), ...]`` for every must-have field.

	Required = the wizard's User minima (email/first_name/last_name) plus
	every ``GRM User Project Assignment`` field with ``reqd: 1`` *except*
	fields the operator cannot map: ``project`` (wizard supplies it),
	``administrative_region`` (handled via the TARGET_REGION sentinel + level
	sub-picker), and ``user`` (auto-derived from ``User.email`` at import time).

	When ``phone_as_username`` is True, ``User.email`` is dropped from the
	required set: the service layer synthesises ``<phone-digits>@<domain>``
	for missing-email rows, so the operator does not need to map an Email
	column — but they MUST map a Phone-bearing column (mobile_no/phone), so
	we add that to the required set in its place.
	"""
	required: list[tuple[str, str]] = []
	user_meta = frappe.get_meta("User")
	user_meta_by_name = {f.fieldname: f for f in user_meta.fields}
	user_required = ("first_name", "last_name") if phone_as_username else ("email", "first_name", "last_name")
	for fname in user_required:
		f = user_meta_by_name.get(fname)
		label = (f.label if f else fname) or fname
		required.append((f"User.{fname}", label))
	if phone_as_username:
		# Either mobile_no or phone satisfies the requirement; we record
		# both targets and check disjunctively in validate_mapping.
		required.append(("User.mobile_no|User.phone", "Phone (Mobile No or Phone)"))

	non_mappable_assignment = {"project", "administrative_region", "user"}
	for f in frappe.get_meta("GRM User Project Assignment").fields:
		if not getattr(f, "reqd", 0):
			continue
		if f.fieldname in non_mappable_assignment:
			continue
		label = f.label or f.fieldname
		required.append((f"Assignment.{f.fieldname}", label))
	return required


def validate_mapping(mapping: dict, project_meta: dict, phone_as_username: bool = False) -> dict:
	"""Check that every required target is mapped exactly once.

	``phone_as_username``: when True, ``User.email`` is dropped from the
	required set and a "Phone (Mobile No or Phone)" disjunctive requirement
	is added — the operator must map either a ``User.mobile_no`` or
	``User.phone`` column, satisfying the requirement when at least one is
	present.

	Returns:
	    ``{"ok": bool, "missing_required": [label, ...],
	        "errors": [str, ...], "warnings": [str, ...]}``
	"""
	del project_meta  # required-set is doctype-driven, not project-meta-driven

	required = _required_targets(phone_as_username=phone_as_username)
	targets_in_use: list[tuple[str, str | None]] = []
	level_type_use: dict[str, list[str]] = {}

	for header, m in (mapping or {}).items():
		target = m.get("target")
		if not target or target == TARGET_SKIP:
			continue
		level_type = m.get("level_type")
		targets_in_use.append((target, level_type))
		if target == TARGET_REGION:
			if not level_type:
				# Caller surfaces this in `errors` so the UI can highlight
				# the offending row in the mapper table.
				continue
			level_type_use.setdefault(level_type, []).append(header)

	target_token_set = {t for t, _ in targets_in_use}

	missing_labels: list[str] = []
	for token, label in required:
		if token == TARGET_REGION:
			continue  # region is optional at the doctype level
		# Disjunctive requirement (``a|b``) — satisfied when ANY listed
		# target is mapped. Used for the phone-as-username flow where
		# either ``User.mobile_no`` or ``User.phone`` counts.
		if "|" in token:
			if not any(t in target_token_set for t in token.split("|")):
				missing_labels.append(label)
			continue
		if token not in target_token_set:
			missing_labels.append(label)

	errors: list[str] = []
	warnings: list[str] = []

	# Multiple admin-level columns: enforce 'at most one column per level type'.
	for level_type, headers_using in level_type_use.items():
		if len(headers_using) > 1:
			errors.append(
				f"Multiple source columns mapped to admin level '{level_type}': "
				f"{', '.join(headers_using)}. Pick exactly one."
			)

	# Region target with no level_type sub-pick.
	for header, m in (mapping or {}).items():
		if m.get("target") == TARGET_REGION and not m.get("level_type"):
			errors.append(
				f"Column '{header}' is mapped to administrative_region but has no level type selected."
			)

	# Duplicate non-region target → warning (doctype will reject silently otherwise).
	seen_non_region: dict[str, str] = {}
	for header, m in (mapping or {}).items():
		target = m.get("target")
		if not target or target == TARGET_SKIP or target == TARGET_REGION:
			continue
		if target in seen_non_region:
			warnings.append(
				f"Both '{seen_non_region[target]}' and '{header}' map to {target}; "
				f"the second column will overwrite the first."
			)
		else:
			seen_non_region[target] = header

	ok = not missing_labels and not errors
	return {
		"ok": ok,
		"missing_required": missing_labels,
		"errors": errors,
		"warnings": warnings,
	}


# ---------------------------------------------------------------------------
# A.1 — materialize_staged_csv
# ---------------------------------------------------------------------------


def _staged_dir() -> str:
	"""Return the on-disk directory for staged user-import CSVs.

	Frappe's Data Import expects an attached file under ``private/files``
	(so it is reachable via ``/private/files/...``). We bucket all wizard
	user-imports into a single subdirectory for tidy lifecycle hooks.
	"""
	base = frappe.get_site_path("private", "files", "grm_user_import")
	os.makedirs(base, exist_ok=True)
	return base


def _ordered_level_columns(mapping: dict) -> list[tuple[str, str]]:
	"""Return ``[(level_type, source_header), ...]`` in source-column order.

	Source-column order implies hierarchy (left-to-right = highest-to-lowest)
	per plan line 116. The mapper UI lets the user re-order; this function
	just trusts whatever order the dict was given in (Python 3.7+ preserves
	insertion order).
	"""
	ordered: list[tuple[str, str]] = []
	for header, m in mapping.items():
		if m.get("target") == TARGET_REGION and m.get("level_type"):
			ordered.append((m["level_type"], header))
	return ordered


def materialize_staged_csv(
	rows: list[list[str]],
	headers: list[str],
	mapping: dict,
	project: str,
	auto_create_regions: bool = True,
	synthesize_emails: bool = False,
	synthesize_email_domain: str = "",
	phone_as_username: bool = False,
) -> dict:
	"""Apply mapping + region resolution to every row, write a staged CSV.

	Output CSV has one column per *resolved target field* — i.e. the
	``User.<x>`` and ``Assignment.<x>`` targets become bare ``<x>``
	columns suitable for Frappe's Data Import (which expects fieldnames
	or labels, not our ``Doctype.<fieldname>`` form). The single
	``administrative_region`` column holds the resolved region id.

	Returns a structured dict with the staged path, counts, the list of
	regions that were (or would be) created, warnings, errors, and a
	preview of the first ``PREVIEW_LIMIT`` resolved-row dicts.
	"""
	# Review fix B12: cap CSV rows at 10k. Beyond this the importer's
	# per-row region resolution, user upsert, and assignment insert
	# combine into a request that can blow request memory and lock
	# tables for minutes. Larger imports should go through the bench
	# CLI path which streams + chunks.
	_MAX_ROWS = 10_000
	if len(rows) > _MAX_ROWS:
		frappe.throw(
			f"CSV has {len(rows):,} rows; the in-request importer is capped at "
			f"{_MAX_ROWS:,}. Split the file or run the bench CLI importer."
		)

	# Project's default_language is stamped on every freshly-created User
	# so operators see the desk in the project's language on first login.
	# An empty value leaves Frappe's own default in place.
	project_default_language = frappe.db.get_value("GRM Project", project, "default_language") or ""

	header_index = {h: i for i, h in enumerate(headers)}
	level_columns = _ordered_level_columns(mapping)

	# Build the output column list. Order: User fields (alpha), Assignment
	# fields (alpha), then administrative_region last (if any region cols).
	user_targets: list[str] = []
	asgn_targets: list[str] = []
	for _h, m in mapping.items():
		target = m.get("target")
		if not target or target == TARGET_SKIP or target == TARGET_REGION:
			continue
		if target.startswith("User."):
			fname = target.split(".", 1)[1]
			if fname not in user_targets:
				user_targets.append(fname)
		elif target.startswith("Assignment."):
			fname = target.split(".", 1)[1]
			if fname not in asgn_targets:
				asgn_targets.append(fname)

	# The staged CSV imports into ``GRM User Project Assignment`` ONLY —
	# User records are created up-front per row, before the row is written,
	# and the resulting User name (== email) is what we persist on the
	# Assignment via the ``user`` link field. This avoids the chicken-and-egg
	# problem where Frappe Data Import would try to insert an Assignment
	# whose ``user`` doesn't yet exist (and whose ``before_insert`` hook
	# tries to read ``User.email`` to mint an activation code).
	out_headers = ["user", *list(asgn_targets)]
	if level_columns:
		out_headers.append("administrative_region")
	# The Assignment doctype requires `project`, but `_required_targets`
	# excludes it from the user-facing mapping (the wizard supplies the
	# project context out-of-band). Frappe Data Import has no out-of-band
	# mechanism, so we inject the project value into every row of the
	# staged CSV here.
	out_headers.append("project")

	# ------------------------------------------------------------------
	# Caches built ONCE per call (vs per-row × per-target previously).
	# ------------------------------------------------------------------
	# 1) Level-key → level-doc-name. Saves N_rows × N_levels DB lookups.
	#    The wizard's mapper UI uses the level-type ``name`` (autoname like
	#    ``131j7c1dkn``) as its <option value>, while CLI/API callers may
	#    pass the human-readable ``level_name`` (e.g. ``"Province"``). Accept
	#    both so the same `level_lookup` works for either wire format.
	level_lookup: dict[str, str] = {}
	level_label_by_id: dict[str, str] = {}
	for row in frappe.get_all(
		"GRM Administrative Level Type",
		filters={"project": project},
		fields=["name", "level_name"],
	):
		level_lookup[row.name] = row.name
		if row.level_name:
			level_lookup[row.level_name] = row.name
		level_label_by_id[row.name] = row.level_name or row.name
	# Region breadcrumb cache: region_id -> "Province / District / Sector".
	# Populated lazily by ``_region_breadcrumb`` as preview rows are built;
	# walking parent_region in SQL each call is fine because PREVIEW_LIMIT
	# caps the worst case at 50 rows.
	region_breadcrumb_cache: dict[str, str] = {}
	# Role label → role `name` (random hash). The Assignment.role link points
	# at GRM Project Role.name; the operator's CSV carries the human label
	# (`role_name`). Build a case-/whitespace-insensitive lookup scoped to
	# the project so we can rewrite cells before handing the staged CSV to
	# Frappe Data Import. Track distinct unresolved labels so the wizard
	# can tell the operator exactly which roles need to be created in Step 8.
	role_lookup: dict[str, str] = {}
	role_label_by_name: dict[str, str] = {}
	for row in frappe.get_all(
		"GRM Project Role",
		filters={"project": project},
		fields=["name", "role_name"],
	):
		role_lookup[_normalize_label(row.name)] = row.name
		role_label_by_name[row.name] = row.role_name or row.name
		if row.role_name:
			role_lookup[_normalize_label(row.role_name)] = row.name
	missing_roles: dict[str, str] = {}  # lower → original label as seen first
	# 2) Target token → source header. ``_find_source_for`` semantics:
	#    on duplicate mappings the *last* declared header wins; replicate
	#    by overwriting on iteration. Region target is many-to-one
	#    (per-level-type), so it is handled separately via ``level_columns``
	#    and intentionally excluded here.
	target_to_source: dict[str, str] = {}
	for header, m in mapping.items():
		target = m.get("target")
		if not target or target == TARGET_SKIP or target == TARGET_REGION:
			continue
		target_to_source[target] = header

	preview: list[dict[str, Any]] = []
	rows_ready = 0
	rows_skipped = 0
	warnings: list[str] = []
	errors: list[str] = []
	regions_created_global: list[tuple[str, str, str]] = []
	regions_to_create_dryrun: set[tuple[str, str]] = set()

	# Review fix B8: use frappe.generate_hash so concurrent imports for
	# the same project in the same second can't collide on the staged
	# filename (the previous ``int(time.time())`` suffix has 1-second
	# granularity and is fully predictable, so two parallel CSV jobs
	# could overwrite each other's staged file).
	out_path = os.path.join(_staged_dir(), f"users_{project}_{frappe.generate_hash(length=8)}.csv")
	with open(out_path, "w", encoding="utf-8", newline="") as fh:
		writer = csv.writer(fh)
		writer.writerow(out_headers)

		for row_num, raw_row in enumerate(rows, start=2):
			row_dict = {
				h: (raw_row[header_index[h]] if header_index[h] < len(raw_row) else "")
				for h in headers
				if h in header_index
			}

			level_cells: list[tuple[str, str]] = []
			for level_type, src_header in level_columns:
				level_cells.append((level_type, (row_dict.get(src_header) or "").strip()))

			try:
				region_id = None
				if level_cells and any(v for _, v in level_cells):
					if auto_create_regions:
						region_id, created_here = resolve_region(
							row_dict,
							level_cells,
							project,
							auto_create=True,
							level_lookup=level_lookup,
						)
						regions_created_global.extend(created_here)
					else:
						# Dry-run: don't write, but compute what *would* be needed.
						region_id = _resolve_region_dryrun(
							level_cells,
							project,
							regions_to_create_dryrun,
							level_lookup=level_lookup,
						)
			except frappe.ValidationError as exc:
				errors.append(f"Row {row_num}: {exc}")
				rows_skipped += 1
				continue

			# Locked dry-run contract: if auto_create_regions=False AND the
			# row had non-empty admin-level cells but resolved to no region,
			# do NOT write a NULL-region row to the staged CSV (Frappe Data
			# Import would otherwise silently insert assignments with
			# administrative_region=NULL). Skip the row, record the first
			# missing level for the error message.
			if (
				not auto_create_regions
				and level_cells
				and any(v for _, v in level_cells)
				and region_id is None
			):
				first_missing_level, first_missing_value = next((lt, v) for lt, v in level_cells if v)
				errors.append(
					f"Row {row_num}: region {first_missing_level}={first_missing_value!r} "
					f"does not exist (auto_create=False)"
				)
				rows_skipped += 1
				continue

			resolved: dict[str, Any] = {}

			user_payload: dict[str, str] = {}
			for fname in user_targets:
				src_header = target_to_source.get(f"User.{fname}")
				raw = row_dict.get(src_header) if src_header else ""
				user_payload[fname] = _clean_cell(raw)
				resolved[fname] = user_payload[fname]

			# Email is required on the User doctype (Frappe autonames by
			# email — user.py:198 — and the field has email-format
			# validation). When the source cell is blank or carries an
			# Excel formula error (#NAME?, #REF!, …) we have three paths:
			#
			#   - phone_as_username=True (the new RDAP default):
			#     synthesise ``<phone-digits>@<domain>``. Domain defaults
			#     to ``yopmail.com`` if the operator left it blank — the
			#     end user never sees it; they log in with their raw
			#     phone via System Settings.allow_login_using_mobile_number.
			#     Keying on phone digits avoids collisions between users
			#     who share a first/last-name pair.
			#   - synthesize_emails=True (legacy name-based path):
			#     build ``firstname.lastname@<domain>``.
			#   - neither: error + skip so the operator sees what's broken.
			#
			# phone_as_username takes precedence — when it's on, we always
			# use phone-keyed synthesis even if the legacy flag is also on.
			if not user_payload.get("email"):
				phone_for_synth = user_payload.get("mobile_no") or user_payload.get("phone") or ""
				if phone_as_username:
					if not _phone_digits(phone_for_synth):
						errors.append(
							f"Row {row_num}: phone is missing or unreadable "
							f"(phone-as-username mode requires a usable phone "
							f"number — source cell empty or non-digit)."
						)
						rows_skipped += 1
						continue
					domain = (synthesize_email_domain or "").strip() or DEFAULT_PHONE_EMAIL_DOMAIN
					synthetic = _synthesize_phone_email(phone_for_synth, domain)
					user_payload["email"] = synthetic
					resolved["email"] = synthetic
				elif synthesize_emails:
					synthetic = _synthesize_email(
						user_payload.get("first_name", ""),
						user_payload.get("last_name", ""),
						synthesize_email_domain,
					)
					user_payload["email"] = synthetic
					resolved["email"] = synthetic
				else:
					errors.append(
						f"Row {row_num}: email is missing or unreadable "
						f"(source cell empty or contains an Excel formula error)."
					)
					rows_skipped += 1
					continue

			# Resolve assignment fields (incl. role label → role name lookup)
			# in a transient dict — only after BOTH role resolution and User
			# creation succeed do we write to the staged CSV.
			asgn_resolved: dict[str, str] = {}
			row_role_missing = False
			for fname in asgn_targets:
				src_header = target_to_source.get(f"Assignment.{fname}")
				raw = row_dict.get(src_header) if src_header else ""
				val = _clean_cell(raw)
				if fname == "role" and val:
					key = _normalize_label(val)
					resolved_name = role_lookup.get(key)
					if resolved_name:
						asgn_resolved[fname] = resolved_name
						resolved[fname] = val
						continue
					if key not in missing_roles:
						missing_roles[key] = val
					row_role_missing = True
					asgn_resolved[fname] = val
					resolved[fname] = val
					continue
				asgn_resolved[fname] = val
				resolved[fname] = val
			if row_role_missing:
				errors.append(
					f"Row {row_num}: role does not exist in this project " f"(create it in Step 8 first)."
				)
				rows_skipped += 1
				continue

			# Find-or-create the User. Failures here are logged per-row so
			# the operator sees exactly which rows had bad user data; the
			# whole import does not abort. Pass the resolved project-role
			# name so ``_ensure_user`` can seed the matching Frappe duty
			# roles at insert time (suppresses Frappe's "No Roles Specified"
			# warning and gives the user immediate access on first login).
			try:
				user_name, _was_created = _ensure_user(
					email=user_payload.get("email", ""),
					first_name=user_payload.get("first_name", ""),
					last_name=user_payload.get("last_name", ""),
					gender=user_payload.get("gender", ""),
					phone=user_payload.get("phone", ""),
					project_role=asgn_resolved.get("role", ""),
					phone_as_username=phone_as_username,
					mobile_no=user_payload.get("mobile_no", ""),
					language=project_default_language,
				)
			except Exception as exc:
				errors.append(f"Row {row_num}: could not create User: {exc}")
				rows_skipped += 1
				continue

			# Now write the Assignment-only row: user + assignment fields
			# + administrative_region + project.
			out_row: list[str] = [user_name]
			for fname in asgn_targets:
				out_row.append(asgn_resolved.get(fname, ""))
			if level_columns:
				out_row.append(region_id or "")
				# Preview surfaces the human-readable breadcrumb (e.g.
				# ``Kigali city / Gasabo / Kacyiru``) so reviewers can
				# eyeball-verify the resolution; the staged CSV keeps the
				# opaque region_id (Frappe Data Import needs the link key).
				resolved["administrative_region"] = (
					_region_breadcrumb(region_id, region_breadcrumb_cache) if region_id else ""
				)
			out_row.append(project)
			resolved["project"] = project
			resolved["user"] = user_name

			writer.writerow(out_row)
			rows_ready += 1
			if len(preview) < PREVIEW_LIMIT:
				preview.append(resolved)

	# Normalize level_type to human-readable form for display. The dry-run
	# accumulator and `regions_created_global` may contain either autonames
	# (when the wizard sends doctype `name`) or human labels (CLI/API
	# callers); always surface the human label to the UI.
	def _label(lt: str) -> str:
		return level_label_by_id.get(lt, lt)

	regions_to_create = (
		[(_label(lt), val, new_id) for lt, val, new_id in regions_created_global]
		if auto_create_regions
		else [(_label(lt), val) for lt, val in sorted(regions_to_create_dryrun)]
	)

	return {
		"staged_path": out_path,
		"rows_total": len(rows),
		"rows_ready": rows_ready,
		"rows_skipped": rows_skipped,
		"regions_to_create": regions_to_create,
		"missing_roles": sorted(missing_roles.values()),
		"warnings": warnings,
		"errors": errors,
		"preview": preview,
	}


def _resolve_region_dryrun(
	level_cells: list[tuple[str, str]],
	project: str,
	accumulator: set[tuple[str, str]],
	level_lookup: dict[str, str] | None = None,
) -> str | None:
	"""Walk the hierarchy without inserting; record any missing levels.

	Mirrors ``resolve_region`` but never writes. Records each missing
	``(level_type, value)`` pair into ``accumulator`` so the caller can
	surface them as the ``regions_to_create`` preview list.

	``level_lookup`` is the same optional cache as ``resolve_region``;
	callers building it once across many rows pass it here too.
	"""
	parent: str | None = None
	for level_type, raw_value in level_cells:
		value = (raw_value or "").strip()
		if not value:
			continue
		if level_lookup is not None:
			level_doc_name = level_lookup.get(level_type)
		else:
			level_doc_name = frappe.db.get_value(
				"GRM Administrative Level Type",
				{"project": project, "level_name": level_type},
				"name",
			)
		if not level_doc_name:
			accumulator.add((level_type, value))
			return None
		existing = frappe.db.exists(
			"GRM Administrative Region",
			{
				"project": project,
				"administrative_level": level_doc_name,
				"region_name": value,
				"parent_region": parent,
			},
		)
		if existing:
			parent = existing
			continue
		accumulator.add((level_type, value))
		# Once a level is missing, any deeper level can't be looked up; stop.
		return None
	return parent
