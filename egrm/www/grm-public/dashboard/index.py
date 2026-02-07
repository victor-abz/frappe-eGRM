"""
GRM Public Dashboard
Dynamic context for public metrics dashboard
"""

import frappe
from egrm.api.public_metrics import get_public_dashboard


def get_context(context):
    context.no_cache = 1

    project_id = frappe.form_dict.get("project")
    date_range = frappe.form_dict.get("range", "30d")

    metrics_result = get_public_dashboard(project_id, date_range)

    if metrics_result.get("status") == "success":
        context.metrics = metrics_result.get("data", {})
    else:
        context.metrics = {}
        context.error = metrics_result.get("message")

    context.projects = frappe.get_all(
        "GRM Project",
        filters={"is_active": 1},
        fields=["name", "title"]
    )

    context.selected_project = project_id
    context.selected_range = date_range
