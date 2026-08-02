"""Whitelisted endpoints for Step 9 (Users) bulk-import flow — Phase A + E.

Hosts the doctype-introspection + auto-detect endpoints consumed by the
Step 9 column-mapper UI:

- ``get_assignment_field_meta(project)`` — picker options for the
  source-header → target-field dropdown plus the project's level types
  and active roles (Phase A).
- ``auto_detect_user_import_mapping(project, file_url)`` — read the
  uploaded CSV/XLSX and propose a starting mapping with validation
  (Phase E.4).

Sibling modules (kept under the 400-line cap, plan §Engineering
Conventions clause 4):

- Phase B Data Import wrappers — ``grm_project_wizard_user_data_import.py``
- Phase C list/edit/bulk endpoints — ``grm_project_wizard_user_assignments.py``

All endpoints are re-exported from ``grm_project_wizard.py`` so the JS
RPC paths
(``egrm.egrm.page.grm_project_wizard.grm_project_wizard.<method>``)
keep working unchanged.
"""

from __future__ import annotations

import frappe


def _require_wizard_role() -> None:
	"""Lazy-import shim to avoid a circular import with ``grm_project_wizard``.

	The wizard module re-exports our endpoints at the bottom of its own
	body; importing ``_require_wizard_role`` at module top would close
	the cycle and fail with a partially-initialized module error when
	this file is imported first (e.g. by a test).
	"""
	from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
		_require_wizard_role as _impl,
	)

	return _impl()


# Field types that have no business showing up in a CSV mapper picker:
# UI breaks (Section/Column/Tab) cannot carry data, and Tables are flattened
# via their own child doctype rather than a single column.
_HIDDEN_MAPPER_FIELDTYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
	"Table",
	"Table MultiSelect",
	"Button",
	"HTML",
	"Heading",
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
		out.append(
			{
				"fieldname": f.fieldname,
				"label": f.label or f.fieldname,
				"fieldtype": f.fieldtype,
				"reqd": int(getattr(f, "reqd", 0) or 0),
				"options": f.options or None,
				"read_only": int(getattr(f, "read_only", 0) or 0),
			}
		)
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


# --- Phase E.4 -------------------------------------------------------------


@frappe.whitelist()
def auto_detect_user_import_mapping(project: str, file_url: str) -> dict:
	"""Read the uploaded file's headers and propose a column mapping.

	Returns ``{headers, mapping, validation, project_meta, preview_rows,
	total_rows}`` so the Step 9 mapper UI can render the table without a
	second round-trip. ``mapping`` follows the canonical
	``{header: {target, level_type, ...}}`` shape produced by
	``egrm.services.user_import.auto_detect_mapping`` so the user can
	edit it inline before submitting to ``prepare_user_import``.

	Imports are deferred to dodge the circular dependency on
	``grm_project_wizard_user_data_import`` (which imports us at
	module load).
	"""
	_require_wizard_role()

	project = (project or "").strip()
	if not project:
		frappe.throw(frappe._("project is required"))
	if not frappe.db.exists("GRM Project", project):
		frappe.throw(frappe._("Project {0} not found").format(project))

	from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import import (
		read_uploaded_file,
	)
	from egrm.services.user_import import auto_detect_mapping, validate_mapping

	headers, rows = read_uploaded_file(file_url)
	project_meta = get_assignment_field_meta(project)
	mapping = auto_detect_mapping(headers, project_meta)
	validation = validate_mapping(mapping, project_meta)

	# Send a small preview (first 5 data rows) so the mapper UI can show
	# a sample-cell column next to each source header.
	preview_rows = rows[:5]

	return {
		"headers": headers,
		"mapping": mapping,
		"validation": validation,
		"project_meta": project_meta,
		"preview_rows": preview_rows,
		"total_rows": len(rows),
	}
