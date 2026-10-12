"""
eGRM API - Portal Configuration
--------------------------------
Guest-accessible endpoint that returns the public portal's visibility flags
together with the caller's identity and staff state so the React SPA can
decide which pages and cards to render, and can show who is signed in.

Public pages (Dashboard, Reports) are OFF by default; administrators opt
them in via EGRM Settings.
"""

import frappe

from egrm.egrm.doctype.egrm_settings.egrm_settings import get_portal_visibility

STAFF_ROLES = {
	"GRM Intake",
	"GRM Review",
	"GRM Assignment",
	"GRM Investigate & Resolve",
	"GRM Feedback",
	"GRM Supervise",
	"GRM Platform Administrator",
	"System Manager",
}

GUEST_USERS = ("Guest", "", None)


def _is_staff() -> bool:
	if frappe.session.user in GUEST_USERS:
		return False
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles & STAFF_ROLES)


@frappe.whitelist(allow_guest=True)
def get_portal_config() -> dict:
	"""Return visibility flags, identity and staff status for the portal."""
	visibility = get_portal_visibility()
	is_staff = _is_staff()
	is_authenticated = frappe.session.user not in GUEST_USERS

	# The portal could not show who was signed in because it was never told.
	# Without a name there is no way to offer a sign-out the user can trust,
	# which left a shared cell-office browser holding a live staff session.
	full_name = frappe.utils.get_fullname(frappe.session.user) if is_authenticated else ""

	return {
		"is_staff": is_staff,
		"is_authenticated": is_authenticated,
		"user": frappe.session.user if is_authenticated else "",
		"full_name": full_name,
		# The dashboard flag is still bypassed for staff, but the bypass is
		# reported separately so the navbar can badge the link. An admin who
		# switches a page off must be able to see that it went off; a silent
		# bypass makes the only person who ever tests the control the one
		# person it never applies to.
		"show_dashboard": is_staff or visibility["enable_public_dashboard"],
		"dashboard_staff_preview": is_staff and not visibility["enable_public_dashboard"],
		# Reports carry programme-level detail that is published deliberately
		# or not at all, so the flag is authoritative for everyone. There is
		# no staff bypass here: staff read reports in the desk, not here.
		"show_reports": bool(visibility["enable_public_reports"]),
		"reports_staff_preview": False,
		"flags": visibility,
	}
