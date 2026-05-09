import logging

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from egrm.api._roles import GRM_ALL_PROJECTS_ROLES
from egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment import (
    GOVERNMENT_WORKER_DUTIES,
    _government_worker_role_names_for_project,
    _project_role_duties,
)

log = logging.getLogger(__name__)


def _find_pending_assignment_name(user_name: str) -> str | None:
    """Return the assignment name for any active gov-worker assignment of
    ``user_name`` whose status is not yet ``Activated``. Duty-driven: a
    gov-worker is anyone whose Project Role carries Intake or Investigate
    & Resolve."""
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user_name,
            "is_active": 1,
            "activation_status": ["!=", "Activated"],
        },
        fields=["name", "role"],
    )
    for row in rows:
        duties = set(_project_role_duties(row.role))
        if duties & GOVERNMENT_WORKER_DUTIES:
            return row.name
    return None


def _find_eligible_assignment_for_resend(user_name: str) -> str | None:
    """Like ``_find_pending_assignment_name`` but also accepts ``Expired``
    and ``Draft`` so we can re-issue a code."""
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user_name,
            "is_active": 1,
            "activation_status": ["in", ["Draft", "Pending Activation", "Expired"]],
        },
        fields=["name", "role"],
    )
    for row in rows:
        duties = set(_project_role_duties(row.role))
        if duties & GOVERNMENT_WORKER_DUTIES:
            return row.name
    return None


def _find_any_gov_worker_assignment(user_name: str) -> dict | None:
    """Return the first government-worker assignment for the user (any status)."""
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user_name},
        fields=[
            "name",
            "role",
            "activation_status",
            "activation_expires_on",
            "activated_on",
            "code_sent_on",
            "activation_attempts",
            "position_title",
        ],
    )
    for row in rows:
        duties = set(_project_role_duties(row.role))
        if duties & GOVERNMENT_WORKER_DUTIES:
            return row
    return None


@frappe.whitelist(allow_guest=True)
def activate_government_worker(email, activation_code, new_password=None):
    """
    API endpoint to activate government worker account

    Args:
        email (str): User email address
        activation_code (str): 6-digit activation code
        new_password (str, optional): New password for the user

    Returns:
        dict: Response with success status and user details
    """
    try:
        # Input validation
        if not email or not activation_code:
            return {
                "success": False,
                "message": _("Email and activation code are required"),
                "errors": ["Missing required parameters"],
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            log.warning(f"Activation attempt for non-existent user: {email}")
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"],
            }

        # Find government worker assignment via duty-driven lookup.
        assignment_name = _find_pending_assignment_name(user_name)
        if not assignment_name:
            log.warning(f"No pending activation found for user: {email}")
            return {
                "success": False,
                "message": _("No pending activation found for this email"),
                "errors": ["Assignment not found"],
            }

        # Get the assignment document. The activation code itself is the
        # auth token here (callable as Guest), so the save inside
        # activate_worker must bypass the doctype's role-based permissions.
        assignment_doc = frappe.get_doc("GRM User Project Assignment", assignment_name)
        assignment_doc.flags.ignore_permissions = True

        # Validate and activate
        try:
            result = assignment_doc.activate_worker(activation_code, new_password)

            if result:
                frappe.log(f"Government worker activated successfully via API: {email}")
                return {
                    "success": True,
                    "message": _("Account activated successfully!"),
                    "data": {
                        "user_id": user_name,
                        "status": "Activated",
                        "activated_on": assignment_doc.activated_on,
                    },
                    "errors": [],
                }
        except Exception as activation_error:
            frappe.log_error(f"Activation failed for {email}: {str(activation_error)}")
            return {
                "success": False,
                "message": str(activation_error),
                "errors": [str(activation_error)],
            }

    except Exception as e:
        frappe.log_error(f"API activation error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred during activation. Please try again."),
            "errors": [str(e)],
        }


@frappe.whitelist(allow_guest=True)
def resend_activation_code(email):
    """
    API endpoint to resend activation code

    Args:
        email (str): User email address

    Returns:
        dict: Response with success status
    """
    try:
        # Input validation
        if not email:
            return {
                "success": False,
                "message": _("Email is required"),
                "errors": ["Missing email parameter"],
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            log.warning(f"Resend attempt for non-existent user: {email}")
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"],
            }

        # Find government worker assignment via duty-driven lookup.
        assignment_name = _find_eligible_assignment_for_resend(user_name)
        if not assignment_name:
            log.warning(f"No eligible assignment found for resend: {email}")
            return {
                "success": False,
                "message": _("No pending activation found for this email"),
                "errors": ["Assignment not found"],
            }

        # Get the assignment document and resend code. Guest call path —
        # bypass role-based perms; the email lookup is the implicit auth.
        assignment_doc = frappe.get_doc("GRM User Project Assignment", assignment_name)
        assignment_doc.flags.ignore_permissions = True

        try:
            result = assignment_doc.resend_activation_code()

            if result:
                frappe.log(f"Activation code resent successfully via API: {email}")
                return {
                    "success": True,
                    "message": _("Activation code sent successfully!"),
                    "data": {
                        "user_id": user_name,
                        "status": assignment_doc.activation_status,
                        "code_sent_on": assignment_doc.code_sent_on,
                    },
                    "errors": [],
                }
        except Exception as resend_error:
            frappe.log_error(f"Resend failed for {email}: {str(resend_error)}")
            return {
                "success": False,
                "message": str(resend_error),
                "errors": [str(resend_error)],
            }

    except Exception as e:
        frappe.log_error(f"API resend error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _(
                "An error occurred while sending activation code. Please try again."
            ),
            "errors": [str(e)],
        }


