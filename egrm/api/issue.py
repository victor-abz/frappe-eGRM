"""
EGRM API - Issue Management Endpoints
-----------------------------------
This module contains API endpoints for managing GRM issues.
"""

import json
import logging

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

from egrm.api.sync import create_issue_from_sync  # Import the sync creation function

# Configure logging
log = logging.getLogger(__name__)


@frappe.whitelist()
def list(
    project_id=None, status=None, assignee=None, reporter=None, limit=50, offset=0
):
    """
    List issues with filters

    Args:
        project_id (str, optional): Project ID
        status (str, optional): Status filter
        assignee (str, optional): Assignee filter
        reporter (str, optional): Reporter filter
        limit (int): Number of records to return
        offset (int): Offset for pagination

    Returns:
        dict: List of issues
    """
    try:
        user = frappe.session.user
        frappe.log(f"Listing issues for user: {user}")

        # Build filters
        filters = {}
        if project_id:
            filters["project"] = project_id
        if status:
            filters["status"] = status
        if assignee:
            filters["assignee"] = assignee
        if reporter:
            filters["reporter"] = reporter

        # Get user's accessible projects if no specific project
        if not project_id:
            accessible_projects = get_user_accessible_projects(user)
            if accessible_projects:
                filters["project"] = ["in", accessible_projects]
            else:
                # User has no project access
                return {"status": "success", "data": []}

        # Get issues
        issues = frappe.get_all(
            "GRM Issue",
            filters=filters,
            fields=[
                "name",
                "tracking_code",
                "title",
                "description",
                "status",
                "assignee",
                "reporter",
                "citizen_name",
                "citizen_type",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "gender",
                "category",
                "issue_type",
                "created_date",
                "resolution_days",
                "resolution_date",
                "intake_date",
                "issue_date",
                "administrative_region",
                "confirmed",
                "resolution_accepted",
                "rating",
                "escalate_flag",
                "project",
                "contact_information",
                "contact_medium",
                "ongoing_issue",
                "auto_increment_id",
            ],
            limit=limit,
            start=offset,
            order_by="creation desc",
        )

        # Enhance issue data
        for issue in issues:
            # Get status details
            if issue.status:
                status_doc = frappe.get_doc("GRM Issue Status", issue.status)
                issue.status_details = {
                    "id": status_doc.name,
                    "name": status_doc.status_name,
                    "final_status": status_doc.final_status,
                    "initial_status": status_doc.initial_status,
                    "open_status": status_doc.open_status,
                    "rejected_status": status_doc.rejected_status,
                }

            # Get category details
            if issue.category:
                category_doc = frappe.get_doc("GRM Issue Category", issue.category)
                issue.category_details = {
                    "id": category_doc.name,
                    "name": category_doc.category_name,
                    "confidentiality_level": category_doc.confidentiality_level,
                }

            # Get issue type details
            if issue.issue_type:
                type_doc = frappe.get_doc("GRM Issue Type", issue.issue_type)
                issue.type_details = {"id": type_doc.name, "name": type_doc.type_name}

            # Get administrative region details
            if issue.administrative_region:
                region_doc = frappe.get_doc(
                    "GRM Administrative Region", issue.administrative_region
                )
                issue.region_details = {
                    "administrative_id": region_doc.name,
                    "name": region_doc.region_name,
                    "latitude": region_doc.latitude,
                    "longitude": region_doc.longitude,
                }

            # Get attachments
            attachments = frappe.get_all(
                "GRM Issue Attachment",
                filters={"parent": issue.name},
                fields=["name", "file", "description", "uploaded_by", "upload_date"],
            )
            issue.attachments = attachments

            # Get logs
            logs = frappe.get_all(
                "GRM Issue Log",
                filters={"parent": issue.name},
                fields=["log_type", "log_by", "log_date", "description"],
                order_by="log_date desc",
            )
            issue.logs = logs

            # Get comments
            comments = frappe.get_all(
                "GRM Issue Comment",
                filters={"parent": issue.name},
                fields=["comment_by", "comment_text", "comment_date"],
                order_by="comment_date desc",
            )
            issue.comments = comments

        frappe.log(f"Returning {len(issues)} issues")
        return {"status": "success", "data": issues}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in list_issues: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get(issue_id):
    """
    Get a single issue with full details

    Args:
        issue_id (str): Issue ID

    Returns:
        dict: Issue details
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting issue {issue_id} for user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if user has permission to read the issue
        if not frappe.has_permission("GRM Issue", "read", issue_id):
            log.warning(
                f"User {user} does not have permission to read issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to access this issue"),
            }

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Convert to dict and enhance
        issue_dict = issue.as_dict()

        # Get related data
        if issue_dict.get("status"):
            status_doc = frappe.get_doc("GRM Issue Status", issue_dict["status"])
            issue_dict["status_details"] = status_doc.as_dict()

        if issue_dict.get("category"):
            category_doc = frappe.get_doc("GRM Issue Category", issue_dict["category"])
            issue_dict["category_details"] = category_doc.as_dict()

        if issue_dict.get("issue_type"):
            type_doc = frappe.get_doc("GRM Issue Type", issue_dict["issue_type"])
            issue_dict["type_details"] = type_doc.as_dict()

        if issue_dict.get("administrative_region"):
            region_doc = frappe.get_doc(
                "GRM Administrative Region", issue_dict["administrative_region"]
            )
            issue_dict["region_details"] = region_doc.as_dict()

        frappe.log(f"Returning issue {issue_id}")
        return {"status": "success", "data": issue_dict}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in get_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create(issue_data):
    """
    Create a new issue using the sync creation logic for consistency

    Args:
        issue_data (dict): Issue data

    Returns:
        dict: Created issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Creating issue for user: {user}")

        # Parse issue data if it's a string
        if isinstance(issue_data, str):
            issue_data = json.loads(issue_data)

        # Use the sync creation function to ensure consistency
        result = create_issue_from_sync(issue_data, user)

        if result.get("status") == "success":
            issue_name = result["data"]["name"]

            # Get the created issue
            issue = frappe.get_doc("GRM Issue", issue_name)

            frappe.log(f"Issue {issue.name} already submitted")
            return {"status": "success", "data": issue.as_dict()}
        else:
            frappe.log_error(
                f"Error in create_issue_from_sync: {result.get('message')}"
            )
            return result  # Return the error from create_issue_from_sync

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in create_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def update(issue_id, issue_data):
    """
    Update an existing issue

    Args:
        issue_id (str): Issue ID
        issue_data (dict): Updated issue data

    Returns:
        dict: Updated issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Updating issue {issue_id} for user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if user has permission to update the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(
                f"User {user} does not have permission to update issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to update this issue"),
            }

        # Parse issue data if it's a string
        if isinstance(issue_data, str):
            issue_data = json.loads(issue_data)

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Track changes for logging
        changes = []

        # Update fields
        updatable_fields = [
            "title",
            "description",
            "citizen_name",
            "citizen_type",
            "gender",
            "contact_medium",
            "ongoing_issue",
            "confirmed",
            "resolution_accepted",
            "rating",
            "research_result",
            "reject_reason",
        ]

        for field in updatable_fields:
            if field in issue_data and getattr(issue, field) != issue_data[field]:
                old_value = getattr(issue, field)
                setattr(issue, field, issue_data[field])
                changes.append(f"{field}: {old_value} → {issue_data[field]}")

        # Update related fields
        if "status" in issue_data and issue.status != issue_data["status"]:
            old_status = issue.status
            issue.status = issue_data["status"]
            changes.append(f"status: {old_status} → {issue_data['status']}")

        # Save issue
        issue.save()

        # Add update log if there were changes
        if changes:
            issue.append(
                "grm_issue_log",
                {
                    "log_type": "Updated",
                    "log_by": user,
                    "log_date": now_datetime(),
                    "description": f"Issue updated: {', '.join(changes)}",
                },
            )
            issue.save()

        frappe.log(f"Updated issue {issue_id}")
        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in update_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def assign(issue_id, assignee_id):
    """
    Assign an issue to a user

    Args:
        issue_id (str): Issue ID
        assignee_id (str): User ID to assign to

    Returns:
        dict: Updated issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Assigning issue {issue_id} to {assignee_id} by user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if assignee exists
        if not frappe.db.exists("User", assignee_id):
            log.warning(f"Assignee {assignee_id} not found")
            return {"status": "error", "message": _("Assignee not found")}

        # Check if user has permission to assign the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(
                f"User {user} does not have permission to assign issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to assign this issue"),
            }

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Update assignee
        old_assignee = issue.assignee
        issue.assignee = assignee_id

        # Update status to accepted if it's initial
        if issue.status:
            status_doc = frappe.get_doc("GRM Issue Status", issue.status)
            if status_doc.initial_status:
                # Find accepted status
                accepted_status = frappe.get_all(
                    "GRM Issue Status",
                    filters={"open_status": 1},
                    fields=["name"],
                    limit=1,
                )
                if accepted_status:
                    issue.status = accepted_status[0].name

        # Save issue
        issue.save()

        # Add assignment log
        assignee_name = frappe.get_value("User", assignee_id, "full_name")
        issue.append(
            "grm_issue_log",
            {
                "log_type": "Assigned",
                "log_by": user,
                "log_date": now_datetime(),
                "description": f"Issue assigned to {assignee_name}",
            },
        )
        issue.save()

        frappe.log(f"Assigned issue {issue_id} to {assignee_id}")
        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in assign_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def resolve(issue_id, resolution_text=None):
    """
    Resolve an issue

    Args:
        issue_id (str): Issue ID
        resolution_text (str, optional): Resolution description

    Returns:
        dict: Updated issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Resolving issue {issue_id} by user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if user has permission to resolve the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(
                f"User {user} does not have permission to resolve issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to resolve this issue"),
            }

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Find resolved status
        resolved_status = frappe.get_all(
            "GRM Issue Status", filters={"final_status": 1}, fields=["name"], limit=1
        )

        if not resolved_status:
            log.warning("No resolved status found")
            return {"status": "error", "message": _("No resolved status configured")}

        # Update issue
        issue.status = resolved_status[0].name
        issue.resolution_date = now_datetime()
        if resolution_text:
            issue.research_result = resolution_text

        # Save issue
        issue.save()

        # Add resolution log
        issue.append(
            "grm_issue_log",
            {
                "log_type": "Resolved",
                "log_by": user,
                "log_date": now_datetime(),
                "description": f"Issue resolved: {resolution_text or 'No description provided'}",
            },
        )
        issue.save()

        frappe.log(f"Resolved issue {issue_id}")
        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in resolve_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def reopen(issue_id, reason=None):
    """
    Reopen a resolved issue

    Args:
        issue_id (str): Issue ID
        reason (str, optional): Reason for reopening

    Returns:
        dict: Updated issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Reopening issue {issue_id} by user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if user has permission to reopen the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(
                f"User {user} does not have permission to reopen issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to reopen this issue"),
            }

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Find reopened status
        reopened_status = get_reopened_status(issue.project)
        if not reopened_status:
            log.warning("No reopened status found")
            return {"status": "error", "message": _("No reopened status configured")}

        # Update issue
        issue.status = reopened_status
        issue.resolution_date = None

        # Save issue
        issue.save()

        # Add reopen log
        issue.append(
            "grm_issue_log",
            {
                "log_type": "Reopened",
                "log_by": user,
                "log_date": now_datetime(),
                "description": f"Issue reopened: {reason or 'No reason provided'}",
            },
        )
        issue.save()

        frappe.log(f"Reopened issue {issue_id}")
        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in reopen_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def escalate(issue_id, reason=None):
    """
    Escalate an issue

    Args:
        issue_id (str): Issue ID
        reason (str, optional): Reason for escalation

    Returns:
        dict: Updated issue
    """
    try:
        user = frappe.session.user
        frappe.log(f"Escalating issue {issue_id} by user: {user}")

        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}

        # Check if user has permission to escalate the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(
                f"User {user} does not have permission to escalate issue {issue_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to escalate this issue"),
            }

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Set escalation flag
        issue.escalate_flag = True

        # Add escalation reason if provided
        if reason:
            if not issue.escalation_reasons:
                issue.escalation_reasons = []
            issue.append(
                "escalation_reasons",
                {
                    "reason": reason,
                    "escalated_by": user,
                    "escalation_date": now_datetime(),
                },
            )

        # Save issue
        issue.save()

        # Add escalation log
        issue.append(
            "grm_issue_log",
            {
                "log_type": "Escalated",
                "log_by": user,
                "log_date": now_datetime(),
                "description": f"Issue escalated: {reason or 'No reason provided'}",
            },
        )
        issue.save()

        frappe.log(f"Escalated issue {issue_id}")
        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in escalate_issue: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_latest_issues(last_sync_timestamp=None, limit=50, offset=0):
    """
    Get issues created after the last sync timestamp.
    This is a lightweight endpoint that only returns essential issue data.

    Args:
        last_sync_timestamp (str, optional): Last sync timestamp in ISO format
        limit (int): Maximum number of issues to return
        offset (int): Offset for pagination

    Returns:
        dict: {
            "data": List of issues created after the timestamp,
            "total_count": Total number of issues matching the criteria,
            "has_more": Boolean indicating if there are more issues to load
        }
    """
    try:
        user = frappe.session.user
        frappe.log(
            f"Getting latest issues for user: {user}, last_sync: {last_sync_timestamp}"
        )

        # Parse timestamp
        if last_sync_timestamp:
            try:
                last_sync = get_datetime(last_sync_timestamp)
            except:
                last_sync = None
        else:
            last_sync = None

        # Get user's accessible projects
        accessible_projects = get_user_accessible_projects(user)
        if not accessible_projects:
            return {
                "status": "success",
                "data": {"issues": [], "total_count": 0, "has_more": False},
            }

        # Build filters
        filters = {"project": ["in", accessible_projects]}
        if last_sync:
            filters["creation"] = [">", last_sync]

        # Get total count first
        total_count = frappe.db.count("GRM Issue", filters=filters)

        # Get paginated issues with minimal fields for efficiency
        issues = frappe.get_all(
            "GRM Issue",
            filters=filters,
            fields=[
                "name",
                "title",
                "description",
                "status",
                "assignee",
                "reporter",
                "category",
                "issue_type",
                "created_date",
                "creation",
                "modified",
                "administrative_region",
                "project",
                "confirmed",
                "resolution_accepted",
                "escalate_flag",
            ],
            limit=cint(limit),
            start=cint(offset),
            order_by="creation desc",
        )

        # Enhance with minimal required related data
        for issue in issues:
            # Get status details
            if issue.status:
                status_doc = frappe.get_doc("GRM Issue Status", issue.status)
                issue.status_details = {
                    "id": status_doc.name,
                    "name": status_doc.status_name,
                    "final_status": status_doc.final_status,
                }

            # Get category details
            if issue.category:
                category_doc = frappe.get_doc("GRM Issue Category", issue.category)
                issue.category_details = {
                    "id": category_doc.name,
                    "name": category_doc.category_name,
                }

            # Get administrative region details
            if issue.administrative_region:
                region_doc = frappe.get_doc(
                    "GRM Administrative Region", issue.administrative_region
                )
                issue.region_details = {
                    "administrative_id": region_doc.name,
                    "name": region_doc.region_name,
                }

        has_more = total_count > (cint(offset) + len(issues))

        frappe.log(f"Returning {len(issues)} latest issues")
        return {
            "status": "success",
            "data": {
                "issues": issues,
                "total_count": total_count,
                "has_more": has_more,
            },
        }

    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error in get_latest_issues: {str(e)}")
        return {"status": "error", "message": str(e)}


