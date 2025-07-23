import frappe
from frappe.model.document import Document

class AndroidAppVersion(Document):
    pass

def has_website_permission(doc, ptype, user, verbose=False):
    """Allow anyone to access the download page"""
    return True
