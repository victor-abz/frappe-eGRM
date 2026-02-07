# Copyright (c) 2025, eGRM and contributors
# For license information, please see license.txt

"""
SLA Manager for GRM Issues

Handles:
- SLA calculation based on administrative level
- SLA status tracking (On Time, Nearing Due, Breached)
- Automatic escalation when SLA breached
- Reminder notifications before SLA expiration
"""

import frappe
from frappe import _
from frappe.utils import (
	getdate, nowdate, add_days, date_diff,
	now_datetime
)


class SLAManager:
	"""Manages SLA tracking and escalation for GRM Issues"""

	def __init__(self, issue_doc):
		self.issue = issue_doc
		self.level_config = None

	def initialize_sla(self):
		"""Initialize SLA when issue is created or administrative region changes."""
		if not self.issue.administrative_region:
			return

		self.level_config = self.get_level_sla_config()
		if not self.level_config:
			return

		self.issue.sla_acknowledgment_days = self.level_config["acknowledgment_days"]
		self.issue.sla_resolution_days = self.level_config["resolution_days"]

		creation_date = getdate(self.issue.creation or nowdate())
		self.issue.sla_acknowledgment_due = add_business_days(
			creation_date, self.level_config["acknowledgment_days"]
		)
		self.issue.sla_resolution_due = add_business_days(
			creation_date, self.level_config["resolution_days"]
		)

		self.issue.sla_acknowledgment_status = "On Time"
		self.issue.sla_resolution_status = "On Time"
		self.update_days_remaining()

	def get_level_sla_config(self):
		"""Get SLA configuration from administrative level type."""
		try:
			region = frappe.get_doc(
				"GRM Administrative Region", self.issue.administrative_region
			)
			level_type = frappe.get_doc(
				"GRM Administrative Level Type", region.administrative_level
			)
			return level_type.get_sla_config()
		except Exception:
			return None

	def update_sla_status(self):
		"""Update SLA status fields based on current dates."""
		if not self.issue.sla_acknowledgment_due and not self.issue.sla_resolution_due:
			return

		if not self.level_config:
			self.level_config = self.get_level_sla_config() or {}

		reminder_days = self.level_config.get("reminder_before_days", 2) if self.level_config else 2

		# Get statuses that represent acknowledged states
		acknowledged_statuses = _get_status_names_beyond_initial()

		# Update acknowledgment SLA status (only if not yet acknowledged)
		current_status_name = _get_status_display_name(self.issue.status)
		if current_status_name not in acknowledged_statuses:
			new_ack_status = self._calculate_sla_status(
				self.issue.sla_acknowledgment_due, reminder_days,
				self.issue.sla_acknowledgment_breached_date
			)
			self.issue.sla_acknowledgment_status = new_ack_status

			if new_ack_status == "Breached" and not self.issue.sla_acknowledgment_breached_date:
				self.issue.sla_acknowledgment_breached_date = now_datetime()

		# Get final statuses
		final_statuses = _get_final_status_names()

		# Update resolution SLA status (only if not resolved/closed)
		if current_status_name not in final_statuses:
			new_res_status = self._calculate_sla_status(
				self.issue.sla_resolution_due, reminder_days,
				self.issue.sla_resolution_breached_date
			)
			self.issue.sla_resolution_status = new_res_status

			if new_res_status == "Breached" and not self.issue.sla_resolution_breached_date:
				self.issue.sla_resolution_breached_date = now_datetime()

		self.update_days_remaining()

	def _calculate_sla_status(self, due_date, reminder_days, breach_date):
		"""Calculate SLA status (On Time, Nearing Due, Breached)."""
		if breach_date:
			return "Breached"

		if not due_date:
			return "On Time"

		today = getdate(nowdate())
		due = getdate(due_date)
		days_until_due = date_diff(due, today)

		if days_until_due < 0:
			return "Breached"
		elif days_until_due <= reminder_days:
			return "Nearing Due"
		return "On Time"

	def update_days_remaining(self):
		"""Calculate and update days remaining for resolution SLA."""
		if not self.issue.sla_resolution_due:
			return
		today = getdate(nowdate())
		due = getdate(self.issue.sla_resolution_due)
		self.issue.sla_days_remaining = date_diff(due, today)

	def check_and_escalate(self):
		"""Check if SLA is breached and escalate if configured."""
		if self.issue.sla_resolution_status != "Breached":
			return False

		if not self.level_config:
			self.level_config = self.get_level_sla_config() or {}

		if not self.level_config.get("auto_escalate"):
			return False

		final_statuses = _get_final_status_names()
		current_status_name = _get_status_display_name(self.issue.status)
		if current_status_name in final_statuses:
			return False

		return self.escalate_to_parent_level()

	def escalate_to_parent_level(self):
		"""Escalate issue to parent administrative region."""
		try:
			current_region = frappe.get_doc(
				"GRM Administrative Region", self.issue.administrative_region
			)
		except Exception:
			return False

		if not current_region.parent_region:
			return False

		old_region = self.issue.administrative_region
		self.issue.administrative_region = current_region.parent_region

		# Recalculate SLA with new level
		self.initialize_sla()

		self.issue.escalation_count = (self.issue.escalation_count or 0) + 1
		self.issue.last_escalated_date = now_datetime()
		self.issue.sla_escalation_reason = (
			f"SLA breach - escalated from {old_region} to {current_region.parent_region}"
		)

		self.issue.add_comment(
			"Info",
			f"Issue auto-escalated to {current_region.parent_region} due to SLA breach"
		)

		self.issue.save(ignore_permissions=True)

		# Send escalation notification
		try:
			self.issue.send_notification("escalated")
		except Exception:
			pass

		return True

	def should_send_reminder(self):
		"""Check if reminder notification should be sent."""
		if not self.level_config:
			self.level_config = self.get_level_sla_config() or {}

		if not self.level_config:
			return False, None

		reminder_days = self.level_config.get("reminder_before_days", 2)
		today = getdate(nowdate())

		# Check acknowledgment reminder
		acknowledged_statuses = _get_status_names_beyond_initial()
		current_status_name = _get_status_display_name(self.issue.status)

		if current_status_name not in acknowledged_statuses and self.issue.sla_acknowledgment_due:
			days_until = date_diff(getdate(self.issue.sla_acknowledgment_due), today)
			if days_until == reminder_days:
				return True, "acknowledgment"

		# Check resolution reminder
		final_statuses = _get_final_status_names()
		if current_status_name not in final_statuses and self.issue.sla_resolution_due:
			days_until = date_diff(getdate(self.issue.sla_resolution_due), today)
			if days_until == reminder_days:
				return True, "resolution"

		return False, None


