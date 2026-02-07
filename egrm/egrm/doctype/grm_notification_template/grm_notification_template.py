# Copyright (c) 2025, eGRM and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GRMNotificationTemplate(Document):
	def validate(self):
		if not self.email_template and not self.enable_sms:
			frappe.throw(_("Please configure at least one notification channel (Email or SMS)"))

		if self.enable_sms and self.sms_message:
			try:
				frappe.render_template(self.sms_message, {
					"tracking_code": "TEST-001",
					"subject": "Test",
					"status": "Open"
				})
			except Exception as e:
				frappe.throw(_("Invalid Jinja2 syntax in SMS message: {0}").format(str(e)))

	def render_sms(self, context):
		if not self.enable_sms or not self.sms_message:
			return None
		return frappe.render_template(self.sms_message, context)
