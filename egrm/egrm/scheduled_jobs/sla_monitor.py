# Copyright (c) 2025, eGRM and contributors
# For license information, please see license.txt

"""
SLA Monitoring Scheduler

Runs daily to:
1. Update SLA status for all active issues
2. Send reminder notifications
3. Auto-escalate breached issues
"""

import frappe
from frappe.utils import nowdate


def monitor_sla():
	"""
	Main scheduled function to monitor SLA for all active issues.
	Runs daily via hooks.py scheduler configuration.
	"""
	frappe.logger().info("Starting SLA monitoring job...")

	from egrm.egrm.utils.sla_manager import SLAManager

	# Get final statuses to exclude
	final_statuses = frappe.get_all(
		"GRM Issue Status", filters={"final_status": 1}, pluck="name"
	)

	filters = {
		"docstatus": 1,
		"sla_resolution_due": ["is", "set"],
	}
	if final_statuses:
		filters["status"] = ["not in", final_statuses]

	active_issues = frappe.get_all("GRM Issue", filters=filters, pluck="name")

	stats = {
		"processed": 0,
		"reminders_sent": 0,
		"escalated": 0,
		"errors": 0,
	}

	for issue_name in active_issues:
		try:
			issue = frappe.get_doc("GRM Issue", issue_name)
			sla_manager = SLAManager(issue)

			# Update SLA status
			sla_manager.update_sla_status()

			# Check if reminder should be sent
			should_remind, reminder_type = sla_manager.should_send_reminder()
			if should_remind:
				issue.send_notification("sla_reminder")
				stats["reminders_sent"] += 1

			# Check and perform escalation if needed
			if sla_manager.check_and_escalate():
				stats["escalated"] += 1
			else:
				# Save updated SLA fields (escalation already saves)
				issue.save(ignore_permissions=True)

			stats["processed"] += 1

		except Exception as e:
			stats["errors"] += 1
			frappe.log_error(
				f"SLA monitoring error for {issue_name}: {e}",
				"SLA Monitor Error",
			)

	frappe.logger().info(
		f"SLA monitoring completed: {stats['processed']} processed, "
		f"{stats['reminders_sent']} reminders, {stats['escalated']} escalated, "
		f"{stats['errors']} errors"
	)

	if stats["escalated"] > 0 or stats["errors"] > 0:
		_notify_admins_sla_summary(stats)

	frappe.db.commit()


def _notify_admins_sla_summary(stats):
	"""Send summary notification to GRM admins."""
	subject = f"SLA Monitoring Summary - {nowdate()}"
	message = f"""
	<h3>GRM SLA Monitoring Daily Summary</h3>
	<ul>
		<li><strong>Issues Processed:</strong> {stats['processed']}</li>
		<li><strong>Reminders Sent:</strong> {stats['reminders_sent']}</li>
		<li><strong>Auto-Escalated:</strong> {stats['escalated']}</li>
		<li><strong>Errors:</strong> {stats['errors']}</li>
	</ul>
	<p>Review issues with breached SLAs in the GRM Issue list.</p>
	"""

	admins = frappe.get_all(
		"Has Role", filters={"role": "GRM Administrator"}, pluck="parent"
	)
	if admins:
		frappe.sendmail(recipients=list(set(admins)), subject=subject, message=message)
