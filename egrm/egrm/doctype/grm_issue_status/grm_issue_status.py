import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueStatus(Document):
	def validate(self):
		try:
			self.sync_project_field()
			self.validate_unique_type()
			self.validate_project_links()
			frappe.log(f"Validating GRM Issue Status {self.name}")
		except Exception as e:
			frappe.log_error(f"Error validating GRM Issue Status: {e!s}")
			raise

	def sync_project_field(self):
		"""Mirror the first child-table project into the top-level `project`
		Link field so REST queries `filters=[["project","=","..."]]` work
		without joining the child table."""
		if self.grm_project_link:
			first_project = self.grm_project_link[0].project
			if first_project and self.project != first_project:
				self.project = first_project

	def validate_unique_type(self):
		try:
			# Coerce `initial_status` upfront — form-encoded REST POSTs
			# arrive as strings ("0" / "1") and Python's bool("0") is
			# True, which would let multiple statuses claim the
			# "initial" slot for a project.
			from frappe.utils import cint

			init_flag = cint(self.initial_status) if self.initial_status not in (None, "") else 0
			self.initial_status = init_flag
			# Skip the uniqueness check entirely when this row isn't
			# claiming the initial-status slot. The previous version
			# treated a string "0" as truthy which fired the check
			# spuriously.
			if not init_flag:
				return
			# Count how many initial statuses we have per project
			seen_projects: set[str] = set()
			for link in self.grm_project_link:
				# The same project can appear multiple times in the
				# child table while we're saving; only check once per
				# project.
				if link.project in seen_projects:
					continue
				seen_projects.add(link.project)
				initial_statuses = frappe.db.sql(
					"""
                    SELECT s.name
                    FROM `tabGRM Issue Status` s
                    INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
                    WHERE s.initial_status = 1
                    AND p.project = %s
                    AND s.name != %s
                    AND COALESCE(s.name, '') != ''
                """,
					(link.project, self.name or ""),
					as_dict=1,
				)

				if initial_statuses:
					frappe.throw(
						_("Project {0} already has an initial status: {1}").format(
							link.project, initial_statuses[0].name
						)
					)
		except Exception as e:
			frappe.log_error(f"Error validating unique status type: {e!s}")
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
					frappe.throw(_("Duplicate project {0} in project links").format(link.project))
				projects[link.project] = True
		except Exception as e:
			frappe.log_error(f"Error validating project links: {e!s}")
			raise
