// Copyright (c) 2025, eGRM and contributors
// For license information, please see license.txt

frappe.query_reports["GRM Public Monthly Report"] = {
	"filters": [
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "GRM Project",
			"reqd": 0
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.month_start(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.month_end(), -1),
			"reqd": 1
		}
	]
};
