"""
eGRM API - App-screen permission check
---------------------------------------
Gate visibility of the eGRM tile on the Frappe v16 Apps screen
(`/apps`) and the desk app-switcher. The allowlist is the canonical L1
Frappe-Role catalog from
`docs/superpowers/plans/2026-04-25-egrm-per-project-architecture-implementation.md`
(§ Phase 1, Task 1.6) — the 6 duty roles + `GRM Platform Administrator`,
plus Frappe's `System Manager`. Membership in any one of these is
sufficient and necessary; we do not consult the database to extend it.
"""

import frappe

GRM_STAFF_ROLES: frozenset[str] = frozenset(
	{
		"System Manager",
		"GRM Platform Administrator",
		"GRM Intake",
		"GRM Review",
		"GRM Assignment",
		"GRM Investigate & Resolve",
		"GRM Feedback",
		"GRM Supervise",
	}
)


def check_app_permission() -> bool:
	if frappe.session.user in ("Guest", "", None):
		return False
	return bool(set(frappe.get_roles()) & GRM_STAFF_ROLES)
