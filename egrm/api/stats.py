"""
EGRM API - Statistics & Reporting Endpoints
------------------------------------------
This module contains API endpoints for statistics and reporting.
"""

import json
import logging

import frappe
from frappe import _
from frappe.utils import add_to_date, date_diff, get_datetime, getdate, now_datetime

# Configure logging
log = logging.getLogger(__name__)


@frappe.whitelist()
def dashboard(project_id=None, date_range=None):
    """
    Get dashboard statistics

    Args:
        project_id (str, optional): Project ID to filter data
        date_range (str, optional): Date range filter (7d, 30d, 90d, 1y)

    Returns:
        dict: Dashboard statistics
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting dashboard stats for user: {user}")

        # Get user's accessible projects
        accessible_projects = get_user_accessible_projects(user)
        if not accessible_projects:
            return {"status": "success", "data": get_empty_dashboard()}

        # Filter by specific project if provided
        if project_id and project_id in accessible_projects:
            accessible_projects = [project_id]
        elif project_id:
            return {
                "status": "error",
                "message": _("You do not have access to this project"),
            }

        # Parse date range
        date_filter = get_date_filter(date_range)

        # Get statistics
        stats = {
            "overview": get_overview_stats(accessible_projects, date_filter),
            "status_breakdown": get_status_breakdown(accessible_projects, date_filter),
            "category_breakdown": get_category_breakdown(
                accessible_projects, date_filter
            ),
            "region_breakdown": get_region_breakdown(accessible_projects, date_filter),
            "trend_data": get_trend_data(accessible_projects, date_range),
            "user_performance": get_user_performance(
                accessible_projects, user, date_filter
            ),
            "recent_activities": get_recent_activities(accessible_projects, user, 10),
        }

        frappe.log(f"Returning dashboard stats for user {user}")
        return {"status": "success", "data": stats}

    except Exception as e:
        frappe.log_error(f"Error in dashboard: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def user_stats(project_id=None, date_range=None):
    """
    Get user-specific statistics

    Args:
        project_id (str, optional): Project ID to filter data
        date_range (str, optional): Date range filter

    Returns:
        dict: User statistics
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting user stats for: {user}")

        # Get user's accessible projects
        accessible_projects = get_user_accessible_projects(user)
        if not accessible_projects:
            return {"status": "success", "data": get_empty_user_stats()}

        # Filter by specific project if provided
        if project_id and project_id in accessible_projects:
            accessible_projects = [project_id]
        elif project_id:
            return {
                "status": "error",
                "message": _("You do not have access to this project"),
            }

        # Parse date range
        date_filter = get_date_filter(date_range)

        # Get user statistics
        stats = {
            "assigned_issues": get_user_assigned_issues(
                accessible_projects, user, date_filter
            ),
            "reported_issues": get_user_reported_issues(
                accessible_projects, user, date_filter
            ),
            "resolved_issues": get_user_resolved_issues(
                accessible_projects, user, date_filter
            ),
            "performance_metrics": get_user_performance_metrics(
                accessible_projects, user, date_filter
            ),
            "workload_distribution": get_user_workload_distribution(
                accessible_projects, user
            ),
            "activity_timeline": get_user_activity_timeline(
                accessible_projects, user, date_filter
            ),
        }

        frappe.log(f"Returning user stats for {user}")
        return {"status": "success", "data": stats}

    except Exception as e:
        frappe.log_error(f"Error in user_stats: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def project_summary(project_id):
    """
    Get project summary statistics

    Args:
        project_id (str): Project ID

    Returns:
        dict: Project summary
    """
    try:
        user = frappe.session.user
        frappe.log(f"Getting project summary for: {project_id}")

        # Check if user has access to project
        accessible_projects = get_user_accessible_projects(user)
        if project_id not in accessible_projects:
            return {
                "status": "error",
                "message": _("You do not have access to this project"),
            }

        # Get project details
        project = frappe.get_doc("GRM Project", project_id)

        # Get project statistics
        stats = {
            "project_info": {
                "name": project.project_name,
                "description": project.description,
                "active": project.active,
                "created_date": project.creation,
            },
            "issue_summary": get_project_issue_summary(project_id),
            "regional_coverage": get_project_regional_coverage(project_id),
            "team_members": get_project_team_members(project_id),
            "performance_indicators": get_project_performance_indicators(project_id),
        }

        frappe.log(f"Returning project summary for {project_id}")
        return {"status": "success", "data": stats}

    except Exception as e:
        frappe.log_error(f"Error in project_summary: {str(e)}")
        return {"status": "error", "message": str(e)}


# Helper functions


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


def get_date_filter(date_range):
    """Get date filter based on range"""
    if not date_range:
        return None

    today = getdate()

    if date_range == "7d":
        return add_to_date(today, days=-7)
    elif date_range == "30d":
        return add_to_date(today, days=-30)
    elif date_range == "90d":
        return add_to_date(today, days=-90)
    elif date_range == "1y":
        return add_to_date(today, years=-1)

    return None


def get_empty_dashboard():
    """Get empty dashboard structure"""
    return {
        "overview": {
            "total_issues": 0,
            "open_issues": 0,
            "resolved_issues": 0,
            "pending_issues": 0,
        },
        "status_breakdown": [],
        "category_breakdown": [],
        "region_breakdown": [],
        "trend_data": [],
        "user_performance": {},
        "recent_activities": [],
    }


def get_empty_user_stats():
    """Get empty user stats structure"""
    return {
        "assigned_issues": 0,
        "reported_issues": 0,
        "resolved_issues": 0,
        "performance_metrics": {},
        "workload_distribution": [],
        "activity_timeline": [],
    }


def get_overview_stats(accessible_projects, date_filter):
    """Get overview statistics"""
    filters = {"project": ["in", accessible_projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Total issues
    total_issues = frappe.db.count("GRM Issue", filters)

    # Open issues
    open_statuses = frappe.get_all(
        "GRM Issue Status", filters={"open_status": 1}, fields=["name"]
    )
    open_status_ids = [s.name for s in open_statuses]

    open_filters = filters.copy()
    if open_status_ids:
        open_filters["status"] = ["in", open_status_ids]
    open_issues = frappe.db.count("GRM Issue", open_filters)

    # Resolved issues
    resolved_statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 1}, fields=["name"]
    )
    resolved_status_ids = [s.name for s in resolved_statuses]

    resolved_filters = filters.copy()
    if resolved_status_ids:
        resolved_filters["status"] = ["in", resolved_status_ids]
    resolved_issues = frappe.db.count("GRM Issue", resolved_filters)

    # Pending issues (initial status)
    pending_statuses = frappe.get_all(
        "GRM Issue Status", filters={"initial_status": 1}, fields=["name"]
    )
    pending_status_ids = [s.name for s in pending_statuses]

    pending_filters = filters.copy()
    if pending_status_ids:
        pending_filters["status"] = ["in", pending_status_ids]
    pending_issues = frappe.db.count("GRM Issue", pending_filters)

    return {
        "total_issues": total_issues,
        "open_issues": open_issues,
        "resolved_issues": resolved_issues,
        "pending_issues": pending_issues,
    }


def get_status_breakdown(accessible_projects, date_filter):
    """Get status breakdown"""
    filters = {"project": ["in", accessible_projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Get all statuses
    statuses = frappe.get_all("GRM Issue Status", fields=["name", "status_name"])

    breakdown = []
    for status in statuses:
        status_filters = filters.copy()
        status_filters["status"] = status.name
        count = frappe.db.count("GRM Issue", status_filters)

        if count > 0:
            breakdown.append({"status": status.status_name, "count": count})

    return breakdown


def get_category_breakdown(accessible_projects, date_filter):
    """Get category breakdown"""
    filters = {"project": ["in", accessible_projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Get categories for accessible projects
    categories = frappe.get_all(
        "GRM Issue Category",
        filters={"project": ["in", accessible_projects]},
        fields=["name", "category_name"],
    )

    breakdown = []
    for category in categories:
        category_filters = filters.copy()
        category_filters["category"] = category.name
        count = frappe.db.count("GRM Issue", category_filters)

        if count > 0:
            breakdown.append({"category": category.category_name, "count": count})

    return breakdown


def get_region_breakdown(accessible_projects, date_filter):
    """Get region breakdown"""
    filters = {"project": ["in", accessible_projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Get regions for accessible projects
    regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": ["in", accessible_projects]},
        fields=["name", "region_name"],
    )

    breakdown = []
    for region in regions:
        region_filters = filters.copy()
        region_filters["administrative_region"] = region.name
        count = frappe.db.count("GRM Issue", region_filters)

        if count > 0:
            breakdown.append({"region": region.region_name, "count": count})

    return breakdown


def get_trend_data(accessible_projects, date_range):
    """Get trend data for charts"""
    # Default to 30 days if no range specified
    days = 30
    if date_range == "7d":
        days = 7
    elif date_range == "90d":
        days = 90
    elif date_range == "1y":
        days = 365

    trend_data = []
    today = getdate()

    for i in range(days):
        date = add_to_date(today, days=-i)

        filters = {
            "project": ["in", accessible_projects],
            "creation": [">=", date],
            "creation": ["<", add_to_date(date, days=1)],
        }

        count = frappe.db.count("GRM Issue", filters)

        trend_data.append({"date": date.strftime("%Y-%m-%d"), "count": count})

    return list(reversed(trend_data))


def get_user_performance(accessible_projects, user, date_filter):
    """Get user performance metrics"""
    filters = {"project": ["in", accessible_projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Issues assigned to user
    assigned_filters = filters.copy()
    assigned_filters["assignee"] = user
    assigned_count = frappe.db.count("GRM Issue", assigned_filters)

    # Issues reported by user
    reported_filters = filters.copy()
    reported_filters["reporter"] = user
    reported_count = frappe.db.count("GRM Issue", reported_filters)

    # Issues resolved by user
    resolved_filters = filters.copy()
    resolved_filters["assignee"] = user
    resolved_statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 1}, fields=["name"]
    )
    if resolved_statuses:
        resolved_filters["status"] = ["in", [s.name for s in resolved_statuses]]
        resolved_count = frappe.db.count("GRM Issue", resolved_filters)
    else:
        resolved_count = 0

    return {
        "assigned_issues": assigned_count,
        "reported_issues": reported_count,
        "resolved_issues": resolved_count,
        "resolution_rate": (
            (resolved_count / assigned_count * 100) if assigned_count > 0 else 0
        ),
    }


def get_recent_activities(accessible_projects, user, limit):
    """Get recent activities"""
    # Get recent issues where user is involved
    filters = {
        "project": ["in", accessible_projects],
        "$or": [{"assignee": user}, {"reporter": user}],
    }

    issues = frappe.get_all(
        "GRM Issue",
        filters=filters,
        fields=["name", "title", "tracking_code", "status", "modified"],
        order_by="modified desc",
        limit=limit,
    )

    activities = []
    for issue in issues:
        # Get status name
        status_name = ""
        if issue.status:
            status_doc = frappe.get_doc("GRM Issue Status", issue.status)
            status_name = status_doc.status_name

        activities.append(
            {
                "issue_id": issue.name,
                "tracking_code": issue.tracking_code,
                "status": status_name,
                "last_modified": issue.modified,
            }
        )

    return activities


def get_user_assigned_issues(accessible_projects, user, date_filter):
    """Get user assigned issues count"""
    filters = {"project": ["in", accessible_projects], "assignee": user}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    return frappe.db.count("GRM Issue", filters)


def get_user_reported_issues(accessible_projects, user, date_filter):
    """Get user reported issues count"""
    filters = {"project": ["in", accessible_projects], "reporter": user}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    return frappe.db.count("GRM Issue", filters)


def get_user_resolved_issues(accessible_projects, user, date_filter):
    """Get user resolved issues count"""
    filters = {"project": ["in", accessible_projects], "assignee": user}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Add resolved status filter
    resolved_statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 1}, fields=["name"]
    )
    if resolved_statuses:
        filters["status"] = ["in", [s.name for s in resolved_statuses]]
        return frappe.db.count("GRM Issue", filters)

    return 0


def get_user_performance_metrics(accessible_projects, user, date_filter):
    """Get detailed user performance metrics"""
    assigned = get_user_assigned_issues(accessible_projects, user, date_filter)
    resolved = get_user_resolved_issues(accessible_projects, user, date_filter)

    # Calculate average resolution time
    avg_resolution_time = calculate_avg_resolution_time(
        accessible_projects, user, date_filter
    )

    return {
        "total_assigned": assigned,
        "total_resolved": resolved,
        "resolution_rate": (resolved / assigned * 100) if assigned > 0 else 0,
        "avg_resolution_time_days": avg_resolution_time,
    }


def get_user_workload_distribution(accessible_projects, user):
    """Get user workload distribution by status"""
    # Get issues assigned to user grouped by status
    issues = frappe.get_all(
        "GRM Issue",
        filters={"project": ["in", accessible_projects], "assignee": user},
        fields=["status"],
        group_by="status",
    )

    distribution = []
    for issue in issues:
        if issue.status:
            status_doc = frappe.get_doc("GRM Issue Status", issue.status)
            count = frappe.db.count(
                "GRM Issue",
                {
                    "project": ["in", accessible_projects],
                    "assignee": user,
                    "status": issue.status,
                },
            )

            distribution.append({"status": status_doc.status_name, "count": count})

    return distribution


def get_user_activity_timeline(accessible_projects, user, date_filter):
    """Get user activity timeline"""
    filters = {"project": ["in", accessible_projects], "assignee": user}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Get issues and their creation dates
    issues = frappe.get_all(
        "GRM Issue",
        filters=filters,
        fields=["creation", "resolution_date"],
        order_by="creation desc",
    )

    timeline = []
    for issue in issues:
        timeline.append(
            {"date": issue.creation.strftime("%Y-%m-%d"), "type": "created", "count": 1}
        )

        if issue.resolution_date:
            timeline.append(
                {
                    "date": issue.resolution_date.strftime("%Y-%m-%d"),
                    "type": "resolved",
                    "count": 1,
                }
            )

    return timeline


def calculate_avg_resolution_time(accessible_projects, user, date_filter):
    """Calculate average resolution time for user"""
    filters = {
        "project": ["in", accessible_projects],
        "assignee": user,
        "resolution_date": ["is", "set"],
    }
    if date_filter:
        filters["creation"] = [">=", date_filter]

    issues = frappe.get_all(
        "GRM Issue", filters=filters, fields=["creation", "resolution_date"]
    )

    if not issues:
        return 0

    total_days = 0
    for issue in issues:
        if issue.creation and issue.resolution_date:
            days = date_diff(issue.resolution_date, issue.creation)
            total_days += days

    return total_days / len(issues) if issues else 0


def get_project_issue_summary(project_id):
    """Get project issue summary"""
    filters = {"project": project_id}

    total = frappe.db.count("GRM Issue", filters)

    # Get status breakdown
    statuses = frappe.get_all("GRM Issue Status", fields=["name", "status_name"])
    status_breakdown = []

    for status in statuses:
        status_filters = filters.copy()
        status_filters["status"] = status.name
        count = frappe.db.count("GRM Issue", status_filters)

        if count > 0:
            status_breakdown.append({"status": status.status_name, "count": count})

    return {"total_issues": total, "status_breakdown": status_breakdown}


def get_project_regional_coverage(project_id):
    """Get project regional coverage"""
    regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": project_id},
        fields=["name", "region_name", "administrative_level"],
    )

    coverage = []
    for region in regions:
        issue_count = frappe.db.count(
            "GRM Issue", {"project": project_id, "administrative_region": region.name}
        )

        coverage.append(
            {
                "region": region.region_name,
                "level": region.administrative_level,
                "issue_count": issue_count,
            }
        )

    return coverage


def get_project_team_members(project_id):
    """Get project team members"""
    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"project": project_id, "active": 1},
        fields=["user", "role"],
    )

    team_members = []
    for assignment in assignments:
        user_doc = frappe.get_doc("User", assignment.user)

        # Get user's issue counts
        assigned_count = frappe.db.count(
            "GRM Issue", {"project": project_id, "assignee": assignment.user}
        )

        reported_count = frappe.db.count(
            "GRM Issue", {"project": project_id, "reporter": assignment.user}
        )

        team_members.append(
            {
                "user": assignment.user,
                "name": user_doc.full_name,
                "role": assignment.role,
                "assigned_issues": assigned_count,
                "reported_issues": reported_count,
            }
        )

    return team_members


def get_project_performance_indicators(project_id):
    """Get project performance indicators"""
    # Total issues
    total_issues = frappe.db.count("GRM Issue", {"project": project_id})

    # Resolved issues
    resolved_statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 1}, fields=["name"]
    )

    resolved_count = 0
    if resolved_statuses:
        resolved_count = frappe.db.count(
            "GRM Issue",
            {
                "project": project_id,
                "status": ["in", [s.name for s in resolved_statuses]],
            },
        )

    # Average resolution time
    avg_resolution_time = calculate_project_avg_resolution_time(project_id)

    return {
        "total_issues": total_issues,
        "resolved_issues": resolved_count,
        "resolution_rate": (
            (resolved_count / total_issues * 100) if total_issues > 0 else 0
        ),
        "avg_resolution_time_days": avg_resolution_time,
    }


def calculate_project_avg_resolution_time(project_id):
    """Calculate average resolution time for project"""
    issues = frappe.get_all(
        "GRM Issue",
        filters={"project": project_id, "resolution_date": ["is", "set"]},
        fields=["creation", "resolution_date"],
    )

    if not issues:
        return 0

    total_days = 0
    for issue in issues:
        if issue.creation and issue.resolution_date:
            days = date_diff(issue.resolution_date, issue.creation)
            total_days += days

    return total_days / len(issues) if issues else 0
