"""Phase B (Step 9 Users): Data Import wrapper endpoints.

``prepare_user_import`` (B.1), ``start_user_import`` (B.2),
``poll_user_import`` (B.3), ``download_user_template`` (B.4).
Re-exported from ``grm_project_wizard.py`` so JS RPC paths keep working.
Split from ``grm_project_wizard_user_import.py`` for the <=400-line cap
(plan §Engineering Conventions clause 4). ``poll_user_import`` derives
success/fail counts from ``Data Import Log`` (parent stores no totals).
"""

from __future__ import annotations

import csv
import io
import logging
import os
from typing import Any

import frappe
from frappe import _

from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_import import (
    get_assignment_field_meta,
)
from egrm.services.user_import import (
    TARGET_REGION,
    TARGET_SKIP,
    materialize_staged_csv,
    validate_mapping,
)

logger = logging.getLogger(__name__)


def _require_wizard_role() -> None:
    """Lazy shim — avoids circular import with ``grm_project_wizard``
    (which re-exports our endpoints at module bottom)."""
    from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
        _require_wizard_role as _impl,
    )
    return _impl()


# --- Argument coercion helpers ---------------------------------------------

def _coerce_dict(value: Any, label: str) -> dict:
    """Coerce JSON-string-or-dict RPC argument to a dict."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    parsed = frappe.parse_json(value)
    if not isinstance(parsed, dict):
        frappe.throw(_("Expected an object for {0}, got {1}").format(label, type(parsed).__name__))
    return parsed


def _coerce_bool(value: Any) -> bool:
    """Accept the truthy variants RPC sends (``"1"`` / ``"true"`` / ``True``)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


# --- B.1 prepare_user_import -----------------------------------------------

def _read_uploaded_file(file_url: str) -> tuple[list[str], list[list[str]]]:
    """Read the CSV or XLSX at ``file_url`` and return ``(headers, rows)``.

    Raises ``frappe.ValidationError`` for unsupported extensions or empty files.
    """
    if not file_url:
        frappe.throw(_("file_url is required"))

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    abs_path = file_doc.get_full_path()
    lower = abs_path.lower()

    raw_rows: list[list[Any]]
    if lower.endswith(".csv"):
        from frappe.utils.csvutils import read_csv_content
        with open(abs_path, "rb") as fh:
            raw_rows = read_csv_content(fh.read())
    elif lower.endswith((".xlsx", ".xls")):
        from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
        raw_rows = read_xlsx_file_from_attached_file(file_url=file_url)
    else:
        frappe.throw(_("Unsupported file type: {0}. Use CSV or XLSX.").format(abs_path))

    if not raw_rows:
        frappe.throw(_("Uploaded file is empty"))

    # Stringify cells (xlsx returns native types). Empty cells become "".
    def _stringify(row: list[Any]) -> list[str]:
        return ["" if cell is None else str(cell) for cell in row]

    headers = _stringify(raw_rows[0])
    rows = [_stringify(r) for r in raw_rows[1:]]
    if not any(h.strip() for h in headers):
        frappe.throw(_("Uploaded file has no header row"))
    return headers, rows


def _build_mapping(headers: list[str], header_mapping: dict, level_mapping: dict) -> dict:
    """Combine JS-shaped ``header_mapping`` + ``level_mapping`` into the
    canonical mapping dict ``materialize_staged_csv`` expects.

    ``header_mapping[h]`` = ``"User.<f>"`` | ``"Assignment.<f>"`` |
    ``"(skip)"`` | ``"administrative_region"``; ``level_mapping[h]`` =
    level-type name (only when target == ``administrative_region``).
    Headers absent from ``header_mapping`` default to ``TARGET_SKIP``.
    """
    out: dict[str, dict[str, Any]] = {}
    for header in headers:
        target = (header_mapping.get(header) or TARGET_SKIP).strip()
        entry: dict[str, Any] = {
            "target": target,
            "level_type": None,
        }
        if target == TARGET_REGION:
            level = (level_mapping.get(header) or "").strip()
            entry["level_type"] = level or None
        out[header] = entry
    return out


