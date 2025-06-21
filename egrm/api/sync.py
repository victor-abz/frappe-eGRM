"""
EGRM API - Sync Management Endpoints
----------------------------------
This module contains API endpoints for synchronizing data between mobile app and Frappe.
"""

import json
import logging
import traceback

import frappe
from frappe import _
from frappe.utils import (
    add_to_date,
    cint,
    cstr,
    get_datetime,
    get_datetime_str,
    now_datetime,
)
from werkzeug.wrappers import Response

# Configure logging
log = logging.getLogger(__name__)


@frappe.whitelist()
def get_changes(last_sync_timestamp=None, project_id=None):
    """
    Get all changes since last sync timestamp

    Args:
        last_sync_timestamp (str, optional): Last sync timestamp in ISO format
        project_id (str, optional): Project ID to filter data

    Returns:
        dict: Changes since last sync
    """
    try:
        user = frappe.session.user
        frappe.log(
            f"Getting changes for user: {user}, last_sync: {last_sync_timestamp}"
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
                "data": {"changes": [], "timestamp": now_datetime().isoformat()},
            }

        # Filter by specific project if provided
        if project_id and project_id in accessible_projects:
            accessible_projects = [project_id]
        elif project_id:
            # User doesn't have access to this project
            return {
                "status": "error",
                "message": _("You do not have access to this project"),
            }

        changes = {
            "issues": get_issue_changes(last_sync, accessible_projects),
            "regions": get_region_changes(last_sync, accessible_projects),
            "categories": get_category_changes(last_sync, accessible_projects),
            "types": get_type_changes(last_sync, accessible_projects),
            "statuses": get_status_changes(last_sync),
            "age_groups": get_age_group_changes(last_sync),
            "citizen_groups": get_citizen_group_changes(last_sync),
            "departments": get_department_changes(last_sync),
            "projects": get_project_changes(last_sync, accessible_projects),
        }

        current_timestamp = now_datetime().isoformat()

        frappe.log(f"Returning changes for user {user}")
        return {
            "status": "success",
            "data": {"changes": changes, "timestamp": current_timestamp},
        }

    except Exception as e:
        frappe.log(f"Error in get_changes: {str(e)}")
        frappe.log_error(f"Error in get_changes: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def push_changes(changes_data):
    """
    Push local changes to server

    Args:
        changes_data (dict): Local changes to push

    Returns:
        dict: Result of push operation
    """
    try:
        user = frappe.session.user
        frappe.log(f"Pushing changes for user: {user}")

        # Parse changes data if it's a string
        if isinstance(changes_data, str):
            changes_data = json.loads(changes_data)

        results = {"created": [], "updated": [], "errors": []}

        # Process issue changes
        if "issues" in changes_data:
            issue_results = process_issue_changes(changes_data["issues"], user)
            results["created"].extend(issue_results.get("created", []))
            results["updated"].extend(issue_results.get("updated", []))
            results["errors"].extend(issue_results.get("errors", []))

        # Process attachment changes
        if "attachments" in changes_data:
            attachment_results = process_attachment_changes(
                changes_data["attachments"], user
            )
            results["created"].extend(attachment_results.get("created", []))
            results["updated"].extend(attachment_results.get("updated", []))
            results["errors"].extend(attachment_results.get("errors", []))

        frappe.log(
            f"Push completed for user {user}: {len(results['created'])} created, {len(results['updated'])} updated, {len(results['errors'])} errors"
        )

        frappe.log(len(results["errors"]))
        response = Response(json.dumps(results), content_type="application/json")
        response.status_code = 200

        return response

    except Exception as e:
        frappe.log(f"Error in push_changes: {str(e)}")
        frappe.log_error(f"Error in push_changes: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_user_data(project_id=None):
    """
    Get all data accessible to the current user

    Args:
        project_id (str, optional): Project ID to filter data

    Returns:
        dict: User's accessible data
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting user data for: {user}")

        # Get user's accessible projects
        accessible_projects = get_user_accessible_projects(user)
        if not accessible_projects:
            return {"status": "success", "data": {}}

        # Filter by specific project if provided
        if project_id and project_id in accessible_projects:
            accessible_projects = [project_id]
        elif project_id:
            return {
                "status": "error",
                "message": _("You do not have access to this project"),
            }

        data = {
            "projects": get_user_projects_data(accessible_projects),
            "regions": get_user_regions_data(accessible_projects),
            "categories": get_user_categories_data(accessible_projects),
            "types": get_user_types_data(accessible_projects),
            "statuses": get_user_statuses_data(),
            "age_groups": get_user_age_groups_data(),
            "citizen_groups": get_user_citizen_groups_data(),
            "departments": get_user_departments_data(),
            "issues": get_user_issues_data(accessible_projects, user),
            "timestamp": now_datetime().isoformat(),
        }

        frappe.log(f"Returning user data for {user}")
        return {"status": "success", "data": data}

    except Exception as e:
        frappe.log(f"Error in get_user_data: {str(e)}")
        frappe.log_error(f"Error in get_user_data: {str(e)}")
        return {"status": "error", "message": str(e)}


# Helper functions for getting changes


def get_issue_changes(last_sync, accessible_projects):
    """Get issue changes since last sync"""
    filters = {"project": ["in", accessible_projects]}
    if last_sync:
        filters["modified"] = [">", last_sync]

    issues = frappe.get_all(
        "GRM Issue", filters=filters, fields=["*"], order_by="modified desc"
    )

    # Enhance with related data
    for issue in issues:
        enhance_issue_data(issue)

    return issues


def get_region_changes(last_sync, accessible_projects):
    """Get region changes since last sync"""
    filters = {"project": ["in", accessible_projects]}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Administrative Region",
        filters=filters,
        fields=["*"],
        order_by="modified desc",
    )


def get_category_changes(last_sync, accessible_projects):
    """Get category changes since last sync"""
    filters = {"project": ["in", accessible_projects]}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Issue Category", filters=filters, fields=["*"], order_by="modified desc"
    )


def get_type_changes(last_sync, accessible_projects):
    """Get type changes since last sync"""
    filters = {"project": ["in", accessible_projects]}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Issue Type", filters=filters, fields=["*"], order_by="modified desc"
    )


def get_status_changes(last_sync):
    """Get status changes since last sync"""
    filters = {}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Issue Status", filters=filters, fields=["*"], order_by="modified desc"
    )


def get_age_group_changes(last_sync):
    """Get age group changes since last sync"""
    filters = {}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Issue Age Group", filters=filters, fields=["*"], order_by="modified desc"
    )


def get_citizen_group_changes(last_sync):
    """Get citizen group changes since last sync"""
    filters = {}
    if last_sync:
        filters["modified"] = [">", last_sync]

    # Get all citizen groups from the single DocType
    citizen_groups = frappe.get_all(
        "GRM Issue Citizen Group",
        filters=filters,
        fields=["*"],
        order_by="modified desc",
    )

    # Split into two groups based on group_type
    citizen_groups_1 = [group for group in citizen_groups if group.group_type == "1"]
    citizen_groups_2 = [group for group in citizen_groups if group.group_type == "2"]

    return {"citizen_group_1": citizen_groups_1, "citizen_group_2": citizen_groups_2}


def get_department_changes(last_sync):
    """Get department changes since last sync"""
    filters = {}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Issue Department", filters=filters, fields=["*"], order_by="modified desc"
    )


def get_project_changes(last_sync, accessible_projects):
    """Get project changes since last sync"""
    filters = {"name": ["in", accessible_projects]}
    if last_sync:
        filters["modified"] = [">", last_sync]

    return frappe.get_all(
        "GRM Project", filters=filters, fields=["*"], order_by="modified desc"
    )


# Helper functions for getting user data


def get_user_projects_data(accessible_projects):
    """Get user's accessible projects"""
    return frappe.get_all(
        "GRM Project", filters={"name": ["in", accessible_projects]}, fields=["*"]
    )


def get_user_regions_data(accessible_projects):
    """Get user's accessible regions"""
    return frappe.get_all(
        "GRM Administrative Region",
        filters={"project": ["in", accessible_projects]},
        fields=["*"],
    )


def get_user_categories_data(accessible_projects):
    """Get user's accessible categories"""
    return frappe.get_all(
        "GRM Issue Category",
        filters={"project": ["in", accessible_projects]},
        fields=["*"],
    )


def get_user_types_data(accessible_projects):
    """Get user's accessible types"""
    return frappe.get_all(
        "GRM Issue Type", filters={"project": ["in", accessible_projects]}, fields=["*"]
    )


def get_user_statuses_data():
    """Get all statuses"""
    return frappe.get_all("GRM Issue Status", fields=["*"])


def get_user_age_groups_data():
    """Get all age groups"""
    return frappe.get_all("GRM Issue Age Group", fields=["*"])


def get_user_citizen_groups_data():
    """Get all citizen groups"""
    # Get all citizen groups from the single DocType
    citizen_groups = frappe.get_all("GRM Issue Citizen Group", fields=["*"])

    # Split into two groups based on group_type
    citizen_groups_1 = [group for group in citizen_groups if group.group_type == "1"]
    citizen_groups_2 = [group for group in citizen_groups if group.group_type == "2"]

    return {"citizen_group_1": citizen_groups_1, "citizen_group_2": citizen_groups_2}


def get_user_departments_data():
    """Get all departments"""
    return frappe.get_all("GRM Issue Department", fields=["*"])


def get_user_issues_data(accessible_projects, user):
    """Get user's accessible issues"""
    # Get issues where user is assignee, reporter, or has project access
    issues = frappe.get_all(
        "GRM Issue",
        filters={"project": ["in", accessible_projects]},
        fields=["*"],
        order_by="creation desc",
    )

    # Enhance with related data
    for issue in issues:
        enhance_issue_data(issue)

    return issues


# Helper functions for processing changes


def process_issue_changes(issue_changes, user):
    """Process issue changes from mobile app"""
    results = {"created": [], "updated": [], "errors": []}

    for change in issue_changes:
        try:
            if change.get("action") == "create":
                # Create new issue
                issue_data = change.get("data", {})
                result = create_issue_from_sync(issue_data, user)
                if result.get("status") == "success":
                    results["created"].append(
                        {
                            "local_id": change.get("local_id"),
                            "server_id": result["data"]["name"],
                            "type": "issue",
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "local_id": change.get("local_id"),
                            "error": result.get("message"),
                            "type": "issue",
                        }
                    )

            elif change.get("action") == "update":
                # Update existing issue
                issue_id = change.get("id")
                issue_data = change.get("data", {})
                result = update_issue_from_sync(issue_id, issue_data, user)
                if result.get("status") == "success":
                    results["updated"].append({"id": issue_id, "type": "issue"})
                else:
                    results["errors"].append(
                        {
                            "id": issue_id,
                            "error": result.get("message"),
                            "type": "issue",
                        }
                    )

        except Exception as e:
            results["errors"].append(
                {
                    "local_id": change.get("local_id") or change.get("id"),
                    "error": str(e),
                    "type": "issue",
                }
            )

    return results


def process_attachment_changes(attachment_changes, user):
    """Process attachment changes from mobile app"""
    results = {"created": [], "updated": [], "errors": []}

    for change in attachment_changes:
        try:
            if change.get("action") == "upload":
                # Upload new attachment
                attachment_data = change.get("data", {})
                result = upload_attachment_from_sync(attachment_data, user)
                if result.get("status") == "success":
                    results["created"].append(
                        {
                            "local_id": change.get("local_id"),
                            "server_id": result["data"]["name"],
                            "type": "attachment",
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "local_id": change.get("local_id"),
                            "error": result.get("message"),
                            "type": "attachment",
                        }
                    )

        except Exception as e:
            results["errors"].append(
                {
                    "local_id": change.get("local_id"),
                    "error": str(e),
                    "type": "attachment",
                }
            )

    return results


def enhance_issue_data(issue):
    """Enhance issue data with related information"""
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


def validate_issue_data(issue_data):
    """Centralized validation for issue data"""
    required_fields = {
        "description": "Description",
        "category": "Category",
        "issue_type": "Issue Type",
        "administrative_region": "Administrative Region",
    }

    validation_errors = []

    # Check required fields
    for field, label in required_fields.items():
        if not issue_data.get(field):
            validation_errors.append(f"{label} is required")

    # Validate coordinates format if provided
    if issue_data.get("coordinates"):
        try:
            if isinstance(issue_data["coordinates"], str):
                # Try to parse as JSON if it's a string
                coordinates = json.loads(issue_data["coordinates"])
                if not (
                    coordinates.get("type") == "FeatureCollection"
                    and coordinates.get("features")
                    and coordinates["features"][0]
                    .get("geometry", {})
                    .get("coordinates")
                ):
                    validation_errors.append("Invalid GeoJSON format for coordinates")
        except json.JSONDecodeError:
            validation_errors.append("Invalid coordinates format")

    # Validate dates if provided
    for date_field in ["intake_date", "issue_date"]:
        if issue_data.get(date_field):
            try:
                get_datetime(issue_data[date_field])
            except:
                validation_errors.append(f"Invalid {date_field} format")

    # Validate references to other doctypes
    if issue_data.get("category"):
        if not frappe.db.exists("GRM Issue Category", issue_data["category"]):
            validation_errors.append("Invalid category")

    if issue_data.get("issue_type"):
        if not frappe.db.exists("GRM Issue Type", issue_data["issue_type"]):
            validation_errors.append("Invalid issue type")

    if issue_data.get("administrative_region"):
        if not frappe.db.exists(
            "GRM Administrative Region", issue_data["administrative_region"]
        ):
            validation_errors.append("Invalid administrative region")

    # Validate assignee if provided
    if issue_data.get("assignee"):
        if not frappe.db.exists("User", issue_data["assignee"]):
            validation_errors.append("Invalid assignee")

    return validation_errors


def create_issue_from_sync(issue_data, user):
    """Create issue from sync data"""
    try:
        # Log incoming data for debugging
        frappe.log(f"Issue data to be created: {issue_data}")

        # Log assignment data specifically
        if issue_data.get("assignee"):
            frappe.log(f"Assignment data - Assignee: {issue_data['assignee']}")
            if not frappe.db.exists("User", issue_data["assignee"]):
                frappe.log(f"Warning: Assignee {issue_data['assignee']} does not exist")

        # First check for duplicate based on key fields
        existing_issue = find_duplicate_issue(issue_data)
        if existing_issue:
            frappe.log(f"Found duplicate issue: {existing_issue.name}")
            return {"status": "success", "data": existing_issue.as_dict()}

        # Create new issue document
        issue = frappe.new_doc("GRM Issue")

        # Map fields from issue_data to issue document
        field_mapping = {
            "description": "description",
            "citizen": "citizen",
            "citizen_type": "citizen_type",
            "gender": "gender",
            "contact_medium": "contact_medium",
            "contact_type": "contact_info_type",
            "contact_value": "contact_information",
            "category": "category",
            "issue_type": "issue_type",
            "administrative_region": "administrative_region",
            "citizen_age_group": "citizen_age_group",
            "citizen_group_1": "citizen_group_1",
            "citizen_group_2": "citizen_group_2",
            "project": "project",
            "ongoing_issue": "ongoing_issue",
            "confirmed": "confirmed",
            "tracking_code": "tracking_code",
            "assignee": "assignee",
        }

        # Set fields using mapping
        for src_field, dest_field in field_mapping.items():
            if issue_data.get(src_field) is not None:
                issue.set(dest_field, issue_data[src_field])

        # Handle dates with proper formatting
        for date_field in ["intake_date", "issue_date"]:
            if issue_data.get(date_field):
                issue.set(
                    date_field, get_datetime_str(get_datetime(issue_data[date_field]))
                )

        # Set geolocation coordinates if provided
        if issue_data.get("coordinates"):
            issue.issue_location = cstr(issue_data["coordinates"])

        # Set reporter
        issue.reporter = user

        # Save issue
        issue.insert()

        # Submit the issue
        if issue.docstatus == 0:
            issue.submit()

        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        traceback.print_exc()
        frappe.log(f"******** ERROR INSERT ******** {str(e)}")
        return {"status": "error", "message": str(e)}


def find_duplicate_issue(issue_data):
    """Find a duplicate issue based on key fields"""
    # Define fields to check for duplication
    key_fields = [
        "description",
        "category",
        "issue_type",
        "administrative_region",
        "coordinates",
        "intake_date",
        "issue_date",
    ]

    # Build filters
    filters = {}
    for field in key_fields:
        if issue_data.get(field):
            if field == "coordinates":
                # For coordinates, we need exact match
                filters["issue_location"] = issue_data[field]
            elif field in ["intake_date", "issue_date"]:
                # For dates, match within a small time window (e.g., 1 minute)
                try:
                    date_value = get_datetime(issue_data[field])
                    filters[field] = [
                        "between",
                        [
                            add_to_date(date_value, minutes=-1),
                            add_to_date(date_value, minutes=1),
                        ],
                    ]
                except:
                    continue
            else:
                filters[field] = issue_data[field]

    # Add creation time filter to only check recent issues (e.g., last hour)
    filters["creation"] = [">", add_to_date(now_datetime(), hours=-1)]

    # Search for matching issues
    matching_issues = frappe.get_all(
        "GRM Issue", filters=filters, fields=["name"], limit=1
    )

    if matching_issues:
        return frappe.get_doc("GRM Issue", matching_issues[0].name)

    return None


def update_issue_from_sync(issue_id, issue_data, user):
    """Update issue from sync data"""
    try:
        # Check if issue exists and user has permission
        if not frappe.db.exists("GRM Issue", issue_id):
            return {"status": "error", "message": "Issue not found"}

        if not frappe.has_permission("GRM Issue", "write", issue_id):
            return {"status": "error", "message": "Permission denied"}

        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)

        # Update fields from sync data
        for field, value in issue_data.items():
            if hasattr(issue, field) and field not in ["name", "creation", "modified"]:
                setattr(issue, field, value)

        # Save issue
        issue.save()

        return {"status": "success", "data": issue.as_dict()}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def upload_attachment_from_sync(attachment_data, user):
    """Upload attachment from sync data"""
    try:
        # This would handle file upload from sync
        # Implementation depends on how files are sent in sync
        return {"status": "success", "data": {"name": "temp_attachment_id"}}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_user_accessible_projects(user):
    """Get projects a user can access"""
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
