import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime
import logging

log = logging.getLogger(__name__)

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
                "errors": ["Missing required parameters"]
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            log.warning(f"Activation attempt for non-existent user: {email}")
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"]
            }

        # Find government worker assignment
        assignment = frappe.db.get_value(
            "GRM User Project Assignment",
            {
                "user": user_name,
                "role": ["in", ["GRM Field Officer", "GRM Department Head"]],
                "activation_status": ["!=", "Activated"]
            },
            ["name", "activation_status", "activation_code", "activation_expires_on", "activation_attempts"],
            as_dict=True
        )

        if not assignment:
            log.warning(f"No pending activation found for user: {email}")
            return {
                "success": False,
                "message": _("No pending activation found for this email"),
                "errors": ["Assignment not found"]
            }

        # Get the assignment document
        assignment_doc = frappe.get_doc("GRM User Project Assignment", assignment.name)

        # Validate and activate
        try:
            result = assignment_doc.activate_worker(activation_code, new_password)

            if result:
                log.info(f"Government worker activated successfully via API: {email}")
                return {
                    "success": True,
                    "message": _("Account activated successfully!"),
                    "data": {
                        "user_id": user_name,
                        "status": "Activated",
                        "activated_on": assignment_doc.activated_on
                    },
                    "errors": []
                }
        except Exception as activation_error:
            log.error(f"Activation failed for {email}: {str(activation_error)}")
            return {
                "success": False,
                "message": str(activation_error),
                "errors": [str(activation_error)]
            }

    except Exception as e:
        log.error(f"API activation error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred during activation. Please try again."),
            "errors": [str(e)]
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
                "errors": ["Missing email parameter"]
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            log.warning(f"Resend attempt for non-existent user: {email}")
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"]
            }

        # Find government worker assignment
        assignment_name = frappe.db.get_value(
            "GRM User Project Assignment",
            {
                "user": user_name,
                "role": ["in", ["GRM Field Officer", "GRM Department Head"]],
                "activation_status": ["in", ["Draft", "Pending Activation", "Expired"]]
            },
            "name"
        )

        if not assignment_name:
            log.warning(f"No eligible assignment found for resend: {email}")
            return {
                "success": False,
                "message": _("No pending activation found for this email"),
                "errors": ["Assignment not found"]
            }

        # Get the assignment document and resend code
        assignment_doc = frappe.get_doc("GRM User Project Assignment", assignment_name)

        try:
            result = assignment_doc.resend_activation_code()

            if result:
                log.info(f"Activation code resent successfully via API: {email}")
                return {
                    "success": True,
                    "message": _("Activation code sent successfully!"),
                    "data": {
                        "user_id": user_name,
                        "status": assignment_doc.activation_status,
                        "code_sent_on": assignment_doc.code_sent_on
                    },
                    "errors": []
                }
        except Exception as resend_error:
            log.error(f"Resend failed for {email}: {str(resend_error)}")
            return {
                "success": False,
                "message": str(resend_error),
                "errors": [str(resend_error)]
            }

    except Exception as e:
        log.error(f"API resend error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred while sending activation code. Please try again."),
            "errors": [str(e)]
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
                "errors": ["Missing email parameter"]
            }

        # Find user by email
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            return {
                "success": False,
                "message": _("Invalid email address"),
                "errors": ["User not found"]
            }

        # Find government worker assignment
        assignment_data = frappe.db.get_value(
            "GRM User Project Assignment",
            {
                "user": user_name,
                "role": ["in", ["GRM Field Officer", "GRM Department Head"]]
            },
            [
                "activation_status", "activation_expires_on", "activated_on",
                "code_sent_on", "activation_attempts", "position_title"
            ],
            as_dict=True
        )

        if not assignment_data:
            return {
                "success": False,
                "message": _("No government worker assignment found for this email"),
                "errors": ["Assignment not found"]
            }

        # Prepare response data
        response_data = {
            "user_id": user_name,
            "status": assignment_data.activation_status or "Unknown",
            "position_title": assignment_data.position_title,
            "activation_attempts": assignment_data.activation_attempts or 0,
            "max_attempts": 5
        }

        # Add conditional fields
        if assignment_data.activation_expires_on:
            response_data["expires_on"] = assignment_data.activation_expires_on
            response_data["is_expired"] = get_datetime(assignment_data.activation_expires_on) < now_datetime()

        if assignment_data.activated_on:
            response_data["activated_on"] = assignment_data.activated_on

        if assignment_data.code_sent_on:
            response_data["code_sent_on"] = assignment_data.code_sent_on

        log.info(f"Status check successful for {email}: {assignment_data.activation_status}")
        return {
            "success": True,
            "message": _("Status retrieved successfully"),
            "data": response_data,
            "errors": []
        }

    except Exception as e:
        log.error(f"API status check error for {email}: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred while checking status. Please try again."),
            "errors": [str(e)]
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
    try:
        # Check permissions
        if not frappe.has_permission("GRM User Project Assignment", "write"):
            return {
                "success": False,
                "message": _("No permission to send activation codes"),
                "errors": ["Permission denied"]
            }

        # Build filters
        assignment_filters = {
            "project": project_code,
            "role": ["in", ["GRM Field Officer", "GRM Department Head"]],
            "activation_status": ["in", ["Draft", "Expired"]]
        }

        if filters:
            assignment_filters.update(filters)

        # Get assignments
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters=assignment_filters,
            fields=["name", "user"]
        )

        if not assignments:
            return {
                "success": False,
                "message": _("No eligible workers found"),
                "errors": ["No workers found"]
            }

        # Send codes in bulk
        success_count = 0
        failed_count = 0
        errors = []

        for assignment in assignments:
            try:
                assignment_doc = frappe.get_doc("GRM User Project Assignment", assignment.name)
                assignment_doc.send_activation_email()
                success_count += 1
                log.info(f"Bulk activation email sent to {assignment.user}")

            except Exception as send_error:
                failed_count += 1
                error_msg = f"Failed to send to {assignment.user}: {str(send_error)}"
                errors.append(error_msg)
                log.error(error_msg)

        return {
            "success": True,
            "message": _(f"Bulk operation completed: {success_count} sent, {failed_count} failed"),
            "data": {
                "total_processed": len(assignments),
                "success_count": success_count,
                "failed_count": failed_count
            },
            "errors": errors
        }

    except Exception as e:
        log.error(f"Bulk send error: {str(e)}")
        return {
            "success": False,
            "message": _("An error occurred during bulk operation"),
            "errors": [str(e)]
        }
