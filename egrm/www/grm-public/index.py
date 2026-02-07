"""
GRM Public Homepage
Provides dynamic context for public homepage
"""

import frappe


def get_context(context):
    context.no_cache = 1

    # Get active projects
    projects = frappe.get_all(
        "GRM Project",
        filters={"is_active": 1},
        fields=["name", "title", "description"]
    )

    context.projects = projects
    context.site_url = frappe.utils.get_url()
