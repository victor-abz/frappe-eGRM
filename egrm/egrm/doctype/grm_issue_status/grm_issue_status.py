import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueStatus(Document):
    def validate(self):
        try:
            self.validate_unique_type()
            self.validate_project_links()
            frappe.log(f"Validating GRM Issue Status {self.name}")
        except Exception as e:
            frappe.log_error(f"Error validating GRM Issue Status: {str(e)}")
            raise

    def validate_unique_type(self):
        try:
            # Count how many initial statuses we have per project
            for link in self.grm_project_link:
                if self.initial_status:
                    initial_statuses = frappe.db.sql(
                        """
                        SELECT s.name
                        FROM `tabGRM Issue Status` s
                        INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
                        WHERE s.initial_status = 1
                        AND p.project = %s
                        AND s.name != %s
                    """,
                        (link.project, self.name),
                        as_dict=1,
                    )

                    if initial_statuses:
                        frappe.throw(
                            _("Project {0} already has an initial status: {1}").format(
                                link.project, initial_statuses[0].name
                            )
                        )
        except Exception as e:
            frappe.log_error(f"Error validating unique status type: {str(e)}")
            raise

    def validate_project_links(self):
        try:
            # Ensure there is at least one project linked
            if not self.grm_project_link or len(self.grm_project_link) == 0:
                frappe.throw(_("At least one project must be linked to the status"))

            # Check for duplicate project links
            projects = {}
            for link in self.grm_project_link:
                if link.project in projects:
                    frappe.throw(
                        _("Duplicate project {0} in project links").format(link.project)
                    )
                projects[link.project] = True
        except Exception as e:
            frappe.log_error(f"Error validating project links: {str(e)}")
            raise
