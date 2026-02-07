"""
Public Tracking API
Allows citizens to track complaints by tracking code (no auth required)
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def track_complaint(tracking_code):
    """
    Track complaint status by tracking code

    Args:
        tracking_code (str): Unique tracking code

    Returns:
        dict: Complaint status (anonymized, no PII)
    """
    if not tracking_code:
        return {
            "status": "error",
            "message": _("Tracking code is required")
        }

    try:
        # Find issue by tracking code
        issue_name = frappe.db.get_value("GRM Issue", {"tracking_code": tracking_code}, "name")

        if not issue_name:
            return {
                "status": "error",
                "message": _("Complaint not found. Please check your tracking code.")
            }

        # Get issue data (only public-safe fields)
        issue = frappe.db.get_value(
            "GRM Issue",
            issue_name,
            [
                "tracking_code",
                "status",
                "creation",
                "category",
                "resolution_date",
                "appeal_submitted",
                "accepted_date",
            ],
            as_dict=True
        )

        # Get status name
        status_name = ""
        if issue.status:
            status_name = frappe.db.get_value("GRM Issue Status", issue.status, "status_name") or ""

        # Get category name
        category_name = ""
        if issue.category:
            category_name = frappe.db.get_value("GRM Issue Category", issue.category, "category_name") or ""

        # Build response (NO PII)
        response = {
            "status": "success",
            "data": {
                "tracking_code": issue.tracking_code,
                "status": status_name,
                "category": category_name,
                "submission_date": issue.creation.strftime("%Y-%m-%d %H:%M") if issue.creation else None,
                "acknowledged_date": issue.accepted_date.strftime("%Y-%m-%d") if issue.accepted_date else None,
                "resolution_date": issue.resolution_date.strftime("%Y-%m-%d") if issue.resolution_date else None,
                "appeal_submitted": issue.appeal_submitted or False
            }
        }

        return response

    except Exception as e:
        frappe.log_error(f"Tracking error: {str(e)}", "Public Tracking API")
        return {
            "status": "error",
            "message": _("Error retrieving complaint status")
        }
