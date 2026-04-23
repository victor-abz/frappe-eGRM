import frappe
from frappe.model.document import Document


class EGRMSettings(Document):
    pass


def get_portal_visibility() -> dict:
    """Return portal visibility flags; defaults to disabled when the Single is missing."""
    try:
        settings = frappe.get_cached_doc("EGRM Settings")
        return {
            "enable_public_dashboard": bool(settings.enable_public_dashboard),
            "enable_public_reports": bool(settings.enable_public_reports),
        }
    except frappe.DoesNotExistError:
        return {"enable_public_dashboard": False, "enable_public_reports": False}
