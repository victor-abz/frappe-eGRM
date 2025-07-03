"""
EGRM API Version 1 - General Endpoints
--------------------------------------
This module contains general API endpoints for the mobile app.
"""

import logging

import frappe
from frappe import _
from frappe.utils import get_datetime

# Configure logging
log = logging.getLogger(__name__)


@frappe.whitelist()
def get_user_projects():
    """
    Get projects a user can access based on GRM User Project Assignment.

    Returns:
        list: List of projects the current user can access
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting projects for user: {user}")

        # Check if user is Administrator or has System Manager role (full access)
        if user == "Administrator" or "System Manager" in frappe.get_roles(user):
            projects = frappe.get_all(
                "GRM Project", fields=["name", "project_name", "description", "active"]
            )
            frappe.log(f"Admin user, returning all {len(projects)} projects")
            return {"status": "success", "data": projects}

        # Get projects assigned to the user
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters={"user": user, "active": 1},
            fields=["project"],
        )

        if not assignments:
            log.warning(f"No project assignments found for user {user}")
            return {"status": "success", "data": []}

        # Get project details for assigned projects
        project_names = [a.project for a in assignments]
        projects = frappe.get_all(
            "GRM Project",
            filters={"name": ["in", project_names], "active": 1},
            fields=["name", "project_name", "description", "active"],
        )

        frappe.log(f"Returning {len(projects)} projects for user {user}")
        return {"status": "success", "data": projects}

    except Exception as e:
        frappe.log_error(f"Error in get_user_projects: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_system_info():
    """
    Get system information including current version and configuration.

    Returns:
        dict: System information
    """
    try:
        return {
            "status": "success",
            "data": {
                "version": "1.0.0",
                "api_version": "v1",
                "system_date": get_datetime().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    except Exception as e:
        frappe.log_error(f"Error in get_system_info: {str(e)}")
        return {"status": "error", "message": str(e)}
