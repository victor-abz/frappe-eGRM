// Copyright (c) 2025, eGRM and contributors
// For license information, please see license.txt

frappe.query_reports["GRM Public Quarterly Report"] = {
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
			"default": get_last_quarter_start(),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": get_last_quarter_end(),
			"reqd": 1
		}
	]
};

function get_last_quarter_start() {
	let today = new Date();
	let month = today.getMonth();
	let year = today.getFullYear();

	if (month < 3) {
		return new Date(year - 1, 9, 1).toISOString().split('T')[0];
	} else if (month < 6) {
		return new Date(year, 0, 1).toISOString().split('T')[0];
	} else if (month < 9) {
		return new Date(year, 3, 1).toISOString().split('T')[0];
	} else {
		return new Date(year, 6, 1).toISOString().split('T')[0];
	}
}

function get_last_quarter_end() {
	let today = new Date();
	let month = today.getMonth();
	let year = today.getFullYear();

	if (month < 3) {
		return new Date(year - 1, 11, 31).toISOString().split('T')[0];
	} else if (month < 6) {
		return new Date(year, 2, 31).toISOString().split('T')[0];
	} else if (month < 9) {
		return new Date(year, 5, 30).toISOString().split('T')[0];
	} else {
		return new Date(year, 8, 30).toISOString().split('T')[0];
	}
}
