import logging

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

log = logging.getLogger(__name__)


class GRMAdministrativeLevelType(Document):
    def validate(self):
        try:
            # Form-encoded REST POSTs deliver Int/Check fields as strings.
            # Coerce upfront so every downstream comparison is numeric.
            self._coerce_int_fields()
            self.validate_level_order()
            self.validate_sla_config()
            self.validate_project_scoped_uniqueness()
            frappe.log(f"Validating GRM Administrative Level Type {self.name}")
        except Exception as e:
            frappe.log_error(
                f"Error validating GRM Administrative Level Type: {str(e)}"
            )
            raise

    def _coerce_int_fields(self) -> None:
        for fieldname in (
            "level_order",
            "acknowledgment_days",
            "resolution_days",
            "reminder_before_days",
            "auto_escalate",
        ):
            value = self.get(fieldname)
            if value is None or value == "":
                continue
            if isinstance(value, str):
                self.set(fieldname, cint(value))

    def validate_project_scoped_uniqueness(self):
        # Records use hash autoname; controller-level uniqueness on
        # (project, level_name) gives a clear error and prevents duplicates
        # within a project (level_name is the title_field shown to users).
        if not (self.project and self.level_name):
            return
        existing = frappe.db.get_value(
            "GRM Administrative Level Type",
            {
                "project": self.project,
                "level_name": self.level_name,
                "name": ["!=", self.name],
            },
            "name",
        )
        if existing:
            frappe.throw(
                _("Level Name '{0}' already exists for project {1}.").format(
                    self.level_name, self.project
                )
            )

    def validate_level_order(self):
        try:
            if cint(self.level_order) < 0:
                frappe.throw(_("Level Order cannot be negative"))
        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(f"Error validating level order: {str(e)}")
            raise

    def validate_sla_config(self):
        ack = cint(self.acknowledgment_days) if self.acknowledgment_days else 0
        res = cint(self.resolution_days) if self.resolution_days else 0
        rem = cint(self.reminder_before_days) if self.reminder_before_days else 0
        if ack and res and ack >= res:
            frappe.throw(_("Acknowledgment days must be less than resolution days"))
        if rem and res and rem >= res:
            frappe.throw(_("Reminder days must be less than resolution days"))

    def get_sla_config(self):
        return {
            'acknowledgment_days': self.acknowledgment_days or 7,
            'resolution_days': self.resolution_days or 30,
            'reminder_before_days': self.reminder_before_days or 2,
            'auto_escalate': self.auto_escalate
        }
