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
def accept_issue(issue):
    """
    Accept an issue and assign it to the current user
    """
    try:
        if not issue:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if user is assigned to the issue
        if doc.assignee != frappe.session.user:
            frappe.throw(_("You are not assigned to this issue"))

        # Get open status for the project
        open_status = get_open_status(doc.project)
        if not open_status:
            frappe.throw(_("No open status found for this project"))

        # Update status to open
        doc.status = open_status
        doc.accepted_date = now_datetime()

        # Add comment and log
        comment_text = _("Issue was accepted by {0}").format(frappe.session.user)
        log_text = _("Issue accepted and assigned for processing")
        add_comment_and_log(doc, comment_text, log_text, "Accepted issue")

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error accepting issue: {str(e)}")
        frappe.throw(_("Error accepting issue: {0}").format(str(e)))
        return False


@frappe.whitelist()
def reject_issue(issue, reason):
    """
    Reject an issue with a reason
    """
    try:
        if not issue or not reason:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if user is assigned to the issue
        if doc.assignee != frappe.session.user:
            frappe.throw(_("You are not assigned to this issue"))

        # Get rejected status for the project
        rejected_status = get_rejected_status(doc.project)
        if not rejected_status:
            frappe.throw(_("No rejected status found for this project"))

        # Update rejection fields
        doc.status = rejected_status
        doc.reject_reason = reason
        doc.rejected_date = now_datetime()
        doc.rejected_by = frappe.session.user

        # Add comment and log
        comment_text = _("Issue was rejected by {0}, reason: {1}").format(
            frappe.session.user, reason
        )
        log_text = _("Issue rejected with provided reason")
        add_comment_and_log(doc, comment_text, log_text, "Rejected issue")

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error rejecting issue: {str(e)}")
        frappe.throw(_("Error rejecting issue: {0}").format(str(e)))
        return False


@frappe.whitelist()
def record_steps(issue, steps):
    """
    Record steps taken on an issue
    """
    try:
        if not issue or not steps:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if user is assigned to the issue
        if doc.assignee != frappe.session.user:
            frappe.throw(_("You are not assigned to this issue"))

        # Add comment (use actual user input)
        doc.append(
            "grm_issue_comment",
            {"user": frappe.session.user, "comment": steps},
        )

        # Add log entry with action tracking
        doc.append(
            "grm_issue_log",
            {
                "text": steps,
                "user": frappe.session.user,
                "timestamp": now_datetime(),
                "action_taken": _("Added steps"),
                "action_taken_by": frappe.session.user,
                "action_taken_date": now_datetime(),
            },
        )

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error recording steps: {str(e)}")
        frappe.throw(_("Error recording steps: {0}").format(str(e)))
        return False


@frappe.whitelist()
def record_resolution(issue, resolution):
    """
    Record resolution for an issue and mark it as resolved
    """
    try:
        if not issue or not resolution:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Check if user is assigned to the issue
        if doc.assignee != frappe.session.user:
            frappe.throw(_("You are not assigned to this issue"))

        # Get final status for the project
        final_status = get_final_status(doc.project)
        if not final_status:
            frappe.throw(_("No final status found for this project"))

        # Update resolution fields
        doc.status = final_status
        doc.resolution_text = resolution
        doc.resolved_by = frappe.session.user
        doc.resolution_date = now_datetime()

        # Calculate resolution days
        if doc.issue_date:
            delta = doc.resolution_date - doc.issue_date
            doc.resolution_days = delta.days

        # Add comment and log
        comment_text = _("Issue was resolved by {0}").format(frappe.session.user)
        log_text = _("Issue has been marked as resolved")
        add_comment_and_log(doc, comment_text, log_text, "Resolved issue")

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error recording resolution: {str(e)}")
        frappe.throw(_("Error recording resolution: {0}").format(str(e)))
        return False


@frappe.whitelist()
def rate_issue(issue, rating, comment):
    """
    Rate an issue (citizen feedback)
    """
    try:
        if not issue or not rating or not comment:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Validate rating
        rating = int(rating)
        if rating < 1 or rating > 5:
            frappe.throw(_("Rating must be between 1 and 5"))

        # Update rating fields
        doc.rating = rating
        doc.rated_date = now_datetime()

        # Add comment and log
        comment_text = _("Issue was rated by citizen, rating: {0}").format(rating)
        log_text = _("Citizen has provided feedback rating")
        add_comment_and_log(doc, comment_text, log_text, "Rated issue")

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error rating issue: {str(e)}")
        frappe.throw(_("Error rating issue: {0}").format(str(e)))
        return False


@frappe.whitelist()
def appeal_issue(issue, comment):
    """
    Submit an appeal for an issue
    """
    try:
        if not issue or not comment:
            frappe.throw(_("Missing required parameters"))

        # Get the issue document
        doc = frappe.get_doc("GRM Issue", issue)
        if not doc:
            frappe.throw(_("Issue not found"))

        # Get open status to reopen the issue
        open_status = get_open_status(doc.project)
        if not open_status:
            frappe.throw(_("No open status found for this project"))

        # Update appeal fields
        doc.appeal_submitted = 1
        doc.appeal_date = now_datetime()
        doc.status = open_status  # Reopen the issue

        # Add comment and log
        comment_text = _("Appeal submitted by citizen")
        log_text = _("Appeal has been submitted for review")
        add_comment_and_log(doc, comment_text, log_text, "Submitted appeal")

        # Save the document
        doc.save()

        return True
    except Exception as e:
        frappe.log_error(f"Error submitting appeal: {str(e)}")
        frappe.throw(_("Error submitting appeal: {0}").format(str(e)))
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


def get_open_status(project):
    """
    Get open status for a project
    """
    try:
        if not project:
            return None

        # Get open status
        status = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.open_status = 1
            LIMIT 1
        """,
            project,
            as_dict=1,
        )

        return status[0].name if status else None
    except Exception as e:
        frappe.log_error(f"Error getting open status: {str(e)}")
        return None


def get_final_status(project):
    """
    Get final status for a project
    """
    try:
        if not project:
            return None

        # Get final status
        status = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.final_status = 1
            LIMIT 1
        """,
            project,
            as_dict=1,
        )

        return status[0].name if status else None
    except Exception as e:
        frappe.log_error(f"Error getting final status: {str(e)}")
        return None


def get_rejected_status(project):
    """
    Get rejected status for a project
    """
    try:
        if not project:
            return None

        # Get rejected status
        status = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.rejected_status = 1
            LIMIT 1
        """,
            project,
            as_dict=1,
        )

        return status[0].name if status else None
    except Exception as e:
        frappe.log_error(f"Error getting rejected status: {str(e)}")
        return None


def add_comment_and_log(doc, comment, log_text, action_type=None):
    """
    Add a comment and log entry to an issue
    """
    try:
        # Add comment
        doc.append(
            "grm_issue_comment", {"user": frappe.session.user, "comment": comment}
        )

        # Add log entry
        log_entry = {
            "text": log_text,
            "user": frappe.session.user,
            "timestamp": now_datetime(),
        }

        # Add action tracking fields if provided
        if action_type:
            log_entry["action_taken"] = action_type
            log_entry["action_taken_by"] = frappe.session.user
            log_entry["action_taken_date"] = now_datetime()

        doc.append("grm_issue_log", log_entry)
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
