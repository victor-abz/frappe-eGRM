import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueDepartment(Document):
	def validate(self):
		try:
			self.sync_project_field()
			self.validate_head()
			self.validate_project_links()
			frappe.log(f"Validating GRM Issue Department {self.name}")
		except Exception as e:
			frappe.log_error(f"Error validating GRM Issue Department: {e!s}")
			raise

	def sync_project_field(self):
		"""Mirror the first child-table project into the top-level `project`
		Link field so REST queries `filters=[["project","=","..."]]` work
		without joining the child table."""
		if self.grm_project_link:
			first_project = self.grm_project_link[0].project
			if first_project and self.project != first_project:
				self.project = first_project

	def validate_head(self):
		try:
			if self.head:
				# Check if the user exists
				if not frappe.db.exists("User", self.head):
					frappe.throw(_("User {0} does not exist").format(self.head))
		except Exception as e:
			frappe.log_error(f"Error validating department head: {e!s}")
			raise

	def validate_project_links(self):
		try:
			# Ensure there is at least one project linked
			if not self.grm_project_link or len(self.grm_project_link) == 0:
				frappe.throw(_("At least one project must be linked to the department"))

			# Check for duplicate project links
			projects = {}
			for link in self.grm_project_link:
				if link.project in projects:
					frappe.throw(_("Duplicate project {0} in project links").format(link.project))
				projects[link.project] = True
		except Exception as e:
			frappe.log_error(f"Error validating project links: {e!s}")
			raise
