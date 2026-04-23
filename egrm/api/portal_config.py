"""
eGRM API - Portal Configuration
--------------------------------
Guest-accessible endpoint that returns the public portal's visibility flags
together with the caller's authentication / staff state so the React SPA
can decide which pages and cards to render.

Staff (any authenticated user with a GRM role) always sees every page; the
flags only gate guest visitors.
"""

import frappe

from egrm.egrm.doctype.egrm_settings.egrm_settings import get_portal_visibility

STAFF_ROLES = {
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
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
        # For guests, honor the flags. Staff always see every page.
        "show_dashboard": is_staff or visibility["show_public_dashboard"],
        "show_reports": is_staff or visibility["show_public_reports"],
        "flags": visibility,
    }
