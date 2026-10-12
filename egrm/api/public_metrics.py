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

from egrm.api.portal_config import _is_staff
from egrm.egrm.doctype.egrm_settings.egrm_settings import get_portal_visibility

# ---------------------------------------------------------------------------
# Main public endpoint
# ---------------------------------------------------------------------------


def _guard_dashboard() -> None:
	"""Refuse the figures when the public dashboard is switched off.

	Hiding the nav link left the endpoint itself answering anyone who asked,
	so "turned off" meant the page was merely harder to find. Staff keep the
	preview the navbar badges; everyone else is refused here, not in the SPA.
	"""
	if get_portal_visibility()["enable_public_dashboard"]:
		return
	if _is_staff():
		return
	frappe.throw(
		frappe._("The public dashboard is not published."),
		frappe.PermissionError,
	)


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
	          *type_breakdown*, *region_breakdown*, and *trend_data*.

	Raises:
	    frappe.PermissionError: When the dashboard is unpublished and the
	        caller is not staff.
	"""
	_guard_dashboard()

	try:
		# Only show data for active projects
		projects = _get_active_projects(project_id)
		if not projects:
			return {"status": "success", "data": _empty_dashboard()}

		date_filter = _get_date_filter(date_range)

		data = {
			"overview": _get_overview_stats(projects, date_filter),
			"status_breakdown": _get_status_breakdown(projects, date_filter),
			"category_breakdown": _get_category_breakdown(projects, date_filter),
			"type_breakdown": _get_type_breakdown(projects, date_filter),
			"region_breakdown": _get_region_breakdown(projects, date_filter),
			"trend_data": _get_trend_data(projects, date_range),
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


def _empty_dashboard():
	return {
		"overview": {
			"total_issues": 0,
			"open_issues": 0,
			"resolved_issues": 0,
			"pending_issues": 0,
			"issues_this_week": 0,
			"issues_this_month": 0,
			"resolution_rate": 0.0,
			"avg_resolution_days": None,
		},
		"status_breakdown": [],
		"category_breakdown": [],
		"type_breakdown": [],
		"region_breakdown": [],
		"trend_data": [],
	}


# ---------------------------------------------------------------------------
# Shared SQL helpers
# ---------------------------------------------------------------------------


def _get_date_filter(date_range):
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


def _project_placeholders(projects):
	"""Return (placeholder_str, values_list) for SQL IN clause."""
	placeholders = ", ".join(["%s"] * len(projects))
	return placeholders, list(projects)


def _where_clause(projects, date_filter):
	"""Build WHERE clause fragment and params for common issue filters."""
	ph, params = _project_placeholders(projects)
	where = f"gi.project IN ({ph}) AND gi.docstatus = 1"
	if date_filter:
		where += " AND gi.creation >= %s"
		params.append(date_filter)
	return where, params


# ---------------------------------------------------------------------------
# Overview stats — 1 query with conditional aggregation
# ---------------------------------------------------------------------------


def _get_overview_stats(projects, date_filter):
	where, params = _where_clause(projects, date_filter)
	today = getdate()
	week_start = add_to_date(today, days=-7)
	month_start = add_to_date(today, days=-30)

	# The mobile Statistics screen leads with resolution rate and average
	# resolution time; the public dashboard published neither, so the same
	# programme looked different depending on which door you came through.
	# Both are derived here in the one existing aggregate query rather than
	# added as extra round trips.
	row = frappe.db.sql(
		f"""
        SELECT
            COUNT(*) AS total_issues,
            SUM(CASE WHEN s.open_status = 1 THEN 1 ELSE 0 END) AS open_issues,
            SUM(CASE WHEN s.final_status = 1 THEN 1 ELSE 0 END) AS resolved_issues,
            SUM(CASE WHEN s.initial_status = 1 THEN 1 ELSE 0 END) AS pending_issues,
            SUM(CASE WHEN gi.creation >= %s THEN 1 ELSE 0 END) AS issues_this_week,
            SUM(CASE WHEN gi.creation >= %s THEN 1 ELSE 0 END) AS issues_this_month,
            AVG(
                CASE
                    WHEN s.final_status = 1 AND gi.resolution_date IS NOT NULL
                    THEN DATEDIFF(gi.resolution_date, DATE(gi.creation))
                END
            ) AS avg_resolution_days
        FROM `tabGRM Issue` gi
        LEFT JOIN `tabGRM Issue Status` s ON gi.status = s.name
        WHERE {where}
        """,
		[week_start, month_start, *params],
		as_dict=True,
	)

	r = row[0] if row else {}
	total = r.get("total_issues") or 0
	resolved = r.get("resolved_issues") or 0
	avg_days = r.get("avg_resolution_days")

	return {
		"total_issues": total,
		"open_issues": r.get("open_issues") or 0,
		"resolved_issues": resolved,
		"pending_issues": r.get("pending_issues") or 0,
		"issues_this_week": r.get("issues_this_week") or 0,
		"issues_this_month": r.get("issues_this_month") or 0,
		"resolution_rate": round(resolved * 100.0 / total, 1) if total else 0.0,
		# None, not 0 -- "no issue has been resolved yet" and "issues are
		# resolved the same day" are different facts and must not render alike.
		"avg_resolution_days": round(float(avg_days), 1) if avg_days is not None else None,
	}


# ---------------------------------------------------------------------------
# Status breakdown — 1 query with GROUP BY
# ---------------------------------------------------------------------------


def _get_status_breakdown(projects, date_filter):
	where, params = _where_clause(projects, date_filter)

	rows = frappe.db.sql(
		f"""
        SELECT s.status_name AS status, COUNT(*) AS count
        FROM `tabGRM Issue` gi
        JOIN `tabGRM Issue Status` s ON gi.status = s.name
        WHERE {where}
        GROUP BY gi.status
        HAVING count > 0
        ORDER BY count DESC
        """,
		params,
		as_dict=True,
	)
	return [{"status": r.status, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Category breakdown — 1 query with JOIN
# ---------------------------------------------------------------------------


def _get_category_breakdown(projects, date_filter):
	where, params = _where_clause(projects, date_filter)

	rows = frappe.db.sql(
		f"""
        SELECT ic.category_name AS category, COUNT(*) AS count
        FROM `tabGRM Issue` gi
        JOIN `tabGRM Issue Category` ic ON gi.category = ic.name
        WHERE {where}
          AND gi.category IS NOT NULL AND gi.category != ''
        GROUP BY gi.category
        HAVING count > 0
        ORDER BY count DESC
        """,
		params,
		as_dict=True,
	)
	return [{"category": r.category, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Issue-type breakdown — 1 query with JOIN
# ---------------------------------------------------------------------------


def _get_type_breakdown(projects, date_filter):
	where, params = _where_clause(projects, date_filter)

	rows = frappe.db.sql(
		f"""
        SELECT it.type_name AS issue_type, COUNT(*) AS count
        FROM `tabGRM Issue` gi
        JOIN `tabGRM Issue Type` it ON gi.issue_type = it.name
        WHERE {where}
          AND gi.issue_type IS NOT NULL AND gi.issue_type != ''
        GROUP BY gi.issue_type
        HAVING count > 0
        ORDER BY count DESC
        """,
		params,
		as_dict=True,
	)
	return [{"issue_type": r.issue_type, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Region breakdown — 1 query with JOIN
# ---------------------------------------------------------------------------


def _get_region_breakdown(projects, date_filter):
	where, params = _where_clause(projects, date_filter)

	rows = frappe.db.sql(
		f"""
        SELECT r.region_name AS region, COUNT(*) AS count
        FROM `tabGRM Issue` gi
        JOIN `tabGRM Administrative Region` r
            ON gi.administrative_region = r.name
        WHERE {where}
          AND gi.administrative_region IS NOT NULL
          AND gi.administrative_region != ''
        GROUP BY gi.administrative_region
        HAVING count > 0
        ORDER BY count DESC
        """,
		params,
		as_dict=True,
	)
	return [{"region": r.region, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Trend data — 1 query with GROUP BY DATE
# ---------------------------------------------------------------------------


def _get_trend_data(projects, date_range):
	days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
	days = days_map.get(date_range, 30)

	today = getdate()
	start_date = add_to_date(today, days=-days)

	ph, params = _project_placeholders(projects)
	params.extend([start_date, today])

	rows = frappe.db.sql(
		f"""
        SELECT DATE(creation) AS date, COUNT(*) AS count
        FROM `tabGRM Issue`
        WHERE project IN ({ph})
          AND docstatus = 1
          AND DATE(creation) >= %s
          AND DATE(creation) <= %s
        GROUP BY DATE(creation)
        ORDER BY date ASC
        """,
		params,
		as_dict=True,
	)

	# Build a dict for quick lookup, then fill gaps with zeros
	counts_by_date = {str(r.date): r.count for r in rows}
	trend = []
	for i in range(days + 1):
		day = add_to_date(start_date, days=i)
		day_str = day.strftime("%Y-%m-%d")
		trend.append({"date": day_str, "count": counts_by_date.get(day_str, 0)})

	return trend
