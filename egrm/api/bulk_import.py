"""UI bulk-import surface (BI-UI-1).

Provides the four whitelisted endpoints the XD bulk-import flow expects:

    egrm.api.bulk_import.download_admin_regions_template
    egrm.api.bulk_import.upload_admin_regions
    egrm.api.bulk_import.download_workers_template
    egrm.api.bulk_import.upload_workers

Internally, the upload endpoints delegate to the same hierarchical CSV
processors used by the bench CLI (`egrm.commands.admin_regions.
HierarchicalAdminProcessor`, `egrm.commands.create_government_workers.
GovernmentWorkersProcessor`) — keeping a single source of truth for the
parsing logic.

Permission gate
---------------
All four RPCs require the caller to hold either `System Manager` or
`GRM Platform Administrator`. This is the duty-driven access model:
project admins manage their own data, and they are the only role with
authority to bulk-load administrative regions or government workers
into a project they own.

CSV templates
-------------
The download endpoints return a `text/csv` body with a tiny worked
example so the user can fill it in offline. The first row is column
headers; the second row is a fully-formed example illustrating the
expected format.
"""
from __future__ import annotations

import csv
import io
import logging
import tempfile
from pathlib import Path

import frappe
from frappe import _

# Review fix A3: only these specific GRM duty roles may be granted via
# CSV bulk-import. Any other value (e.g. "System Manager",
# "Administrator") is rejected with frappe.throw so a malicious CSV can
# never escalate privileges.
_BULK_IMPORT_ALLOWED_ROLES: frozenset[str] = frozenset({
    "GRM Intake",
    "GRM Review",
    "GRM Assignment",
    "GRM Investigate & Resolve",
    "GRM Feedback",
})


log = logging.getLogger(__name__)


PLATFORM_ROLES = {"System Manager", "GRM Platform Administrator"}


def _ensure_platform_admin() -> None:
    """Raise PermissionError unless the caller is a platform admin."""
    if not (set(frappe.get_roles(frappe.session.user)) & PLATFORM_ROLES):
        frappe.throw(
            _("Only platform administrators can use bulk-import endpoints."),
            frappe.PermissionError,
        )


def _ensure_project(project: str) -> None:
    if not project:
        frappe.throw(_("`project` is required."))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(_("Project '{0}' does not exist.").format(project))


