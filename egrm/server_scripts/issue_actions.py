import logging

import frappe
from frappe import _
from frappe.utils import now_datetime

log = logging.getLogger(__name__)


@frappe.whitelist()
def change_status(issue, status, comment):
    """
    Change the status of an issue and add a comment
    """
    try:
        if not issue or not status or not comment:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if status is allowed
        if not is_valid_status(doc.project, status):
            frappe.throw(_("Invalid status for this project"))

        # Get old status for logging
        old_status = doc.status

        # Update status
        doc.status = status

        # Add log entry
        log_text = _("Changed status from {0} to {1}: {2}").format(
            old_status, status, comment
        )
        add_comment_and_log(doc, comment, log_text)

        # Check if this is a resolution status
        if is_final_status(status):
            # Set resolution date and days
            doc.resolution_date = now_datetime()

            # Calculate resolution days
            if doc.created_date:
                import datetime

                delta = doc.resolution_date - doc.created_date
                doc.resolution_days = delta.days

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error changing issue status: {str(e)}")
        frappe.throw(_("Error changing status: {0}").format(str(e)))
        return False


@frappe.whitelist()
def escalate_issue(issue, reason, due_at):
    """
    Escalate an issue and add an escalation reason
    """
    try:
        if not issue or not reason or not due_at:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Set escalation flag
        doc.escalate_flag = 1

        # Add escalation reason
        doc.append(
            "grm_issue_escalation_reason",
            {"user": frappe.session.user, "comment": reason, "due_at": due_at},
        )

        # Add log entry
        log_text = _("Issue escalated: {0}").format(reason)
        doc.append(
            "grm_issue_log",
            {
                "text": log_text,
                "user": frappe.session.user,
                "timestamp": now_datetime(),
            },
        )

        # Get escalation department for the category
        category_doc = frappe.get_doc("GRM Issue Category", doc.category)
        if category_doc.assigned_escalation_department:
            # Get department head
            dept_head = frappe.db.get_value(
                "GRM Issue Department",
                category_doc.assigned_escalation_department,
                "head",
            )

            if dept_head:
                # Assign to department head
                doc.assignee = dept_head

                # Add log entry
                log_text = _(
                    "Issue assigned to escalation department head: {0}"
                ).format(dept_head)
                doc.append(
                    "grm_issue_log",
                    {
                        "text": log_text,
                        "user": frappe.session.user,
                        "timestamp": now_datetime(),
                    },
                )

                # Notify department head
                send_notification(
                    dept_head,
                    _("Issue Escalated"),
                    _("Issue {0} has been escalated to you").format(doc.name),
                )

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error escalating issue: {str(e)}")
        frappe.throw(_("Error escalating issue: {0}").format(str(e)))
        return False


@frappe.whitelist()
def reassign_issue(issue, assignee, comment):
    """
    Reassign an issue to another user
    """
    try:
        if not issue or not assignee or not comment:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if assignee has access to this project
        if not has_project_access(assignee, doc.project):
            frappe.throw(_("Selected user does not have access to this project"))

        # Get old assignee for logging
        old_assignee = doc.assignee or _("Unassigned")

        # Update assignee
        doc.assignee = assignee

        # Add log entry
        log_text = _("Reassigned from {0} to {1}: {2}").format(
            old_assignee, assignee, comment
        )
        add_comment_and_log(doc, comment, log_text)

        # Notify new assignee
        send_notification(
            assignee,
            _("Issue Assigned"),
            _("Issue {0} has been assigned to you: {1}").format(doc.name, comment),
        )

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error reassigning issue: {str(e)}")
        frappe.throw(_("Error reassigning issue: {0}").format(str(e)))
        return False


@frappe.whitelist()
def collect_feedback(issue, resolution_accepted, rating, comment):
    """
    Collect citizen feedback on issue resolution
    """
    try:
        if not issue or not resolution_accepted or rating is None or not comment:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Validate rating
        rating = int(rating)
        if rating < 0 or rating > 5:
            frappe.throw(_("Rating must be between 0 and 5"))

        # Update feedback fields
        doc.resolution_accepted = resolution_accepted
        doc.rating = rating

        # Add comment
        doc.append(
            "grm_issue_comment",
            {
                "user": frappe.session.user,
                "comment": _("Citizen feedback: {0}").format(comment),
            },
        )

        # Add log entry
        status_text = _("Accepted") if resolution_accepted == "1" else _("Rejected")
        log_text = _("Citizen feedback collected: Resolution {0}, Rating: {1}").format(
            status_text, rating
        )
        doc.append(
            "grm_issue_log",
            {
                "text": log_text,
                "user": frappe.session.user,
                "timestamp": now_datetime(),
            },
        )

        # If resolution was rejected, reopen the issue
        if resolution_accepted == "2":  # Rejected
            # Get initial status
            initial_status = get_initial_status(doc.project)

            if initial_status:
                doc.status = initial_status

                # Add log entry
                log_text = _("Issue reopened due to resolution rejection")
                doc.append(
                    "grm_issue_log",
                    {
                        "text": log_text,
                        "user": frappe.session.user,
                        "timestamp": now_datetime(),
                    },
                )

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error collecting feedback: {str(e)}")
        frappe.throw(_("Error collecting feedback: {0}").format(str(e)))
        return False


# Helper functions


def is_valid_status(project, status):
    """
    Check if a status is valid for a project
    """
    try:
        if not project or not status:
            return False

        # Check if status exists and is linked to the project
        status_exists = frappe.db.exists(
            "GRM Project Link", {"parent": status, "project": project}
        )

        return status_exists is not None
    except Exception as e:
        frappe.log_error(f"Error checking valid status: {str(e)}")
        return False


def is_final_status(status):
    """
    Check if a status is a final status
    """
    try:
        if not status:
            return False

        final_status = frappe.db.get_value("GRM Issue Status", status, "final_status")
        return final_status
    except Exception as e:
        frappe.log_error(f"Error checking final status: {str(e)}")
        return False


def has_project_access(user, project):
    """
    Check if a user has access to a project
    """
    try:
        if not user or not project:
            return False

        # Check if user is assigned to the project
        assignment_exists = frappe.db.exists(
            "GRM User Project Assignment",
            {"user": user, "project": project, "is_active": 1},
        )

        return assignment_exists is not None
    except Exception as e:
        frappe.log_error(f"Error checking project access: {str(e)}")
        return False


def get_initial_status(project):
    """
    Get initial status for a project
    """
    try:
        if not project:
            return None

        # Get initial status
        status = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.initial_status = 1
            LIMIT 1
        """,
            project,
            as_dict=1,
        )

        return status[0].name if status else None
    except Exception as e:
        frappe.log_error(f"Error getting initial status: {str(e)}")
        return None


def add_comment_and_log(doc, comment, log_text):
    """
    Add a comment and log entry to an issue
    """
    try:
        # Add comment
        doc.append(
            "grm_issue_comment", {"user": frappe.session.user, "comment": comment}
        )

        # Add log entry
        doc.append(
            "grm_issue_log",
            {
                "text": log_text,
                "user": frappe.session.user,
                "timestamp": now_datetime(),
            },
        )
    except Exception as e:
        frappe.log_error(f"Error adding comment and log: {str(e)}")
        raise


def send_notification(user, subject, message):
    """
    Send a notification to a user
    """
    try:
        frappe.sendmail(
            recipients=[user],
            sender=frappe.session.user,
            subject=subject,
            message=message,
            reference_doctype="GRM Issue",
        )
    except Exception as e:
        frappe.log_error(f"Error sending notification: {str(e)}")
        # Don't raise exception for notification errors
