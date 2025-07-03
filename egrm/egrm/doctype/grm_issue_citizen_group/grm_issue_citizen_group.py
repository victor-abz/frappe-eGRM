import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueCitizenGroup(Document):
    def validate(self):
        try:
            self.validate_project_links()
            frappe.log(f"Validating GRM Issue Citizen Group {self.name}")
        except Exception as e:
            frappe.log_error(f"Error validating GRM Issue Citizen Group: {str(e)}")
            raise

    def validate_project_links(self):
        try:
            # Ensure there is at least one project linked
            if not self.grm_project_link or len(self.grm_project_link) == 0:
                frappe.throw(
                    _("At least one project must be linked to the citizen group")
                )

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
