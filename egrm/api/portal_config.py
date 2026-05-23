"""
eGRM API - Portal Configuration
--------------------------------
Guest-accessible endpoint that returns the public portal's visibility flags
together with the caller's authentication / staff state so the React SPA
can decide which pages and cards to render.

Public pages (Dashboard, Reports) are OFF by default; administrators opt
them in via EGRM Settings. Staff (any authenticated user with a GRM role
or System Manager) always see every page regardless of the flags.
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


def _is_staff() -> bool:
    if frappe.session.user in ("Guest", "", None):
        return False
    roles = set(frappe.get_roles(frappe.session.user))
    return bool(roles & STAFF_ROLES)


@frappe.whitelist(allow_guest=True)
def get_portal_config() -> dict:
    """Return visibility flags and staff status for the GRM public portal."""
    visibility = get_portal_visibility()
    is_staff = _is_staff()

    return {
        "is_staff": is_staff,
        "is_authenticated": frappe.session.user not in ("Guest", "", None),
        # Staff bypass the gate; guests only see a page when its flag is enabled.
        "show_dashboard": is_staff or visibility["enable_public_dashboard"],
        "show_reports": is_staff or visibility["enable_public_reports"],
        "flags": visibility,
    }
