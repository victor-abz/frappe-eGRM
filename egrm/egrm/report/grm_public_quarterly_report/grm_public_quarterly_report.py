# Copyright (c) 2025, eGRM and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

from egrm.egrm.report.grm_public_monthly_report.grm_public_monthly_report import (
	get_columns,
	get_data,
	get_chart_data,
	get_report_summary,
)


def execute(filters=None):
	filters = validate_quarterly_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data, filters)
	report_summary = get_report_summary(filters)

	return columns, data, None, chart, report_summary


def validate_quarterly_filters(filters):
	if not filters:
		filters = frappe._dict()

	if not filters.get("from_date") or not filters.get("to_date"):
		today = getdate()
		current_month = today.month

		if current_month <= 3:
			# Q1, last quarter is Q4 of previous year
			filters["from_date"] = today.replace(year=today.year - 1, month=10, day=1)
			filters["to_date"] = today.replace(year=today.year - 1, month=12, day=31)
		elif current_month <= 6:
			# Q2, last quarter is Q1
			filters["from_date"] = today.replace(month=1, day=1)
			filters["to_date"] = today.replace(month=3, day=31)
		elif current_month <= 9:
			# Q3, last quarter is Q2
			filters["from_date"] = today.replace(month=4, day=1)
			filters["to_date"] = today.replace(month=6, day=30)
		else:
			# Q4, last quarter is Q3
			filters["from_date"] = today.replace(month=7, day=1)
			filters["to_date"] = today.replace(month=9, day=30)

	filters["from_date"] = getdate(filters["from_date"])
	filters["to_date"] = getdate(filters["to_date"])

	return filters
