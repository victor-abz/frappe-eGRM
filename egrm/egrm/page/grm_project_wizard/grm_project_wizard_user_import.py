"""Whitelisted endpoints for Step 9 (Users) bulk-import flow.

Split out from ``grm_project_wizard.py`` per plan §Engineering Conventions
clause 4 (modules ≤ 400 lines). Phase A only adds doctype introspection;
later phases (B–E) will land:

- ``prepare_user_import`` — calls ``services.user_import.materialize_staged_csv``
  and creates the wrapping ``Data Import`` record.
- ``start_user_import`` — calls Frappe's
  ``form_start_import``.
- ``poll_user_import`` — returns Data Import status / log preview for the
  Step 9 UI to render inline.
- ``download_user_template`` — generates a project-tailored CSV/XLSX skeleton.

Endpoints are re-exported from ``grm_project_wizard.py`` so the JS RPC
paths (``egrm.egrm.page.grm_project_wizard.grm_project_wizard.<method>``)
keep working.
"""

from __future__ import annotations

import frappe

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
    _require_wizard_role,
)

# Field types that have no business showing up in a CSV mapper picker:
# UI breaks (Section/Column/Tab) cannot carry data, and Tables are flattened
# via their own child doctype rather than a single column.
_HIDDEN_MAPPER_FIELDTYPES = {
    "Section Break", "Column Break", "Tab Break",
    "Table", "Table MultiSelect",
    "Button", "HTML", "Heading",
}


def _serialize_field_meta(doctype: str) -> list[dict]:
    """Return the mapper-relevant field meta rows for ``doctype``.

    Always reads from ``frappe.get_meta(...)`` — never duplicates the
    ``reqd: 1`` flag as a constant in JS or Python (plan §Engineering
    Conventions clause 2: "Doctype is source of truth").
    """
    out: list[dict] = []
    for f in frappe.get_meta(doctype).fields:
        if not f.fieldname or f.fieldtype in _HIDDEN_MAPPER_FIELDTYPES:
            continue
        out.append({
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
            "reqd": int(getattr(f, "reqd", 0) or 0),
            "options": f.options or None,
            "read_only": int(getattr(f, "read_only", 0) or 0),
        })
    return out


@frappe.whitelist()
def get_assignment_field_meta(project: str) -> dict:
    """Return doctype meta + project's level types + project's roles.

    Consumed by the Step 9 bulk-import column-mapper UI. Three pieces:

    - ``user_fields`` / ``assignment_fields`` — picker options for the
      mapper dropdown.
    - ``project_levels`` — ordered by ``level_order ASC`` (lowest int =
      highest level, e.g. Province before District) so the mapper's
      sub-picker for ``administrative_region`` shows the natural order.
    - ``project_roles`` — active roles only, with their ``admin_level``
      Link so the single-add form can drive the cascading region picker.
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(frappe._("project is required"))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))

    project_levels = frappe.get_all(
        "GRM Administrative Level Type",
        filters={"project": project},
        fields=["name", "level_name", "level_order"],
        order_by="level_order asc",
    )
    project_roles = frappe.get_all(
        "GRM Project Role",
        filters={"project": project, "is_active": 1},
        fields=["name", "role_name", "admin_level"],
        order_by="role_name asc",
    )
    return {
        "user_fields": _serialize_field_meta("User"),
        "assignment_fields": _serialize_field_meta("GRM User Project Assignment"),
        "project_levels": project_levels,
        "project_roles": project_roles,
    }
