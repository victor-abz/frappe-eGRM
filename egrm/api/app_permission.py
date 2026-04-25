"""
eGRM API - App-screen permission check
---------------------------------------
Gate visibility of the eGRM tile on the Frappe v16 Desktop / Apps screen.
A user sees the tile only if they hold a System Manager or any GRM staff role.
"""

import frappe

GRM_STAFF_ROLES = {
    "System Manager",
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
}


def check_app_permission() -> bool:
    """Return True if the current user has any GRM staff role."""
    if frappe.session.user in ("Guest", "", None):
        return False
    return bool(set(frappe.get_roles()) & GRM_STAFF_ROLES)
