"""Project-scoped government-worker bulk-importer.

Single source of truth for government-worker ingestion. Both the CLI
commands (``create-government-workers``, ``auto-generate-regional-workers``,
``export-activation-codes``) and the wizard RPC endpoints
(``parse_users_csv`` / ``bulk_create_users`` / ``auto_generate_regional_users``
/ ``export_activation_codes`` / ``export_user_template``) call into this
module.

The wizard CSV shape is intentionally simpler than the CLI shape:

    first_name,last_name,position,region,phone[,email]

Where:
* ``region`` is a human-readable region NAME (resolved to an internal
  ``GRM Administrative Region.name`` via project scope).
* ``email`` is optional. When omitted, an email is synthesised from
  ``position.region@<DEFAULT_EMAIL_DOMAIN>``.

Heavy-lifting machinery (``_bulk_validate_and_prepare`` /
``_bulk_create_workers`` / SQL bulk-inserts / activation-code generation)
lives on :class:`OptimizedBulkWorkerCreator` and is shared by both
flows. Wizard rows are normalised to the internal ``worker_data`` shape
expected by the bulk machinery.
"""

import csv
import io
import logging
import re
import secrets
import string

import frappe
from frappe.utils import add_to_date, get_datetime

DEFAULT_EMAIL_DOMAIN = "example.gov.rw"
DEFAULT_DEPARTMENT = "General"
# Default Project Role name. The importer resolves this against
# `GRM Project Role` (per the duty-driven architecture in
# docs/superpowers/plans/2026-04-25-egrm-per-project-architecture-implementation.md),
# NOT against the legacy `Role` table. The CSV `position` column
# overrides this on a per-row basis.
DEFAULT_PROJECT_ROLE_NAME = "GRM Field Officer"
# Duties whose presence on a Project Role means the assignment requires
# activation (matches `GOVERNMENT_WORKER_DUTIES` in the assignment
# controller).
GOVERNMENT_WORKER_DUTIES = {"Intake", "Investigate & Resolve"}
WIZARD_REQUIRED_COLUMNS = ["first_name", "last_name", "position", "region", "phone"]
WIZARD_OPTIONAL_COLUMNS = ["email", "project_role"]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OptimizedBulkWorkerCreator
#
# Verbatim move from ``egrm/commands/create_government_workers.py`` with two
# corrections folded in:
#   1. ``self.frappe.log()`` / ``self.frappe.log_error()`` references — which
#      raised AttributeError because ``self.frappe`` was never assigned —
#      replaced with module-level ``frappe.log`` / ``frappe.log_error``.
#   2. Constructor accepts ``project=`` as a kwarg alias for ``project_code``
#      so the wizard public façade can pass ``project=...`` uniformly.
# ---------------------------------------------------------------------------