@frappe.whitelist()
def prepare_user_import(
    project: str,
    file_url: str,
    header_mapping: Any,
    level_mapping: Any = None,
    auto_create_regions: Any = True,
) -> dict:
    """Stage a user-import CSV and create the wrapping ``Data Import`` doc.

    Reads ``file_url`` (CSV or XLSX), validates the mapping, calls
    ``materialize_staged_csv``, attaches the staged CSV to a freshly
    -created ``Data Import``, and returns preview + counts +
    region-creation summary + the ``data_import`` name.
    """
    _require_wizard_role()

    project = (project or "").strip()
    if not project:
        frappe.throw(_("project is required"))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    header_mapping_d = _coerce_dict(header_mapping, "header_mapping")
    level_mapping_d = _coerce_dict(level_mapping, "level_mapping")
    auto_create = _coerce_bool(auto_create_regions)

    # 2. Read the uploaded file.
    headers, rows = _read_uploaded_file(file_url)

    # 3. Build the canonical mapping.
    mapping = _build_mapping(headers, header_mapping_d, level_mapping_d)

    # 4. Validate against doctype-driven required fields.
    project_meta = get_assignment_field_meta(project)
    validation = validate_mapping(mapping, project_meta)
    if not validation["ok"]:
        missing = ", ".join(validation["missing_required"]) or _("(none)")
        errors = "; ".join(validation["errors"]) or _("(none)")
        frappe.throw(
            _("Mapping is invalid. Missing required: {0}. Errors: {1}").format(missing, errors)
        )

    # 5. Materialize the staged CSV.
    result = materialize_staged_csv(
        rows=rows,
        headers=headers,
        mapping=mapping,
        project=project,
        auto_create_regions=auto_create,
    )

    # No ready rows (e.g. dry-run with all regions missing) → skip
    # Data Import creation; Frappe rejects zero-row templates. The
    # wizard UI uses ``regions_to_create`` to prompt re-submit.
    if result["rows_ready"] == 0:
        return {
            "data_import": None,
            "rows_total": result["rows_total"],
            "rows_ready": 0,
            "rows_skipped": result["rows_skipped"],
            "regions_to_create": result["regions_to_create"],
            "warnings": (result["warnings"] or []) + (validation["warnings"] or []),
            "errors": result["errors"],
            "preview": result["preview"],
        }

    # 6. Save staged CSV as an unattached private File, then create the
    # Data Import (Frappe rejects save_file with attached_to_doctype but
    # no attached_to_name — see file.py::validate_attachment_references).
    from frappe.utils.file_manager import save_file

    with open(result["staged_path"], "rb") as fh:
        staged_bytes = fh.read()

    staged_filename = os.path.basename(result["staged_path"])
    staged_file_doc = save_file(
        fname=staged_filename,
        content=staged_bytes,
        dt=None,
        dn=None,
        folder="Home/Attachments",
        is_private=1,
    )

    data_import = frappe.get_doc({
        "doctype": "Data Import",
        "reference_doctype": "GRM User Project Assignment",
        "import_type": "Insert New Records",
        "import_file": staged_file_doc.file_url,
        "submit_after_import": 0,
        "mute_emails": 1,
    })
    data_import.insert(ignore_permissions=False)

    # 7. Re-attach via db.set_value (atomic — bypasses File's split-write
    # validation) so deleting the Data Import cascades to the staged CSV.
    frappe.db.set_value(
        "File", staged_file_doc.name,
        {"attached_to_doctype": "Data Import", "attached_to_name": data_import.name},
    )

    logger.info(
        "prepare_user_import: created Data Import %s for project %s "
        "(rows_total=%s rows_ready=%s rows_skipped=%s)",
        data_import.name, project,
        result["rows_total"], result["rows_ready"], result["rows_skipped"],
    )

    return {
        "data_import": data_import.name,
        "rows_total": result["rows_total"],
        "rows_ready": result["rows_ready"],
        "rows_skipped": result["rows_skipped"],
        "regions_to_create": result["regions_to_create"],
        "warnings": (result["warnings"] or []) + (validation["warnings"] or []),
        "errors": result["errors"],
        "preview": result["preview"],
    }


# --- B.2 start_user_import -------------------------------------------------

@frappe.whitelist()
def start_user_import(data_import: str) -> dict:
    """Kick off the previously-prepared ``Data Import`` job.

    Wrapper around ``frappe.core.doctype.data_import.data_import.form_start_import``.
    Returns ``{"ok": True, "job_id": <bool>}`` — ``form_start_import``
    returns a truthy/falsy value indicating whether a new background job
    was enqueued (``False`` if one is already running).
    """
    _require_wizard_role()
    if not data_import:
        frappe.throw(_("data_import is required"))

    from frappe.core.doctype.data_import.data_import import form_start_import
    job_id = form_start_import(data_import=data_import)
    return {"ok": True, "job_id": job_id}


