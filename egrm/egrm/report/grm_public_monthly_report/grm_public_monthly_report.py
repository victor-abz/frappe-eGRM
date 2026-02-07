# Copyright (c) 2025, eGRM and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_months, get_first_day, get_last_day, flt


def execute(filters=None):
	filters = validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data, filters)
	report_summary = get_report_summary(filters)

	return columns, data, None, chart, report_summary


def validate_filters(filters):
	if not filters:
		filters = frappe._dict()

	if not filters.get("from_date"):
		# Default to first day of last month
		filters["from_date"] = get_first_day(add_months(getdate(), -1))

	if not filters.get("to_date"):
		# Default to last day of last month
		filters["to_date"] = get_last_day(add_months(getdate(), -1))

	filters["from_date"] = getdate(filters["from_date"])
	filters["to_date"] = getdate(filters["to_date"])

	if filters["from_date"] > filters["to_date"]:
		frappe.throw(_("From Date cannot be after To Date"))

	return filters


def get_columns():
	return [
		{
			"label": _("Category"),
			"fieldname": "category",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Total Received"),
			"fieldname": "total_received",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Resolved"),
			"fieldname": "resolved",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Pending"),
			"fieldname": "pending",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Appealed"),
			"fieldname": "appealed",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Avg Resolution Days"),
			"fieldname": "avg_resolution_days",
			"fieldtype": "Float",
			"width": 160,
			"precision": 1,
		},
	]


def get_data(filters):
	"""Get report data grouped by GRM Issue Category."""

	# Get status names that represent final (resolved) statuses
	final_statuses = frappe.get_all(
		"GRM Issue Status",
		filters={"final_status": 1},
		pluck="name",
	)

	# Build conditions
	conditions = get_conditions(filters)

	# Query all submitted issues in the date range, grouped by category
	issues = frappe.db.sql(
		"""
		SELECT
			cat.category_name AS category,
			COUNT(gi.name) AS total_received,
			SUM(CASE WHEN gi.status IN %(final_statuses)s THEN 1 ELSE 0 END) AS resolved,
			SUM(CASE WHEN gi.status NOT IN %(final_statuses)s THEN 1 ELSE 0 END) AS pending,
			SUM(CASE WHEN gi.appeal_submitted = 1 THEN 1 ELSE 0 END) AS appealed,
			AVG(CASE WHEN gi.resolution_days > 0 THEN gi.resolution_days ELSE NULL END) AS avg_resolution_days
		FROM `tabGRM Issue` gi
		INNER JOIN `tabGRM Issue Category` cat ON gi.category = cat.name
		WHERE gi.docstatus = 1
			AND gi.issue_date BETWEEN %(from_date)s AND %(to_date)s
			{conditions}
		GROUP BY gi.category, cat.category_name
		ORDER BY total_received DESC
		""".format(conditions=conditions),
		{
			"from_date": filters["from_date"],
			"to_date": filters["to_date"],
			"final_statuses": final_statuses or [""],
			"project": filters.get("project"),
		},
		as_dict=True,
	)

	# Clean up numeric values
	for row in issues:
		row["resolved"] = row["resolved"] or 0
		row["pending"] = row["pending"] or 0
		row["appealed"] = row["appealed"] or 0
		row["avg_resolution_days"] = flt(row["avg_resolution_days"], 1)

	return issues


def get_conditions(filters):
	conditions = ""
	if filters.get("project"):
		conditions += " AND gi.project = %(project)s"
	return conditions


def get_chart_data(data, filters):
	"""Generate bar chart comparing received vs resolved per category."""
	if not data:
		return None

	labels = [row["category"] for row in data]
	received = [row["total_received"] for row in data]
	resolved = [row["resolved"] for row in data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Received"), "values": received},
				{"name": _("Resolved"), "values": resolved},
			],
		},
		"type": "bar",
		"colors": ["#7cd6fd", "#5e64ff"],
		"barOptions": {"stacked": False},
	}


def get_report_summary(filters):
	"""Generate summary cards for the report."""

	# Get status names that represent final (resolved) statuses
	final_statuses = frappe.get_all(
		"GRM Issue Status",
		filters={"final_status": 1},
		pluck="name",
	)

	conditions = get_conditions(filters)

	summary_data = frappe.db.sql(
		"""
		SELECT
			COUNT(gi.name) AS total_received,
			SUM(CASE WHEN gi.status IN %(final_statuses)s THEN 1 ELSE 0 END) AS resolved,
			SUM(CASE WHEN gi.status NOT IN %(final_statuses)s THEN 1 ELSE 0 END) AS not_resolved,
			SUM(CASE WHEN gi.appeal_submitted = 1 THEN 1 ELSE 0 END) AS appealed
		FROM `tabGRM Issue` gi
		WHERE gi.docstatus = 1
			AND gi.issue_date BETWEEN %(from_date)s AND %(to_date)s
			{conditions}
		""".format(conditions=conditions),
		{
			"from_date": filters["from_date"],
			"to_date": filters["to_date"],
			"final_statuses": final_statuses or [""],
			"project": filters.get("project"),
		},
		as_dict=True,
	)[0]

	total_received = summary_data.get("total_received") or 0
	resolved = summary_data.get("resolved") or 0
	not_resolved = summary_data.get("not_resolved") or 0
	appealed = summary_data.get("appealed") or 0

	resolution_rate = flt((resolved / total_received * 100) if total_received else 0, 1)

	return [
		{
			"value": total_received,
			"indicator": "Blue",
			"label": _("Total Received"),
			"datatype": "Int",
		},
		{
			"value": resolved,
			"indicator": "Green",
			"label": _("Resolved"),
			"datatype": "Int",
		},
		{
			"value": not_resolved,
			"indicator": "Orange",
			"label": _("Not Resolved"),
			"datatype": "Int",
		},
		{
			"value": appealed,
			"indicator": "Red",
			"label": _("Appealed"),
			"datatype": "Int",
		},
		{
			"value": resolution_rate,
			"indicator": "Green" if resolution_rate >= 70 else "Orange",
			"label": _("Resolution Rate (%)"),
			"datatype": "Percent",
		},
	]
