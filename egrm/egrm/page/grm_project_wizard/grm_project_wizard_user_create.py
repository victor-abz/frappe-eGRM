"""Phase D (Step 9 Users): single-add ``create_assignment`` endpoint.

Houses the one whitelisted method the Step-9 single-add form posts to.
Split out from ``grm_project_wizard_user_assignments.py`` so each module
stays under the 400-line cap (plan §Engineering Conventions clause 4).

Re-exported from ``grm_project_wizard.py`` so the JS RPC path
(``egrm.egrm.page.grm_project_wizard.grm_project_wizard.create_assignment``)
keeps working unchanged.
"""

from __future__ import annotations

import logging

import frappe
from frappe import _

logger = logging.getLogger(__name__)


def _require_wizard_role() -> None:
	"""Lazy shim — avoids a circular import with ``grm_project_wizard``,
	which re-exports our endpoint at module bottom."""
	from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
		_require_wizard_role as _impl,
	)

	return _impl()


@frappe.whitelist()
def create_assignment(
	project: str,
	user: str,
	role: str,
	administrative_region: str | None = None,
	department: str | None = None,
	position_title: str | None = None,
	is_active: bool | int | str = 1,
) -> dict:
	"""Create a single ``GRM User Project Assignment`` (Phase D single-add).

	The wizard's single-add form posts here. We pre-validate the four
	cross-doctype invariants below so the operator gets a *focused* error
	message rather than the broad "Validation Error" the doctype's
	``validate()`` would surface — and so we can fail before
	``before_insert`` allocates an activation code.

	  1. ``user`` resolves to an existing User row.
	  2. ``user`` is not already assigned to ``project`` (Phase D contract:
	     per-project uniqueness regardless of role; stricter than the
	     doctype's per-(user, project, role) uniqueness, but matches the
	     plan's "one row per user per project" UX expectation).
	  3. ``role`` belongs to ``project``.
	  4. ``administrative_region`` (if provided) belongs to ``project`` AND
	     sits at or above the role's ``admin_level`` in the level-order
	     hierarchy (lower ``level_order`` = higher in the tree). Per plan
	     §D.2: "When user picks a Project Role, the cascade resets to the
	     role's admin_level and disables levels below" — the server mirrors
	     that gate so a manually-crafted RPC can't bypass it.

	Returns ``{name, activation_code, user, role}``. ``activation_code`` is
	populated by the doctype's ``before_insert`` hook only for government-
	worker roles (duties intersecting Intake / Investigate & Resolve);
	other roles return ``None`` here.
	"""
	_require_wizard_role()

	project = (project or "").strip()
	user = (user or "").strip()
	role = (role or "").strip()
	if not project:
		frappe.throw(_("project is required"))
	if not user:
		frappe.throw(_("user is required"))
	if not role:
		frappe.throw(_("role is required"))

	# 1. User exists.
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} does not exist").format(user))

	# 2. Per-project uniqueness — Phase D contract.
	if frappe.db.exists(
		"GRM User Project Assignment",
		{"project": project, "user": user},
	):
		frappe.throw(_("User {0} is already assigned to {1}").format(user, project))

	# 3. Role belongs to the same project.
	if not frappe.db.exists("GRM Project Role", role):
		frappe.throw(_("Project Role {0} does not exist").format(role))
	role_project, role_admin_level = frappe.db.get_value("GRM Project Role", role, ["project", "admin_level"])
	if role_project != project:
		frappe.throw(_("Role {0} does not belong to project {1}").format(role, project))

	# 4. Region belongs to the same project AND respects role.admin_level.
	region = (administrative_region or "").strip() or None
	if region:
		if not frappe.db.exists("GRM Administrative Region", region):
			frappe.throw(_("Administrative Region {0} does not exist").format(region))
		region_project, region_level = frappe.db.get_value(
			"GRM Administrative Region",
			region,
			["project", "administrative_level"],
		)
		if region_project != project:
			frappe.throw(_("Region {0} does not belong to project {1}").format(region, project))
		if role_admin_level:
			# Compare level_order: lower = higher in the tree. The role's
			# admin_level is the LOWEST level the role can be assigned at,
			# so the region's level_order must be <= role's level_order.
			role_level_order = frappe.db.get_value(
				"GRM Administrative Level Type",
				role_admin_level,
				"level_order",
			)
			region_level_order = frappe.db.get_value(
				"GRM Administrative Level Type",
				region_level,
				"level_order",
			)
			if (
				role_level_order is not None
				and region_level_order is not None
				and region_level_order > role_level_order
			):
				frappe.throw(_("Region {0} sits below the role's allowed admin level").format(region))

	department_val = (department or "").strip() or None
	position_title_val = (position_title or "").strip() or None

	# Coerce is_active — REST form-encoding sends "1"/"0" strings.
	if isinstance(is_active, str):
		is_active_int = 1 if is_active.strip() in {"1", "true", "yes", "on"} else 0
	else:
		is_active_int = 1 if int(bool(is_active)) else 0

	doc = frappe.get_doc(
		{
			"doctype": "GRM User Project Assignment",
			"project": project,
			"user": user,
			"role": role,
			"administrative_region": region,
			"department": department_val,
			"position_title": position_title_val,
			"is_active": is_active_int,
		}
	).insert(ignore_permissions=False)

	logger.info(
		"create_assignment: project=%s user=%s role=%s region=%s name=%s",
		project,
		user,
		role,
		region,
		doc.name,
	)
	return {
		"name": doc.name,
		"activation_code": getattr(doc, "activation_code", None),
		"user": user,
		"role": role,
	}