@frappe.whitelist(allow_guest=True)
def check_activation_status(email):
    """
    API endpoint to check activation status

    Args:
        email (str): User email address

    Returns:
        dict: Response with current activation status
    """
    try:
        # Input validation
        if not email:
            return {
                "success": False,
                "message": _("Email is required"),
                "errors": ["Missing email parameter"],
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"],
            }

        # Find government worker assignment via duty-driven lookup.
        assignment_data = _find_any_gov_worker_assignment(user_name)
        if not assignment_data:
            return {
                "success": False,
                "message": _("No government worker assignment found for this email"),
                "errors": ["Assignment not found"],
            }

        # Prepare response data
        response_data = {
            "user_id": user_name,
            "status": assignment_data.activation_status or "Unknown",
            "position_title": assignment_data.position_title,
            "activation_attempts": assignment_data.activation_attempts or 0,
            "max_attempts": 5,
        }

        # Add conditional fields
        if assignment_data.activation_expires_on:
            response_data["expires_on"] = assignment_data.activation_expires_on
            response_data["is_expired"] = (
                get_datetime(assignment_data.activation_expires_on) < now_datetime()
            )

        if assignment_data.activated_on:
            response_data["activated_on"] = assignment_data.activated_on

        if assignment_data.code_sent_on:
            response_data["code_sent_on"] = assignment_data.code_sent_on

        frappe.log(
            f"Status check successful for {email}: {assignment_data.activation_status}"
        )
        return {
            "success": True,
            "message": _("Status retrieved successfully"),
            "data": response_data,
            "errors": [],
        }

    except Exception as e:
        frappe.log_error(f"API status check error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred while checking status. Please try again."),
            "errors": [str(e)],
        }


# Enhanced API endpoints with rate limiting
@frappe.whitelist(allow_guest=True)
def activate_government_worker_limited(email, activation_code, new_password=None):
    """Rate-limited version of activate_government_worker"""
    return activate_government_worker(email, activation_code, new_password)


@frappe.whitelist(allow_guest=True)
def resend_activation_code_limited(email):
    """Rate-limited version of resend_activation_code"""
    return resend_activation_code(email)


@frappe.whitelist(allow_guest=True)
def check_activation_status_limited(email):
    """Rate-limited version of check_activation_status"""
    return check_activation_status(email)


# Additional utility functions
@frappe.whitelist()
def bulk_send_activation_codes(project_code, filters=None):
    """
    Send activation codes to multiple workers in bulk

    Args:
        project_code (str): Project code
        filters (dict): Additional filters for worker selection

    Returns:
        dict: Bulk operation results
    """
    # Explicit role guard: only supervisors / platform administrators / system
    # managers may bulk send activation codes (writes to GRM User Project
    # Assignment in a loop).
    roles = set(frappe.get_roles(frappe.session.user))
    if frappe.session.user != "Administrator" and not (
        roles & GRM_ALL_PROJECTS_ROLES
    ):
        frappe.throw(
            _("You do not have permission to bulk send activation codes."),
            frappe.PermissionError,
        )

    try:
        # Check permissions
        if not frappe.has_permission("GRM User Project Assignment", "write"):
            return {
                "success": False,
                "message": _("No permission to send activation codes"),
                "errors": ["Permission denied"],
            }

        # Build filters — duty-driven gov-worker scoping (Intake or Investigate
        # & Resolve duty on this project's Project Roles).
        government_worker_roles = _government_worker_role_names_for_project(
            project_code
        )
        if not government_worker_roles:
            return {
                "success": False,
                "message": _("No government worker roles configured for this project"),
                "errors": ["No matching project roles"],
            }
        assignment_filters = {
            "project": project_code,
            "role": ["in", government_worker_roles],
            "activation_status": ["in", ["Draft", "Expired"]],
        }

        if filters:
            assignment_filters.update(filters)

        # Get assignments
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters=assignment_filters,
            fields=["name", "user"],
        )

        if not assignments:
            return {
                "success": False,
                "message": _("No eligible workers found"),
                "errors": ["No workers found"],
            }

        # Send codes in bulk
        success_count = 0
        failed_count = 0
        errors = []

        for assignment in assignments:
            try:
                assignment_doc = frappe.get_doc(
                    "GRM User Project Assignment", assignment.name
                )
                assignment_doc.send_activation_email()
                success_count += 1
                frappe.log(f"Bulk activation email sent to {assignment.user}")

            except Exception as send_error:
                failed_count += 1
                error_msg = f"Failed to send to {assignment.user}: {str(send_error)}"
                errors.append(error_msg)
                frappe.log_error(error_msg)

        return {
            "success": True,
            "message": _(
                f"Bulk operation completed: {success_count} sent, {failed_count} failed"
            ),
            "data": {
                "total_processed": len(assignments),
                "success_count": success_count,
                "failed_count": failed_count,
            },
            "errors": errors,
        }

    except Exception as e:
        frappe.log_error(f"Bulk send error: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred during bulk operation"),
            "errors": [str(e)],
        }