class OptimizedBulkWorkerCreator:
	"""High-performance bulk worker creator using Frappe Query Builder."""

	def __init__(
		self,
		project_code: str | None = None,
		email_domain: str = DEFAULT_EMAIL_DOMAIN,
		department: str = DEFAULT_DEPARTMENT,
		send_emails: bool = False,
		dry_run: bool = False,
		default_password: str | None = None,
		logger: logging.Logger | None = None,
		batch_size: int = 500,
		project: str | None = None,
	):
		# The wizard public façade passes ``project=...``; the CLI passes
		# ``project_code=...``. Accept either, prefer the explicit name.
		resolved = project_code or project
		if not resolved:
			raise ValueError("project_code (or project=) is required")
		self.project_code = resolved
		self.email_domain = email_domain or DEFAULT_EMAIL_DOMAIN
		self.department = department
		self.send_emails = send_emails
		self.dry_run = dry_run
		self.default_password = default_password
		self.batch_size = batch_size
		self.log = logger or log

		self.total_created = 0
		self.total_users = 0
		self.total_emails_sent = 0
		self.created_workers: list[dict] = []
		self.errors: list[str] = []
		self.skipped_users = 0
		self.skipped_assignments = 0
		self._role_duty_cache: dict[str, set[str]] = {}
		# `department` here is the human-facing display name (e.g. "General").
		# The assignment row stores `department` as a Link to GRM Issue
		# Department's `name` (a random hash, since the doctype autonames by
		# hash). Resolve display→name lazily so a stale "General" literal
		# cannot leak into the assignment row and trip Frappe's Link
		# validator on subsequent loads/saves.
		self._resolved_department_link: str | None = None

		# Snapshot prior flag values so they can be restored. Bulk paths
		# need ``in_import`` (suppress background jobs/emails) and
		# ``ignore_permissions`` (raw inserts). These MUST be reverted on
		# __exit__ / restore_flags() — leaving ``ignore_permissions=True``
		# in the request scope is a privilege-escalation risk.
		self._prior_flags = {
			"in_import": frappe.flags.get("in_import"),
			"ignore_permissions": frappe.flags.get("ignore_permissions"),
		}
		self._flags_restored = False
		frappe.flags.in_import = True
		frappe.flags.ignore_permissions = True

		try:
			self._validate_inputs()
		except Exception:
			self.restore_flags()
			raise

	# ------------------------------------------------------------------
	# Context-manager / explicit-restore protocol
	# ------------------------------------------------------------------
	def restore_flags(self) -> None:
		"""Restore the ``frappe.flags`` snapshot taken at construction."""
		if self._flags_restored:
			return
		for key, value in self._prior_flags.items():
			if value is None:
				# The flag did not exist in the prior scope; remove it.
				try:
					delattr(frappe.flags, key)
				except (AttributeError, KeyError):
					frappe.flags[key] = None
			else:
				frappe.flags[key] = value
		self._flags_restored = True

	def __enter__(self) -> "OptimizedBulkWorkerCreator":
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.restore_flags()

	# ------------------------------------------------------------------
	# Validation / setup
	# ------------------------------------------------------------------
	def _validate_inputs(self) -> None:
		try:
			project_exists = (
				frappe.qb.from_("GRM Project")
				.select("name")
				.where(frappe.qb.Field("name") == self.project_code)
				.run()
			)
			if not project_exists:
				raise ValueError(f"Project {self.project_code} does not exist")

			if not self.email_domain or "." not in self.email_domain:
				raise ValueError("Invalid email domain format")

			# Validate the duty catalog is seeded and at least one
			# Project Role exists for this project. Without these, the
			# CSV row → Project Role resolution and the duty-walking
			# `assign_role_to_user()` hook on assignment insert have
			# nothing to bind to.
			duty_count = frappe.qb.from_("GRM Duty").select("name").run()
			if not duty_count:
				raise ValueError(
					"GRM Duty catalog is empty — run "
					"`bench --site <site> migrate` to seed the 6 standard duties."
				)
			project_roles = (
				frappe.qb.from_("GRM Project Role")
				.select("name")
				.where(frappe.qb.Field("project") == self.project_code)
				.run()
			)
			if not project_roles:
				raise ValueError(
					f"No GRM Project Role rows for project {self.project_code} — "
					"create them via the wizard's User Types step (or call "
					"`project_role_seed_defaults`) before bulk-importing users."
				)
		except Exception as exc:
			frappe.log_error(f"Input validation failed: {exc}")
			raise

	# ------------------------------------------------------------------
	# Legacy file-path entry points (CLI compatibility)
	# ------------------------------------------------------------------
	def create_from_csv(self, csv_file_path: str) -> bool:
		"""CLI entry: parse + create from a CSV file on disk."""
		with open(csv_file_path, encoding="utf-8") as fh:
			return self._create_from_legacy_stream(fh)

	def generate_for_regions(
		self, level_filter: str | None = None, position_template: str = "{level}_officer"
	) -> dict:
		"""Auto-generate one Field Officer per region. CLI returns bool; the
		wizard public façade returns a dict report (counts + errors)."""
		try:
			regions_query = (
				frappe.qb.from_("GRM Administrative Region")
				.select("name", "region_name", "administrative_level", "parent_region")
				.where(frappe.qb.Field("project") == self.project_code)
			)
			if level_filter:
				regions_query = regions_query.where(frappe.qb.Field("administrative_level") == level_filter)
			regions = regions_query.orderby("administrative_level", "region_name").run(as_dict=True)
			if not regions:
				raise ValueError(f"No regions found for project {self.project_code}")

			worker_data_list = []
			for region in regions:
				worker_data_list.append(self._generate_worker_data_for_region(region, position_template))

			if self.dry_run:
				self._simulate_creation(worker_data_list)
				return self._report()

			validated = self._bulk_validate_and_prepare(worker_data_list)
			self._bulk_create_workers(validated)
			return self._report()
		except Exception as exc:
			self.errors.append(str(exc))
			frappe.log_error(f"Error generating workers for regions: {exc}")
			return self._report()

	# ------------------------------------------------------------------
	# Wizard text-mode entry points
	# ------------------------------------------------------------------
	def validate_csv_text(self, csv_text: str) -> dict:
		"""Validate a wizard CSV string (no DB writes). Returns a preview report."""
		rows, errors = self._parse_wizard_csv(csv_text)
		if not errors:
			errors = self._validate_wizard_rows(rows)
		return {
			"total_rows": len(rows),
			"errors": errors,
			"preview": rows[:50],
		}

	def create_from_csv_text(self, csv_text: str, default_password: str | None = None) -> dict:
		"""Insert workers from a wizard CSV string. Returns counts + activation codes."""
		if default_password is not None:
			self.default_password = default_password
		rows, errors = self._parse_wizard_csv(csv_text)
		if errors:
			return {"created": 0, "errors": errors, "activation_codes": []}

		worker_data_list, resolve_errors = self._wizard_rows_to_worker_data(rows)
		if resolve_errors:
			return {"created": 0, "errors": resolve_errors, "activation_codes": []}

		try:
			validated = self._bulk_validate_and_prepare(worker_data_list)
			self._bulk_create_workers(validated)
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			self.errors.append(str(exc))

		return {
			"created": self.total_users,
			"assignments": self.total_created,
			"errors": list(self.errors),
			"activation_codes": self._collect_activation_codes(),
		}

	def export_activation_codes_csv(self) -> str:
		"""Return CSV text of all activation codes for this project (no file I/O)."""
		rows = self._fetch_activation_codes()
		buf = io.StringIO()
		writer = csv.DictWriter(
			buf,
			fieldnames=[
				"email",
				"username",
				"activation_code",
				"status",
				"position",
				"region",
				"department",
				"expires_on",
				"activated_on",
				"code_sent_on",
			],
		)
		writer.writeheader()
		for r in rows:
			writer.writerow(
				{
					"email": r.get("email", "") or "",
					"username": r.get("username", "") or "",
					"activation_code": r.get("activation_code", "") or "",
					"status": r.get("activation_status", "") or "",
					"position": r.get("position_title", "") or "",
					"region": r.get("region_name", "") or "",
					"department": r.get("department", "") or "",
					"expires_on": r.get("activation_expires_on", "") or "",
					"activated_on": r.get("activated_on", "") or "",
					"code_sent_on": r.get("code_sent_on", "") or "",
				}
			)
		return buf.getvalue()

	# ------------------------------------------------------------------
	# Wizard CSV parsing / row resolution
	# ------------------------------------------------------------------
	def _parse_wizard_csv(self, csv_text: str) -> tuple[list[dict], list[str]]:
		errors: list[str] = []
		try:
			reader = csv.DictReader(io.StringIO(csv_text))
			headers = [h.strip() for h in (reader.fieldnames or [])]
		except Exception as exc:
			return [], [f"Cannot read CSV: {exc}"]

		missing = [h for h in WIZARD_REQUIRED_COLUMNS if h not in headers]
		if missing:
			return [], [f"CSV missing required columns: {', '.join(missing)}"]

		rows: list[dict] = []
		for row_num, raw in enumerate(reader, start=2):
			clean = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
			if not any(clean.get(c) for c in WIZARD_REQUIRED_COLUMNS):
				continue  # blank row
			clean["_row_num"] = row_num
			rows.append(clean)
		return rows, errors

	def _validate_wizard_rows(self, rows: list[dict]) -> list[str]:
		errors: list[str] = []
		for r in rows:
			for col in WIZARD_REQUIRED_COLUMNS:
				if not r.get(col):
					errors.append(f"Row {r.get('_row_num')}: missing required '{col}'")
					break
			email = r.get("email", "")
			if email and not self._is_valid_email(email):
				errors.append(f"Row {r.get('_row_num')}: invalid email '{email}'")
		return errors

	def _first_project_role_link(self) -> str | None:
		"""Last-ditch fallback for auto-generation when DEFAULT_PROJECT_ROLE_NAME
		isn't a Project Role for this project. Picks the alphabetically-first
		active Project Role so behaviour is deterministic across runs."""
		return frappe.db.get_value(
			"GRM Project Role",
			{"project": self.project_code, "is_active": 1},
			"name",
			order_by="role_name asc",
		)

	def _project_role_link(self, role_name: str) -> str | None:
		"""Resolve a free-text Project Role name to its `<project>-<role_name>`
		link, or None if no matching `GRM Project Role` exists for this project.
		"""
		if not role_name:
			return None
		candidate = f"{self.project_code}-{role_name}"
		if frappe.db.exists("GRM Project Role", candidate):
			return candidate
		# Fallback: a project might have stored the role under a different
		# `name` autoname format. Look it up by (project, role_name).
		match = frappe.db.get_value(
			"GRM Project Role",
			{"project": self.project_code, "role_name": role_name},
			"name",
		)
		return match or None

	def _wizard_rows_to_worker_data(self, rows: list[dict]) -> tuple[list[dict], list[str]]:
		"""Resolve region names → region IDs and `position` → `GRM Project
		Role` link, then build internal worker_data dicts."""
		errors: list[str] = []
		region_names = sorted({r["region"] for r in rows if r.get("region")})
		region_map: dict[str, str] = {}
		if region_names:
			existing = (
				frappe.qb.from_("GRM Administrative Region")
				.select("name", "region_name")
				.where(frappe.qb.Field("project") == self.project_code)
				.where(frappe.qb.Field("region_name").isin(region_names))
				.run(as_dict=True)
			)
			for row in existing:
				# Last write wins if duplicate region names; the importer
				# picks ANY matching region — duplicates within a project are
				# rare and the validation layer logs a warning.
				region_map[row["region_name"]] = row["name"]

		worker_data: list[dict] = []
		for r in rows:
			region_name = r["region"]
			region_id = region_map.get(region_name)
			if not region_id:
				errors.append(
					f"Row {r['_row_num']}: region '{region_name}' not found in project {self.project_code}"
				)
				continue
			position = r["position"]
			# Per-row override: optional `project_role` column. Falls
			# back to `position` (treated as the Project Role's
			# `role_name`), then to `DEFAULT_PROJECT_ROLE_NAME`.
			role_name = (r.get("project_role") or position or DEFAULT_PROJECT_ROLE_NAME).strip()
			project_role_link = self._project_role_link(role_name)
			if not project_role_link:
				errors.append(
					f"Row {r['_row_num']}: no GRM Project Role named "
					f"'{role_name}' in project {self.project_code} "
					"(create it via wizard Step 'User Types' first)"
				)
				continue
			email = r.get("email") or self._generate_email_from_position(position, region_name)
			phone = r.get("phone")
			username = phone or email
			worker_name = f"{r['first_name']} {r['last_name']}".strip()
			worker_data.append(
				{
					"worker_name": worker_name,
					"username": username,
					"email": email,
					"phone": phone,
					"role": project_role_link,
					"position_title": position,
					"region_id": region_id,
					"region_name": region_name,
				}
			)
		return worker_data, errors

	# ------------------------------------------------------------------
	# Auto-generation helpers (single-region worker_data)
	# ------------------------------------------------------------------
	def _generate_worker_data_for_region(
		self, region: dict, position_template: str = "{level}_officer"
	) -> dict:
		level = region.get("administrative_level") or ""
		region_name = region.get("region_name") or ""
		slug_level = self._slugify(level.lower()) or "officer"
		slug_region = self._slugify(region_name.lower())
		position = position_template.format(level=slug_level)
		email = f"{position}.{slug_region}@{self.email_domain}"
		# Auto-generation always uses the default Project Role
		# (DEFAULT_PROJECT_ROLE_NAME). Caller is expected to have ensured
		# the project has that Project Role — `_validate_inputs` will
		# have already failed if no Project Roles exist at all.
		project_role_link = (
			self._project_role_link(DEFAULT_PROJECT_ROLE_NAME) or self._first_project_role_link()
		)
		return {
			"worker_name": f"{level} Field Officer - {region_name}",
			"username": email,
			"email": email,
			"phone": None,
			"role": project_role_link,
			"position_title": f"Field Officer ({level})",
			"region_id": region["name"],
			"region_name": region_name,
		}

	# ------------------------------------------------------------------
	# Bulk machinery (verbatim from legacy class, ``self.frappe.*`` removed)
	# ------------------------------------------------------------------
	def _bulk_validate_and_prepare(self, worker_data_list: list[dict]) -> dict:
		if not worker_data_list:
			return {"new_users": [], "new_assignments": [], "skipped_users": 0, "skipped_assignments": 0}

		region_ids = list({w["region_id"] for w in worker_data_list})
		roles = list({w["role"] for w in worker_data_list})

		existing_regions = (
			frappe.qb.from_("GRM Administrative Region")
			.select("name")
			.where(frappe.qb.Field("name").isin(region_ids))
			.run(pluck=True)
		)
		missing_regions = set(region_ids) - set(existing_regions)
		if missing_regions:
			raise ValueError(f"Regions not found: {', '.join(missing_regions)}")

		# Roles are now `GRM Project Role` links scoped to this project,
		# populated by `_wizard_rows_to_worker_data` via `_project_role_link`.
		existing_roles = (
			frappe.qb.from_("GRM Project Role")
			.select("name")
			.where(frappe.qb.Field("name").isin(roles))
			.where(frappe.qb.Field("project") == self.project_code)
			.run(pluck=True)
		)
		missing_roles = set(roles) - set(existing_roles)
		if missing_roles:
			raise ValueError(
				f"GRM Project Role(s) not found in project {self.project_code}: "
				f"{', '.join(sorted(missing_roles))}"
			)

		usernames = list({w["username"] for w in worker_data_list if w.get("username")})
		emails = list({w["email"] for w in worker_data_list if w.get("email")})

		existing_users_by_username: dict[str, str] = {}
		existing_users_by_email: dict[str, str] = {}
		if usernames:
			for u in (
				frappe.qb.from_("User")
				.select("name", "username", "email")
				.where(frappe.qb.Field("username").isin(usernames))
				.run(as_dict=True)
			):
				existing_users_by_username[u["username"]] = u["name"]
				if u.get("email"):
					existing_users_by_email[u["email"]] = u["name"]
		if emails:
			for u in (
				frappe.qb.from_("User")
				.select("name", "username", "email")
				.where(frappe.qb.Field("email").isin(emails))
				.run(as_dict=True)
			):
				existing_users_by_email[u["email"]] = u["name"]
				if u.get("username"):
					existing_users_by_username[u["username"]] = u["name"]

		existing_assignments = (
			frappe.qb.from_("GRM User Project Assignment")
			.select("user", "project", "administrative_region", "role")
			.where(frappe.qb.Field("project") == self.project_code)
			.run(as_dict=True)
		)
		# Tuple keys avoid string-collision ambiguity: if any of user /
		# project / region contains an underscore (User names are emails,
		# so they often contain underscores or dots), the f-string form
		# is not bijective — ("a_b", "c", "d") and ("a", "b_c", "d") both
		# serialize to "a_b_c_d". Tuples make the composite key safe.
		existing_assignment_keys = {
			(a["user"], a["project"], a["administrative_region"]) for a in existing_assignments
		}

		validated = {
			"new_users": [],
			"new_assignments": [],
			"skipped_users": 0,
			"skipped_assignments": 0,
		}
		for worker_data in worker_data_list:
			user_name = None
			if worker_data.get("email") and worker_data["email"] in existing_users_by_email:
				user_name = existing_users_by_email[worker_data["email"]]
				validated["skipped_users"] += 1
			elif worker_data.get("username") and worker_data["username"] in existing_users_by_username:
				user_name = existing_users_by_username[worker_data["username"]]
				validated["skipped_users"] += 1
			else:
				user_data = self._prepare_user_data(worker_data)
				validated["new_users"].append(user_data)
				user_name = user_data["name"]

			assignment_key = (user_name, self.project_code, worker_data["region_id"])
			if assignment_key not in existing_assignment_keys:
				validated["new_assignments"].append(self._prepare_assignment_data(worker_data, user_name))
			else:
				validated["skipped_assignments"] += 1
		return validated

	def _prepare_user_data(self, worker_data: dict) -> dict:
		# Frappe's User DocType convention: name == email. Activation flows
		# (`update_password`, `enable_user`) look up by name, so a random-hash
		# name silently breaks every downstream activation call.
		email = worker_data["email"] or f"{worker_data['username']}@temp.local"
		user_name = email
		parts = (worker_data["worker_name"] or "").strip().split()
		if len(parts) >= 2:
			first_name, last_name = parts[0], " ".join(parts[1:])
		else:
			first_name, last_name = (worker_data["worker_name"] or "User"), "User"
		full_name = f"{first_name} {last_name}"
		return {
			"name": user_name,
			"username": worker_data["username"],
			"email": email,
			"first_name": first_name,
			"last_name": last_name,
			"full_name": full_name,
			"enabled": 1,
			"send_welcome_email": 0,
			"creation": get_datetime(),
			"modified": get_datetime(),
			"owner": frappe.session.user,
			"modified_by": frappe.session.user,
			"docstatus": 0,
			"worker_data": worker_data,
		}

	def _department_link_for_project(self) -> str | None:
		"""Resolve ``self.department`` (display name like "General") to the
		actual GRM Issue Department record's ``name`` (random hash) on the
		current project. Returns ``None`` if no matching department is
		linked to this project — in which case the assignment row's
		``department`` field stays empty and falls back to region-only
		scoping. Cached per importer instance.
		"""
		if self._resolved_department_link is not None:
			return self._resolved_department_link or None
		if not self.department:
			self._resolved_department_link = ""
			return None
		rows = frappe.db.sql(
			"""
            SELECT d.name
            FROM `tabGRM Issue Department` d
            JOIN `tabGRM Project Link` pl
              ON pl.parent = d.name AND pl.parenttype = 'GRM Issue Department'
            WHERE d.department_name = %s AND pl.project = %s
            LIMIT 1
            """,
			(self.department, self.project_code),
		)
		link = rows[0][0] if rows else ""
		self._resolved_department_link = link
		return link or None

	def _project_role_duties_set(self, project_role_link: str) -> set[str]:
		"""Return the set of duty names linked to ``project_role_link``.
		Cached on ``self._role_duty_cache`` for the lifetime of the importer
		(one project per run, so cache scope is correct)."""
		if project_role_link in self._role_duty_cache:
			return self._role_duty_cache[project_role_link]
		rows = (
			frappe.get_all(
				"GRM Project Role Duty",
				filters={"parent": project_role_link},
				pluck="duty",
			)
			or []
		)
		out = set(rows)
		self._role_duty_cache[project_role_link] = out
		return out

	def _prepare_assignment_data(self, worker_data: dict, user_name: str) -> dict:
		import secrets

		assignment_name = frappe.generate_hash(length=10)
		# Government-worker assignments (those needing activation) are
		# those whose Project Role grants any GOVERNMENT_WORKER_DUTIES.
		duties = self._project_role_duties_set(worker_data["role"])
		is_gov_worker = bool(duties & GOVERNMENT_WORKER_DUTIES)
		activation_code = None
		activation_status = "Activated"
		activation_expires_on = None
		if is_gov_worker:
			# Review fix A2: replaced zlib.adler32(...) (non-cryptographic
			# checksum, predictable seed) with CSPRNG-backed 6-digit code.
			activation_code = f"{secrets.randbelow(10**6):06d}"
			activation_status = "Pending Activation"
			activation_expires_on = add_to_date(get_datetime(), hours=48)
		return {
			"name": assignment_name,
			"user": user_name,
			"project": self.project_code,
			"role": worker_data["role"],
			"position_title": worker_data["position_title"],
			"administrative_region": worker_data["region_id"],
			"department": self._department_link_for_project(),
			"is_active": 1,
			"activation_code": activation_code,
			"activation_status": activation_status,
			"activation_expires_on": activation_expires_on,
			"creation": get_datetime(),
			"modified": get_datetime(),
			"owner": frappe.session.user,
			"modified_by": frappe.session.user,
			"docstatus": 0,
		}

	def _bulk_create_workers(self, validated: dict) -> bool:
		new_users = validated.get("new_users", [])
		new_assignments = validated.get("new_assignments", [])
		if new_users:
			self._bulk_insert_users_sql(new_users)
		if new_assignments:
			self._bulk_insert_assignments_sql(new_assignments)
			# Duty-driven Frappe Role grant: walk each new assignment's
			# Project Role and grant `GRM <duty>` Roles via the
			# assignment hook (replaces the old direct `tabHas Role`
			# insert that granted the legacy `GRM Field Officer`).
			self._post_insert_grant_duty_roles(new_assignments)
		self.total_users = len(new_users)
		self.total_created = len(new_assignments)
		self.skipped_users = validated.get("skipped_users", 0)
		self.skipped_assignments = validated.get("skipped_assignments", 0)
		return True

	def _bulk_insert_users_sql(self, user_data_list: list[dict]) -> None:
		"""Bulk-INSERT raw User rows, skipping the User controller.

		Review fix B13 documentation — this path intentionally bypasses
		``frappe.get_doc("User", ...).insert()`` for speed (10-100x
		faster on multi-thousand-row imports). What we therefore SKIP and
		what compensates for each skip is listed below; if you're adding
		a new side-effect to the User controller, audit this list:

		Skipped controller side-effects:
		  - ``User.before_insert`` (welcome-email, send_welcome_email
		    guard, etc.) — compensated by ``_bulk_set_passwords`` setting
		    a temporary password, and by the bulk import flow being a
		    non-self-service surface (no welcome email needed).
		  - ``User.validate`` (mandatory-field checks, email format,
		    uniqueness check) — compensated by ``_bulk_validate_and_prepare``
		    doing the equivalent checks up-front against the input list.
		  - Role grants from ``UserRole`` child rows — Role assignment is
		    duty-driven now: ``_post_insert_grant_duty_roles`` runs after
		    the assignment rows are inserted and walks each Project Role's
		    duties to grant the matching ``GRM <duty>`` Frappe Roles.
		  - Full-text search index refresh — the global search reindex
		    cron will pick the new rows up on its next scheduled run.
		  - User.on_update hooks subscribed by other apps — none are
		    critical for the duty-driven flow, but be aware.

		Alternative: ``frappe.get_doc(...).insert(ignore_mandatory=True,
		ignore_permissions=True)`` per row gets you back all the
		controller side-effects at ~30x slower throughput. Use that
		instead if a future side-effect can't be replicated outside the
		controller.
		"""
		# NOTE: Frappe Role grants are NOT inserted here anymore.
		# Per the duty-driven architecture, the assignment doctype's
		# `assign_role_to_user()` hook walks the Project Role's duties
		# and grants the matching `GRM <duty>` Frappe Roles. We invoke
		# that hook in `_post_insert_grant_duty_roles` after assignments
		# are written.
		for i in range(0, len(user_data_list), self.batch_size):
			batch = user_data_list[i : i + self.batch_size]
			valid_users: list[dict] = []
			for u in batch:
				if not all(k in u for k in ("name", "username", "email", "first_name")):
					frappe.log_error(f"Missing required fields in user data: {u}")
					continue
				valid_users.append(u)

			if valid_users:
				values = [
					(
						u["name"],
						u["username"],
						u["email"],
						u["first_name"],
						u["last_name"],
						u["full_name"],
						u["enabled"],
						u["send_welcome_email"],
						u["creation"],
						u["modified"],
						u["owner"],
						u["modified_by"],
						u["docstatus"],
					)
					for u in valid_users
				]
				placeholders = ", ".join(["%s"] * len(values[0]))
				values_placeholder = ", ".join([f"({placeholders})"] * len(values))
				sql = (
					"INSERT INTO `tabUser` "
					"(`name`,`username`,`email`,`first_name`,`last_name`,`full_name`,`enabled`,"
					"`send_welcome_email`,`creation`,`modified`,`owner`,`modified_by`,`docstatus`) "
					f"VALUES {values_placeholder}"
				)
				flat = [v for row in values for v in row]
				frappe.db.sql(sql, flat)

		self._bulk_set_passwords(user_data_list)

	def _post_insert_grant_duty_roles(self, assignment_data_list: list[dict]) -> None:
		"""For each freshly-inserted assignment, invoke the
		`assign_role_to_user()` hook so the user gains every
		`GRM <duty>` Frappe Role implied by their Project Role.

		Bypasses the doctype save (which we skipped via raw SQL) but
		gets us the same end-state. Idempotent: the hook checks for
		existing roles before appending."""
		for a in assignment_data_list:
			try:
				doc = frappe.get_doc("GRM User Project Assignment", a["name"])
				doc.assign_role_to_user()
			except Exception as exc:
				frappe.log_error(
					title="duty-role grant failed during bulk import",
					message=f"{a.get('name')}: {exc}",
				)

	def _bulk_insert_assignments_sql(self, assignment_data_list: list[dict]) -> None:
		for i in range(0, len(assignment_data_list), self.batch_size):
			batch = assignment_data_list[i : i + self.batch_size]
			valid: list[dict] = []
			for a in batch:
				if not all(k in a for k in ("name", "user", "project", "role", "administrative_region")):
					frappe.log_error(f"Missing required fields in assignment: {a}")
					continue
				valid.append(a)
			if not valid:
				continue
			values = [
				(
					a["name"],
					a["user"],
					a["project"],
					a["role"],
					a["position_title"],
					a["administrative_region"],
					a["department"],
					a["is_active"],
					a["activation_code"],
					a["activation_status"],
					a["activation_expires_on"],
					a["creation"],
					a["modified"],
					a["owner"],
					a["modified_by"],
					a["docstatus"],
				)
				for a in valid
			]
			placeholders = ", ".join(["%s"] * len(values[0]))
			values_placeholder = ", ".join([f"({placeholders})"] * len(values))
			sql = (
				"INSERT INTO `tabGRM User Project Assignment` "
				"(`name`,`user`,`project`,`role`,`position_title`,"
				"`administrative_region`,`department`,`is_active`,`activation_code`,`activation_status`,"
				"`activation_expires_on`,`creation`,`modified`,`owner`,`modified_by`,`docstatus`) "
				f"VALUES {values_placeholder}"
			)
			flat = [v for row in values for v in row]
			frappe.db.sql(sql, flat)

	def _bulk_set_passwords(self, user_data_list: list[dict]) -> None:
		"""Set a temporary password on each freshly-bulk-inserted user.

		Review fix A4: when no ``default_password`` is configured we
		generate a *unique* CSPRNG password per user (the previous
		implementation generated a single shared password for the whole
		batch, which meant a leak of one row's hash cracked every account
		in the import).
		"""
		try:
			from frappe.utils.password import update_password
		except Exception:
			return
		for u in user_data_list:
			password = self.default_password or self._generate_temp_password()
			try:
				update_password(u["name"], password)
			except Exception as exc:
				self.log.warning(f"Failed to set password for {u['name']}: {exc}")

	# ------------------------------------------------------------------
	# Activation-code export
	# ------------------------------------------------------------------
	def _fetch_activation_codes(self) -> list[dict]:
		# Filter assignments whose Project Role grants any of the
		# GOVERNMENT_WORKER_DUTIES — i.e. assignments that needed an
		# activation code at create time. Replaces the legacy filter
		# on the four hard-coded role-name strings.
		gov_role_links = frappe.db.sql_list(
			"""SELECT DISTINCT pr.name FROM `tabGRM Project Role` pr
               JOIN `tabGRM Project Role Duty` prd ON prd.parent = pr.name
               WHERE pr.project = %s AND prd.duty IN %s""",
			(self.project_code, tuple(GOVERNMENT_WORKER_DUTIES)),
		)
		if not gov_role_links:
			return []
		a = frappe.qb.DocType("GRM User Project Assignment")
		u = frappe.qb.DocType("User")
		r = frappe.qb.DocType("GRM Administrative Region")
		return (
			frappe.qb.from_(a)
			.left_join(u)
			.on(a.user == u.name)
			.left_join(r)
			.on(a.administrative_region == r.name)
			.select(
				u.email,
				u.username,
				a.activation_code,
				a.activation_status,
				a.position_title,
				r.region_name,
				a.department,
				a.activation_expires_on,
				a.activated_on,
				a.code_sent_on,
			)
			.where(a.project == self.project_code)
			.where(a.role.isin(gov_role_links))
			.run(as_dict=True)
		)

	def _collect_activation_codes(self) -> list[dict]:
		return [
			{
				"email": row.get("email"),
				"username": row.get("username"),
				"activation_code": row.get("activation_code"),
				"status": row.get("activation_status"),
				"expires_on": str(row.get("activation_expires_on") or ""),
			}
			for row in self._fetch_activation_codes()
			if row.get("activation_code")
		]

	# ------------------------------------------------------------------
	# Legacy CLI stream helper (kept for backwards compatibility)
	# ------------------------------------------------------------------
	def _create_from_legacy_stream(self, fh) -> bool:
		reader = csv.DictReader(fh)
		worker_data_list: list[dict] = []
		for row_num, row in enumerate(reader, start=2):
			if (
				row.get("region_id", "").startswith("#")
				or not row.get("worker_name", "").strip()
				or not row.get("region_id", "").strip()
			):
				continue
			try:
				wd = self._parse_legacy_csv_row(row)
				if wd:
					worker_data_list.append(wd)
			except Exception as exc:
				self.errors.append(f"Row {row_num}: {exc}")
		if not worker_data_list:
			return True
		if self.dry_run:
			self._simulate_creation(worker_data_list)
			return True
		validated = self._bulk_validate_and_prepare(worker_data_list)
		return self._bulk_create_workers(validated)

	def _parse_legacy_csv_row(self, row: dict) -> dict | None:
		worker_name = row["worker_name"].strip()
		role = row["role"].strip()
		if not worker_name or not role:
			raise ValueError("Worker name and role are required")
		email = (row.get("email") or "").strip()
		phone = (row.get("phone_number") or "").strip()
		auto = (row.get("auto_generate_email") or "no").strip().lower() in ("yes", "true", "1")
		if not email and auto:
			email = self._generate_email_from_position(
				(row.get("position_title") or role).strip(),
				row["region_name"].strip(),
			)
		username = phone or email
		if not username:
			raise ValueError("Either phone_number or email must be provided")
		if email and not self._is_valid_email(email):
			raise ValueError(f"Invalid email format: {email}")
		return {
			"worker_name": worker_name,
			"username": username,
			"email": email,
			"phone": phone,
			"role": role,
			"position_title": (row.get("position_title") or role).strip(),
			"region_id": row["region_id"].strip(),
			"region_name": row["region_name"].strip(),
		}

	# ------------------------------------------------------------------
	# Misc helpers
	# ------------------------------------------------------------------
	def _simulate_creation(self, worker_data_list: list[dict]) -> None:
		self.total_created = len(worker_data_list)
		self.total_users = len({w["username"] for w in worker_data_list})

	def _generate_email_from_position(self, position_title: str, region_name: str) -> str:
		return f"{self._slugify(position_title.lower())}.{self._slugify(region_name.lower())}@{self.email_domain}"

	def _is_valid_email(self, email: str) -> bool:
		return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email) is not None

	def _generate_temp_password(self) -> str:
		# Review fix A4: CSPRNG via secrets.choice (previous code used
		# ``random.choice`` which is seedable from time and unsafe for
		# generating credentials).
		chars = string.ascii_letters + string.digits + "@#$%&"
		return "".join(secrets.choice(chars) for _ in range(12))

	def _slugify(self, text: str) -> str:
		text = re.sub(r"[^\w\s-]", "", (text or "").lower())
		text = re.sub(r"[-\s]+", "-", text)
		return text.strip("-")

	def _report(self) -> dict:
		return {
			"created": self.total_users,
			"assignments": self.total_created,
			"errors": list(self.errors),
			"skipped_users": self.skipped_users,
			"skipped_assignments": self.skipped_assignments,
		}


# ---------------------------------------------------------------------------
# Slim public API (called by wizard RPC + direct ``bench execute`` smoke tests)
# ---------------------------------------------------------------------------


def parse_users_csv(project: str, csv_text: str) -> dict:
	"""Validate-only preview of a wizard worker CSV."""
	with OptimizedBulkWorkerCreator(project=project) as creator:
		return creator.validate_csv_text(csv_text)


def bulk_create_from_csv(project: str, csv_text: str, default_password: str | None = None) -> dict:
	"""Insert workers from a wizard CSV. Returns counts + activation codes."""
	with OptimizedBulkWorkerCreator(project=project, default_password=default_password) as creator:
		return creator.create_from_csv_text(csv_text, default_password=default_password)


def auto_generate_per_region(
	project: str, level_type: str, position_template: str = "{level}_officer"
) -> dict:
	"""Auto-generate one worker per region at the given administrative level."""
	with OptimizedBulkWorkerCreator(project=project) as creator:
		return creator.generate_for_regions(level_filter=level_type, position_template=position_template)


def export_activation_codes(project: str) -> str:
	"""Return CSV text of all activation codes for the project."""
	with OptimizedBulkWorkerCreator(project=project) as creator:
		return creator.export_activation_codes_csv()
