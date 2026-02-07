import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMAdministrativeLevelType(Document):
    def validate(self):
        try:
            self.validate_level_order()
            self.validate_sla_config()
            frappe.log(f"Validating GRM Administrative Level Type {self.name}")
        except Exception as e:
            frappe.log_error(
                f"Error validating GRM Administrative Level Type: {str(e)}"
            )
            raise

    def validate_level_order(self):
        try:
            if self.level_order < 0:
                frappe.throw(_("Level Order cannot be negative"))
        except Exception as e:
            frappe.log_error(f"Error validating level order: {str(e)}")
            raise

    def validate_sla_config(self):
        if self.acknowledgment_days and self.resolution_days:
            if self.acknowledgment_days >= self.resolution_days:
                frappe.throw(_("Acknowledgment days must be less than resolution days"))
        if self.reminder_before_days and self.resolution_days:
            if self.reminder_before_days >= self.resolution_days:
                frappe.throw(_("Reminder days must be less than resolution days"))

    def get_sla_config(self):
        return {
            'acknowledgment_days': self.acknowledgment_days or 7,
            'resolution_days': self.resolution_days or 30,
            'reminder_before_days': self.reminder_before_days or 2,
            'auto_escalate': self.auto_escalate
        }
