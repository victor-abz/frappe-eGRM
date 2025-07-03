import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMAdministrativeLevelType(Document):
    def validate(self):
        try:
            self.validate_level_order()
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
