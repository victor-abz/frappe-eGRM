"""
GRM Public Complaint Tracking
Context for tracking page
"""

import frappe


def get_context(context):
    context.no_cache = 1
    context.site_url = frappe.utils.get_url()
