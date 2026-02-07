"""
EGRM API - Public Metrics Endpoints
------------------------------------
This module provides publicly accessible (allow_guest=True) aggregate
statistics for the GRM public dashboard.  All data is anonymized --
only aggregate counts are returned, never any PII.

Part of WB GRM Compliance Phase 1: Public Transparency.
"""

import frappe
from frappe.utils import add_to_date, getdate


# ---------------------------------------------------------------------------
# Main public endpoint
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_public_dashboard(project_id=None, date_range=None):
    """
    Return anonymized aggregate statistics for the public dashboard.

    Args:
        project_id (str, optional): Restrict to a single GRM Project.
        date_range (str, optional): One of "7d", "30d", "90d", "1y".

    Returns:
        dict: ``{"status": "success", "data": {...}}`` with keys
              *overview*, *status_breakdown*, *category_breakdown*,
              *region_breakdown*, and *trend_data*.
    """
    try:
        # Only show data for active projects
        projects = _get_active_projects(project_id)
        if not projects:
            return {"status": "success", "data": _empty_dashboard()}

        date_filter = get_date_filter(date_range)

        data = {
            "overview": get_overview_stats(projects, date_filter),
            "status_breakdown": get_status_breakdown(projects, date_filter),
            "category_breakdown": get_category_breakdown(projects, date_filter),
            "region_breakdown": get_region_breakdown(projects, date_filter),
            "trend_data": get_trend_data(projects, date_range),
        }

        return {"status": "success", "data": data}

    except Exception as e:
        frappe.log_error(
            title="Public Metrics API Error",
            message=f"get_public_dashboard failed: {e}",
        )
        return {
            "status": "error",
            "message": "An error occurred while fetching public metrics.",
        }


# ---------------------------------------------------------------------------
# Helper: active projects
# ---------------------------------------------------------------------------

def _get_active_projects(project_id=None):
    """
    Return a list of active GRM Project names.

    If *project_id* is supplied and it corresponds to an active project,
    only that project is returned.  Otherwise all active projects are
    returned.
    """
    if project_id:
        is_active = frappe.db.get_value("GRM Project", project_id, "is_active")
        if is_active:
            return [project_id]
        return []

    projects = frappe.get_all(
        "GRM Project",
        filters={"is_active": 1},
        fields=["name"],
    )
    return [p.name for p in projects]


# ---------------------------------------------------------------------------
# Helper: empty dashboard shape
# ---------------------------------------------------------------------------

def _empty_dashboard():
    """Return the dashboard payload when there is no data."""
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
    }


# ---------------------------------------------------------------------------
# Date filter
# ---------------------------------------------------------------------------

def get_date_filter(date_range):
    """
    Convert a human-friendly range string to a date object.

    Supported values: ``"7d"``, ``"30d"``, ``"90d"``, ``"1y"``.
    Returns ``None`` when *date_range* is not recognised (no filter).
    """
    if not date_range:
        return None

    today = getdate()

    range_map = {
        "7d": {"days": -7},
        "30d": {"days": -30},
        "90d": {"days": -90},
        "1y": {"years": -1},
    }

    kwargs = range_map.get(date_range)
    if kwargs:
        return add_to_date(today, **kwargs)

    return None


# ---------------------------------------------------------------------------
# Filters builder
# ---------------------------------------------------------------------------

def _base_filters(projects, date_filter):
    """
    Build the common filter dict shared by all issue queries.

    Only *submitted* issues (``docstatus=1``) are included so that
    draft or cancelled records do not skew public numbers.
    """
    filters = {
        "project": ["in", projects],
        "docstatus": 1,
    }
    if date_filter:
        filters["creation"] = [">=", date_filter]
    return filters


# ---------------------------------------------------------------------------
# Overview stats
# ---------------------------------------------------------------------------