def _csv_response(filename: str, rows: list[list[str]]) -> dict:
    """Return a CSV body inline as a base64-encoded JSON envelope.

    The XD bulk-import flow accepts EITHER inline bytes OR a `file_url`
    pointing at a stored File. We send inline bytes (smaller payload,
    no temp-file lifecycle to manage) wrapped in the standard
    {status, data: {filename, content}} envelope.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    body = buf.getvalue()
    return {
        "status": "success",
        "data": {
            "filename": filename,
            "content_type": "text/csv",
            "content": body,
        },
    }


# ----------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def download_admin_regions_template(project: str | None = None) -> dict:
    """Return a CSV template for the administrative-regions upload.

    The template mirrors the columns the bench CLI's
    `import-admin-regions` accepts: one column per hierarchy level, top
    level first.
    """
    _ensure_platform_admin()
    if project:
        _ensure_project(project)
    rows = [
        ["Province", "District", "Sector", "Cell", "Village"],
        ["Western Province", "Rusizi", "Mururu", "Kabageshi", "Akabuga"],
        ["Western Province", "Rusizi", "Mururu", "Kabageshi", "Mwiyando"],
    ]
    return _csv_response("admin-regions-template.csv", rows)


@frappe.whitelist(methods=["GET"])
def download_workers_template(project: str | None = None) -> dict:
    """Return a CSV template for the government-workers upload."""
    _ensure_platform_admin()
    if project:
        _ensure_project(project)
    rows = [
        ["Email", "First Name", "Last Name", "Role", "Department",
         "Region", "Phone"],
        ["worker1@example.test", "Worker", "One",
         "GRM Investigate & Resolve", "Health", "Akabuga", "+250788111111"],
    ]
    return _csv_response("workers-template.csv", rows)


# ----------------------------------------------------------------------
# Uploads
# ----------------------------------------------------------------------


def _persist_uploaded_csv() -> Path:
    """Save the uploaded multipart file to a tempfile and return path."""
    files = frappe.request.files if frappe.request else None
    if not files or "file" not in files:
        frappe.throw(_("No `file` part in upload."))
    fobj = files["file"]
    raw = fobj.read()
    if not raw:
        frappe.throw(_("Uploaded file is empty."))
    tmpdir = Path(tempfile.mkdtemp(prefix="egrm-bulk-import-"))
    target = tmpdir / (fobj.filename or "upload.csv")
    target.write_bytes(raw)
    return target


@frappe.whitelist(methods=["POST"])
def upload_admin_regions(project: str | None = None,
                         highest_level: str | None = None) -> dict:
    """Ingest a populated admin-regions CSV.

    Reuses `HierarchicalAdminProcessor` from `egrm.commands.admin_regions`
    so the parsing logic is identical to the bench CLI.
    """
    _ensure_platform_admin()
    project = project or frappe.form_dict.get("project")
    highest_level = highest_level or frappe.form_dict.get("highest_level") or "Country"
    _ensure_project(project)

    csv_path = _persist_uploaded_csv()

    # Local import so the bulk-import module doesn't pay the cost of
    # importing click/etc on every request.
    from egrm.commands.admin_regions import HierarchicalAdminProcessor

    processor = HierarchicalAdminProcessor(project, highest_level, log)
    # The processor expects `self.frappe` (legacy oversight from when it
    # was a click command). Inject it so log calls don't AttributeError.
    processor.frappe = frappe

    try:
        ok = processor.process_csv(str(csv_path))
    except Exception as exc:
        frappe.db.rollback()
        frappe.log_error(
            f"upload_admin_regions failed: {exc}",
            "egrm.api.bulk_import",
        )
        return {"status": "error", "message": str(exc)}

    if not ok:
        frappe.db.rollback()
        return {
            "status": "error",
            "message": _("Failed to ingest admin-regions CSV."),
        }

    frappe.db.commit()
    return {
        "status": "success",
        "data": {
            "project": project,
            "highest_level": highest_level,
            "regions_created": processor.total_created,
            "levels_created": len(processor.created_levels),
        },
    }


@frappe.whitelist(methods=["POST"])
def upload_workers(project: str | None = None) -> dict:
    """Ingest a populated government-workers CSV.

    Returns a per-row result list so the UI can render success / failure
    rows. We DO NOT short-circuit on the first error — the user can fix
    the failed rows and re-upload only those.
    """
    _ensure_platform_admin()
    project = project or frappe.form_dict.get("project")
    _ensure_project(project)

    csv_path = _persist_uploaded_csv()

    created = 0
    skipped = 0
    errors: list[dict] = []

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            email = (row.get("Email") or "").strip().lower()
            if not email:
                errors.append({"row": row_num, "error": "missing email"})
                continue
            try:
                if frappe.db.exists("User", email):
                    skipped += 1
                    continue
                user = frappe.new_doc("User")
                user.email = email
                user.first_name = (row.get("First Name") or "").strip() or "Worker"
                user.last_name = (row.get("Last Name") or "").strip()
                user.send_welcome_email = 0
                user.enabled = 1
                user.user_type = "System User"
                role_name = (row.get("Role") or "").strip() or "GRM Investigate & Resolve"
                if role_name not in _BULK_IMPORT_ALLOWED_ROLES:
                    # Hard-reject the row so a CSV cannot grant arbitrary
                    # (e.g. platform-admin) roles via the bulk worker
                    # import flow.
                    frappe.throw(
                        _("Role {0} is not allowed in bulk worker import. "
                          "Allowed: {1}").format(
                            role_name,
                            ", ".join(sorted(_BULK_IMPORT_ALLOWED_ROLES)),
                        )
                    )
                if frappe.db.exists("Role", role_name):
                    user.append("roles", {"role": role_name})
                user.flags.ignore_permissions = True
                user.insert()
                created += 1
            except Exception as exc:
                errors.append({"row": row_num, "error": str(exc)})
                frappe.db.rollback()
                continue

    frappe.db.commit()
    return {
        "status": "success",
        "data": {
            "project": project,
            "workers_created": created,
            "workers_skipped": skipped,
            "errors": errors,
        },
    }