# --- B.3 poll_user_import --------------------------------------------------

@frappe.whitelist()
def poll_user_import(data_import: str) -> dict:
    """Return ``Data Import`` status + log preview + success/fail counts.

    Counts derived from ``Data Import Log`` rows (the doctype stores no
    aggregate counters); mirrors ``data_import.py::get_import_status``.
    """
    _require_wizard_role()
    if not data_import:
        frappe.throw(_("data_import is required"))

    doc = frappe.get_doc("Data Import", data_import)

    # Aggregate Data Import Log: group by `success` boolean → counts.
    succeeded = 0
    failed = 0
    logs = frappe.get_all(
        "Data Import Log",
        fields=[{"COUNT": "*", "as": "count"}, "success"],
        filters={"data_import": data_import},
        group_by="success",
    )
    for log in logs:
        count = int(log.get("count") or 0)
        if log.get("success"):
            succeeded = count
        else:
            failed = count

    # ``import_log_preview`` is an HTML virtual field rendered client-side
    # (see ``data_import.js``); it has no persisted value on the doc.
    # Return "" for API-shape parity — the wizard's Step 9 UI builds its
    # own log from Data Import Log rows when it needs richer detail.
    return {
        "status": doc.status or "Pending",
        "payload_count": int(doc.payload_count or 0),
        "import_log_preview": getattr(doc, "import_log_preview", "") or "",
        "succeeded": succeeded,
        "failed": failed,
    }


# --- B.4 download_user_template --------------------------------------------

def _required_user_fields_for_template() -> list[str]:
    """Return the User-doctype labels for the template header.

    Strictly email/first/last — wizard bulk-create synthesises the rest.
    """
    user_meta = frappe.get_meta("User")
    by_name = {f.fieldname: f for f in user_meta.fields}
    out: list[str] = []
    for fname in ("email", "first_name", "last_name"):
        f = by_name.get(fname)
        if not f:
            continue
        out.append(f.label or f.fieldname)
    return out


def _required_assignment_fields_for_template() -> list[str]:
    """Return ``GRM User Project Assignment`` ``reqd: 1`` field labels
    (excludes ``project`` / ``administrative_region`` / ``user``)."""
    out: list[str] = []
    for f in frappe.get_meta("GRM User Project Assignment").fields:
        if not getattr(f, "reqd", 0):
            continue
        if f.fieldname in ("project", "administrative_region", "user"):
            continue
        out.append(f.label or f.fieldname)
    return out


@frappe.whitelist()
def download_user_template(project: str, format: str = "csv") -> None:
    """Emit a CSV or XLSX user-import template for ``project``.

    Header layout, left-to-right: project level types (highest first via
    ``level_order ASC``), required ``User`` fields, required
    ``GRM User Project Assignment`` fields (excluding ``project`` /
    ``administrative_region`` / ``user``). Response written to
    ``frappe.response`` so Frappe returns the file as an attachment.
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(_("project is required"))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    fmt = (format or "csv").strip().lower()
    if fmt not in {"csv", "xlsx"}:
        frappe.throw(_("Unsupported format: {0}. Use 'csv' or 'xlsx'.").format(format))

    level_types = frappe.get_all(
        "GRM Administrative Level Type",
        filters={"project": project},
        fields=["level_name"],
        order_by="level_order asc",
    )
    level_headers = [lt.level_name for lt in level_types]

    headers = (
        list(level_headers)
        + _required_user_fields_for_template()
        + _required_assignment_fields_for_template()
    )

    if fmt == "xlsx":
        from frappe.utils.xlsxutils import make_xlsx
        xlsx_io = make_xlsx([headers], "User Template")
        frappe.response["filename"] = f"user_template_{project}.xlsx"
        frappe.response["filecontent"] = xlsx_io.getvalue()
        frappe.response["type"] = "binary"
    else:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        frappe.response["filename"] = f"user_template_{project}.csv"
        frappe.response["filecontent"] = buf.getvalue()
        frappe.response["type"] = "binary"
