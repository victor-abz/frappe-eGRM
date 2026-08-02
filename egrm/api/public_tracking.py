"""
Public Tracking API
Allows citizens to track complaints by tracking code (no auth required)
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def track_complaint(tracking_code):
	"""
	Track complaint status by tracking code

	Args:
	    tracking_code (str): Unique tracking code

	Returns:
	    dict: Complaint status (anonymized, no PII)
	"""
	if not tracking_code:
		return {"status": "error", "message": _("Tracking code is required")}

	try:
		# Find issue by tracking code
		issue_name = frappe.db.get_value("GRM Issue", {"tracking_code": tracking_code}, "name")

		if not issue_name:
			return {"status": "error", "message": _("Complaint not found. Please check your tracking code.")}

		# Get issue data (only public-safe fields)
		issue = frappe.db.get_value(
			"GRM Issue",
			issue_name,
			[
				"tracking_code",
				"status",
				"creation",
				"category",
				"resolution_date",
				"appeal_submitted",
				"appeal_date",
				"appeal_reason",
				"accepted_date",
				"contact_info_type",
				"contact_information",
				"rating",
				"rating_submitted_at",
			],
			as_dict=True,
		)

		# Get status name
		status_name = ""
		if issue.status:
			status_name = frappe.db.get_value("GRM Issue Status", issue.status, "status_name") or ""

		# Get category name
		category_name = ""
		if issue.category:
			category_name = frappe.db.get_value("GRM Issue Category", issue.category, "category_name") or ""

		# Determine if citizen has a contact channel (drives rating UX)
		contact_channel = None
		if issue.contact_information:
			cit = (issue.contact_info_type or "").lower()
			if "phone" in cit:
				contact_channel = "phone"
			elif "mail" in cit or "email" in cit:
				contact_channel = "email"

		# Build response (NO PII)
		response = {
			"status": "success",
			"data": {
				"tracking_code": issue.tracking_code,
				"status": status_name,
				"category": category_name,
				"submission_date": issue.creation.strftime("%Y-%m-%d %H:%M") if issue.creation else None,
				"acknowledged_date": issue.accepted_date.strftime("%Y-%m-%d")
				if issue.accepted_date
				else None,
				"resolution_date": issue.resolution_date.strftime("%Y-%m-%d")
				if issue.resolution_date
				else None,
				"appeal_submitted": bool(issue.appeal_submitted),
				"appeal_date": issue.appeal_date.strftime("%Y-%m-%d %H:%M") if issue.appeal_date else None,
				"appeal_reason": issue.appeal_reason or "",
				"contact_channel": contact_channel,
				"rating": issue.rating or 0,
				"rated": bool(issue.rating_submitted_at),
				"rating_submitted_at": issue.rating_submitted_at.strftime("%Y-%m-%d %H:%M")
				if issue.rating_submitted_at
				else None,
			},
		}

		return response

	except Exception as e:
		frappe.log_error(f"Tracking error: {e!s}", "Public Tracking API")
		return {"status": "error", "message": _("Error retrieving complaint status")}


@frappe.whitelist(allow_guest=True, methods=["POST", "GET"])
def add_comment(*args, **kwargs):
	"""PC-13 documented-gap stub.

	The eGRM public portal does NOT expose a citizen-comment endpoint
	on a tracked issue. Hitting this path always returns HTTP 404; the
	AQE contract test asserts that none of the plausible "add comment"
	paths resolve as a real feature. Replace this stub if/when public
	commenting becomes a real feature.
	"""
	frappe.local.response.http_status_code = 404
	return {
		"status": "error",
		"message": _("Public citizen-comment endpoint is not available."),
	}