# Utility functions


def get_user_accessible_projects(user):
    """
    Get projects a user can access

    Args:
        user (str): User ID

    Returns:
        list: List of project IDs
    """
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        projects = frappe.get_all("GRM Project", fields=["name"])
        return [p.name for p in projects]

    # Get projects assigned to the user
    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "active": 1},
        fields=["project"],
    )

    return [a.project for a in assignments]


def get_reopened_status(project_id):
    """
    Get reopened status for a project

    Args:
        project_id (str): Project ID

    Returns:
        str: Reopened status ID
    """
    # Find a status with "reopen" or "reopened" in the name
    statuses = frappe.get_all(
        "GRM Issue Status",
        filters=[["status_name", "like", "%reopen%"]],
        fields=["name"],
    )

    if statuses:
        return statuses[0].name

    # Fallback: Get first non-final status
    statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 0}, fields=["name"]
    )

    if statuses:
        return statuses[0].name

    return None


def user_has_project_access(user, project_id):
    """
    Check if a user has access to a project

    Args:
        user (str): User ID
        project_id (str): Project ID

    Returns:
        bool: True if user has access, False otherwise
    """
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True

    # Check if user is assigned to project
    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "project": project_id, "active": 1},
        fields=["name"],
    )

    return len(assignments) > 0


def user_has_region_access(user, region_id):
    """
    Check if a user has access to a region

    Args:
        user (str): User ID
        region_id (str): Region ID

    Returns:
        bool: True if user has access, False otherwise
    """
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True

    # For now, return True
    # This would need to be implemented based on how regional assignments are stored
    return True


def create_log_entry(issue_id, log_type, user, description):
    """
    Create a log entry for an issue

    Args:
        issue_id (str): Issue ID
        log_type (str): Log type
        user (str): User ID
        description (str): Log description

    Returns:
        None
    """
    try:
        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Add log entry
        issue.append(
            "grm_issue_log",
            {
                "log_type": log_type,
                "log_by": user,
                "log_date": get_datetime(),
                "description": description,
            },
        )

        # Save issue
        issue.save()

        frappe.log(
            f"Created log entry for issue {issue_id}: {log_type} - {description}"
        )
    except Exception as e:
        print(frappe.get_traceback())
        frappe.log_error(f"Error creating log entry for issue {issue_id}: {str(e)}")
