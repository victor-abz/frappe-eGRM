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
            # The wizard's Step 7 creates project-specific statuses /
            # types / departments explicitly; auto-seeding here would
            # collide with them (e.g. duplicate initial-status, see
            # AQE OB-RW-WB.status.Open). Auto-seed ONLY when the wizard
            # is NOT in flight, by checking whether a flag was set on
            # the doc to opt out, or by skipping seeding if the doc was
            # created via the REST `/api/resource/...` path that the
            # wizard uses.
            #
            # Heuristic: the wizard's step1 sets `current_setup_step=0`
            # (server-managed default) and does NOT pre-populate any
            # of these fields. We seed defaults ONLY for projects that
            # are explicitly opted-in via the `seed_default_config`
            # custom flag (e.g. for legacy bench-console creation).
            if not getattr(self.flags, "seed_default_config", False):
                frappe.log(
                    f"Skipping default seed for project {self.name} "
                    "(wizard owns its catalog)."
                )
                return
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
            # Default statuses are scoped to THIS project — the
            # uniqueness key is (status_name, project), not just
            # status_name. Without the project predicate, a "Resolved"
            # status created for project A blocked seeding for B.
            default_statuses = [
                {"status_name": "Open", "initial_status": 1},
                {"status_name": "In Progress", "open_status": 1},
                {"status_name": "Resolved", "final_status": 1},
                {"status_name": "Closed", "final_status": 1},
                {"status_name": "Rejected", "rejected_status": 1},
            ]

            for status in default_statuses:
                if _project_link_exists(
                    "GRM Issue Status", status["status_name"],
                    "status_name", self.name,
                ):
                    continue
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
            default_types = [
                {"type_name": "Complaint"},
                {"type_name": "Inquiry"},
                {"type_name": "Feedback"},
            ]

            for issue_type in default_types:
                if _project_link_exists(
                    "GRM Issue Type", issue_type["type_name"],
                    "type_name", self.name,
                ):
                    continue
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
            if _project_link_exists(
                "GRM Issue Department", "General",
                "department_name", self.name,
            ):
                return
            doc = frappe.new_doc("GRM Issue Department")
            doc.department_name = "General"
            doc.append("grm_project_link", {"project": self.name})
            doc.insert()
            frappe.log(f"Created default department for project {self.name}")
        except Exception as e:
            frappe.log_error(f"Error creating default department: {str(e)}")
            raise


def _project_link_exists(
    doctype: str, name_value: str, name_field: str, project: str,
) -> bool:
    """Return True if a doc of `doctype` with the given name field is
    already linked to `project` via `grm_project_link`.

    Replaces the bare `frappe.db.exists(doctype, {name_field: ...})`
    check that previously caused cross-project leakage: a "Resolved"
    status seeded for project A blocked seeding for project B because
    the existence check ignored the project link."""
    return bool(frappe.db.sql(
        f"""
        SELECT 1 FROM `tab{doctype}` d
        JOIN `tabGRM Project Link` pl ON pl.parent = d.name
        WHERE d.{name_field} = %s
          AND pl.project = %s
          AND pl.parenttype = %s
        LIMIT 1
        """,
        (name_value, project, doctype),
    ))
