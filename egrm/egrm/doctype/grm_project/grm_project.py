import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMProject(Document):
    def validate(self):
        try:
            self.validate_dates()
            self.validate_notification_templates()
            # Ensure project code uniqueness - this is already handled by unique field in DocType
            frappe.log(f"Validating GRM Project {self.name}")
        except Exception as e:
            frappe.log_error(f"Error validating GRM Project: {str(e)}")
            raise

    def validate_notification_templates(self):
        """Ensure selected templates are active and compatible"""
        template_fields = [
            'receipt_template', 'acknowledgment_template', 'in_progress_template',
            'resolved_template', 'closed_template', 'escalated_template',
            'sla_reminder_template'
        ]
        for field in template_fields:
            template_name = self.get(field)
            if template_name:
                template = frappe.get_doc("GRM Notification Template", template_name)
                if not template.active:
                    frappe.throw(_("Template {0} is not active").format(template_name))
                if template.project and template.project != self.name:
                    frappe.throw(_("Template {0} belongs to another project").format(template_name))

    def validate_dates(self):
        try:
            if self.start_date and self.end_date and self.start_date > self.end_date:
                frappe.throw(_("End Date cannot be before Start Date"))
        except Exception as e:
            frappe.log_error(f"Error validating dates for GRM Project: {str(e)}")
            raise

    def after_insert(self):
        try:
            # Create default configuration items on project creation
            self.create_default_statuses()
            self.create_default_issue_types()
            self.create_default_departments()
            frappe.log(f"Created default configuration for project {self.name}")
        except Exception as e:
            frappe.log_error(
                f"Error creating default configurations for project {self.name}: {str(e)}"
            )
            frappe.throw(
                _("Error creating default configurations. Please check the logs.")
            )

    def create_default_statuses(self):
        try:
            # Create default statuses for this project
            default_statuses = [
                {"status_name": "Open", "initial_status": 1},
                {"status_name": "In Progress", "open_status": 1},
                {"status_name": "Resolved", "final_status": 1},
                {"status_name": "Closed", "final_status": 1},
                {"status_name": "Rejected", "rejected_status": 1},
            ]

            for status in default_statuses:
                if not frappe.db.exists(
                    "GRM Issue Status", {"status_name": status["status_name"]}
                ):
                    doc = frappe.new_doc("GRM Issue Status")
                    doc.update(status)
                    doc.append("grm_project_link", {"project": self.name})
                    doc.insert()
                    frappe.log(
                        f"Created default status {status['status_name']} for project {self.name}"
                    )
        except Exception as e:
            frappe.log_error(f"Error creating default statuses: {str(e)}")
            raise

    def create_default_issue_types(self):
        try:
            # Create default issue types for this project
            default_types = [
                {"type_name": "Complaint"},
                {"type_name": "Inquiry"},
                {"type_name": "Feedback"},
            ]

            for issue_type in default_types:
                if not frappe.db.exists(
                    "GRM Issue Type", {"type_name": issue_type["type_name"]}
                ):
                    doc = frappe.new_doc("GRM Issue Type")
                    doc.update(issue_type)
                    doc.append("grm_project_link", {"project": self.name})
                    doc.insert()
                    frappe.log(
                        f"Created default issue type {issue_type['type_name']} for project {self.name}"
                    )
        except Exception as e:
            frappe.log_error(f"Error creating default issue types: {str(e)}")
            raise

    def create_default_departments(self):
        try:
            # Create a default department for this project
            if not frappe.db.exists(
                "GRM Issue Department", {"department_name": "General"}
            ):
                doc = frappe.new_doc("GRM Issue Department")
                doc.department_name = "General"
                doc.append("grm_project_link", {"project": self.name})
                doc.insert()
                frappe.log(f"Created default department for project {self.name}")
        except Exception as e:
            frappe.log_error(f"Error creating default department: {str(e)}")
            raise