def get_overview_stats(projects, date_filter):
    """
    Return total, open, resolved, and pending issue counts.

    * **open** -- statuses with ``open_status = 1``
    * **resolved** -- statuses with ``final_status = 1``
    * **pending** -- statuses with ``initial_status = 1``
    """
    filters = _base_filters(projects, date_filter)

    total_issues = frappe.db.count("GRM Issue", filters)

    # Open issues
    open_statuses = frappe.get_all(
        "GRM Issue Status", filters={"open_status": 1}, fields=["name"]
    )
    open_status_ids = [s.name for s in open_statuses]
    open_issues = 0
    if open_status_ids:
        open_filters = filters.copy()
        open_filters["status"] = ["in", open_status_ids]
        open_issues = frappe.db.count("GRM Issue", open_filters)

    # Resolved issues (final_status)
    resolved_statuses = frappe.get_all(
        "GRM Issue Status", filters={"final_status": 1}, fields=["name"]
    )
    resolved_status_ids = [s.name for s in resolved_statuses]
    resolved_issues = 0
    if resolved_status_ids:
        resolved_filters = filters.copy()
        resolved_filters["status"] = ["in", resolved_status_ids]
        resolved_issues = frappe.db.count("GRM Issue", resolved_filters)

    # Pending issues (initial_status)
    pending_statuses = frappe.get_all(
        "GRM Issue Status", filters={"initial_status": 1}, fields=["name"]
    )
    pending_status_ids = [s.name for s in pending_statuses]
    pending_issues = 0
    if pending_status_ids:
        pending_filters = filters.copy()
        pending_filters["status"] = ["in", pending_status_ids]
        pending_issues = frappe.db.count("GRM Issue", pending_filters)

    return {
        "total_issues": total_issues,
        "open_issues": open_issues,
        "resolved_issues": resolved_issues,
        "pending_issues": pending_issues,
    }


# ---------------------------------------------------------------------------
# Status breakdown
# ---------------------------------------------------------------------------

def get_status_breakdown(projects, date_filter):
    """
    Return a list of ``{"status": <name>, "count": <int>}`` for every
    GRM Issue Status that has at least one matching issue.
    """
    filters = _base_filters(projects, date_filter)

    statuses = frappe.get_all(
        "GRM Issue Status", fields=["name", "status_name"]
    )

    breakdown = []
    for status in statuses:
        status_filters = filters.copy()
        status_filters["status"] = status.name
        count = frappe.db.count("GRM Issue", status_filters)
        if count > 0:
            breakdown.append({"status": status.status_name, "count": count})

    return breakdown


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------

def get_category_breakdown(projects, date_filter):
    """
    Return a list of ``{"category": <name>, "count": <int>}`` for every
    GRM Issue Category that has at least one matching issue.

    Categories are resolved through the GRM Issue records themselves
    (which carry a ``category`` Link field) rather than trying to
    filter the Category DocType by project directly.
    """
    filters = _base_filters(projects, date_filter)

    # Get distinct categories referenced by matching issues
    categories_used = frappe.get_all(
        "GRM Issue",
        filters=filters,
        fields=["category"],
        group_by="category",
    )

    breakdown = []
    for row in categories_used:
        if not row.category:
            continue

        # Count issues for this category
        cat_filters = filters.copy()
        cat_filters["category"] = row.category
        count = frappe.db.count("GRM Issue", cat_filters)

        # Resolve display name
        category_name = frappe.db.get_value(
            "GRM Issue Category", row.category, "category_name"
        )

        if count > 0 and category_name:
            breakdown.append({"category": category_name, "count": count})

    return breakdown


# ---------------------------------------------------------------------------
# Region breakdown
# ---------------------------------------------------------------------------

def get_region_breakdown(projects, date_filter):
    """
    Return a list of ``{"region": <name>, "count": <int>}`` for every
    GRM Administrative Region with at least one matching issue.
    """
    filters = _base_filters(projects, date_filter)

    regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": ["in", projects]},
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


# ---------------------------------------------------------------------------
# Trend data
# ---------------------------------------------------------------------------

def get_trend_data(projects, date_range):
    """
    Return daily issue counts suitable for charting.

    Each entry is ``{"date": "YYYY-MM-DD", "count": <int>}``.

    Note: The original plan had a duplicate-key bug (two ``"creation"``
    keys in the same dict).  This implementation uses the ``["between",
    ...]`` filter to correctly select issues for each day.
    """
    days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(date_range, 30)

    today = getdate()
    trend_data = []

    for i in range(days):
        day = add_to_date(today, days=-i)
        next_day = add_to_date(day, days=1)

        filters = {
            "project": ["in", projects],
            "docstatus": 1,
            "creation": ["between", [day, next_day]],
        }

        count = frappe.db.count("GRM Issue", filters)
        trend_data.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # Return in chronological order (oldest first)
    return list(reversed(trend_data))
