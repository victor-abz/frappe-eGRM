import frappe
from frappe.model.document import Document


class EGRMSettings(Document):
    pass


def get_portal_visibility() -> dict:
    """Return portal visibility flags; falls back to enabled if the Single is missing."""
    try:
        settings = frappe.get_cached_doc("EGRM Settings")
        return {
            "show_public_dashboard": bool(settings.show_public_dashboard),
            "show_public_reports": bool(settings.show_public_reports),
        }
    except frappe.DoesNotExistError:
        return {"show_public_dashboard": True, "show_public_reports": True}
