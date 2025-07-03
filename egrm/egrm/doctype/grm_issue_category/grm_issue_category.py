import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueCategory(Document):
    def validate(self):
        try:
            self.validate_project_links()
            self.validate_departments()
            frappe.log(f"Validating GRM Issue Category {self.name}")
        except Exception as e:
            frappe.log_error(f"Error validating GRM Issue Category: {str(e)}")
            raise

    def validate_project_links(self):
        try:
            # Ensure there is at least one project linked
            if not self.grm_project_link or len(self.grm_project_link) == 0:
                frappe.throw(
                    _("At least one project must be linked to the issue category")
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

    def validate_departments(self):
        try:
            # Ensure assigned department is linked to all projects in the grm_project_link
            project_links = [d.project for d in self.grm_project_link]

            # Check assigned department
            if self.assigned_department:
                dept_projects = frappe.db.sql(
                    """
                    SELECT project FROM `tabGRM Project Link`
                    WHERE parent = %s
                """,
                    (self.assigned_department),
                    as_dict=1,
                )

                dept_project_list = [d.project for d in dept_projects]

                for project in project_links:
                    if project not in dept_project_list:
                        frappe.throw(
                            _(
                                "Assigned department {0} is not linked to project {1}"
                            ).format(self.assigned_department, project)
                        )

            # Check appeal department
            if self.assigned_appeal_department:
                dept_projects = frappe.db.sql(
                    """
                    SELECT project FROM `tabGRM Project Link`
                    WHERE parent = %s
                """,
                    (self.assigned_appeal_department),
                    as_dict=1,
                )

                dept_project_list = [d.project for d in dept_projects]

                for project in project_links:
                    if project not in dept_project_list:
                        frappe.throw(
                            _(
                                "Assigned appeal department {0} is not linked to project {1}"
                            ).format(self.assigned_appeal_department, project)
                        )

            # Check escalation department
            if self.assigned_escalation_department:
                dept_projects = frappe.db.sql(
                    """
                    SELECT project FROM `tabGRM Project Link`
                    WHERE parent = %s
                """,
                    (self.assigned_escalation_department),
                    as_dict=1,
                )

                dept_project_list = [d.project for d in dept_projects]

                for project in project_links:
                    if project not in dept_project_list:
                        frappe.throw(
                            _(
                                "Assigned escalation department {0} is not linked to project {1}"
                            ).format(self.assigned_escalation_department, project)
                        )

            # Check administrative level
            if self.administrative_level:
                for project in project_links:
                    admin_level_exists = frappe.db.exists(
                        "GRM Administrative Level Type",
                        {"name": self.administrative_level, "project": project},
                    )

                    if not admin_level_exists:
                        frappe.throw(
                            _(
                                "Administrative level {0} is not linked to project {1}"
                            ).format(self.administrative_level, project)
                        )
        except Exception as e:
            frappe.log_error(f"Error validating departments: {str(e)}")
            raise