# Helper functions

def add_business_days(start_date, days):
	"""Add business days to a date (excluding weekends)."""
	current = getdate(start_date)
	added = 0
	while added < days:
		current = add_days(current, 1)
		if current.weekday() not in [5, 6]:
			added += 1
	return current


def _get_final_status_names():
	"""Get display names of statuses marked as final."""
	return [s.status_name for s in frappe.get_all(
		"GRM Issue Status", filters={"final_status": 1}, fields=["status_name"]
	)]


def _get_status_names_beyond_initial():
	"""Get display names of statuses beyond initial (open) status."""
	return [s.status_name for s in frappe.get_all(
		"GRM Issue Status",
		filters={"initial_status": 0, "open_status": 0},
		fields=["status_name"]
	)]


def _get_status_display_name(status_id):
	"""Get the display name for a status ID."""
	if not status_id:
		return ""
	try:
		return frappe.db.get_value("GRM Issue Status", status_id, "status_name") or ""
	except Exception:
		return ""


@frappe.whitelist()
def get_sla_dashboard_data(project=None):
	"""Get SLA dashboard data for reporting."""
	conditions = ["gi.docstatus = 1"]
	values = {}

	if project:
		conditions.append("gi.project = %(project)s")
		values["project"] = project

	final_statuses = frappe.get_all(
		"GRM Issue Status", filters={"final_status": 1}, pluck="name"
	)
	if final_statuses:
		conditions.append("gi.status NOT IN %(final_statuses)s")
		values["final_statuses"] = final_statuses

	query = """
		SELECT
			COUNT(*) as total_issues,
			SUM(CASE WHEN sla_acknowledgment_status = 'On Time' THEN 1 ELSE 0 END) as ack_on_time,
			SUM(CASE WHEN sla_acknowledgment_status = 'Nearing Due' THEN 1 ELSE 0 END) as ack_nearing,
			SUM(CASE WHEN sla_acknowledgment_status = 'Breached' THEN 1 ELSE 0 END) as ack_breached,
			SUM(CASE WHEN sla_resolution_status = 'On Time' THEN 1 ELSE 0 END) as res_on_time,
			SUM(CASE WHEN sla_resolution_status = 'Nearing Due' THEN 1 ELSE 0 END) as res_nearing,
			SUM(CASE WHEN sla_resolution_status = 'Breached' THEN 1 ELSE 0 END) as res_breached,
			SUM(CASE WHEN escalation_count > 0 THEN 1 ELSE 0 END) as escalated_issues
		FROM `tabGRM Issue` gi
		WHERE {conditions}
	""".format(conditions=" AND ".join(conditions))

	result = frappe.db.sql(query, values, as_dict=True)[0]

	return {
		"total_active_issues": result.total_issues or 0,
		"acknowledgment": {
			"on_time": result.ack_on_time or 0,
			"nearing_due": result.ack_nearing or 0,
			"breached": result.ack_breached or 0,
		},
		"resolution": {
			"on_time": result.res_on_time or 0,
			"nearing_due": result.res_nearing or 0,
			"breached": result.res_breached or 0,
		},
		"escalation": {
			"total_escalated": result.escalated_issues or 0,
		},
	}
