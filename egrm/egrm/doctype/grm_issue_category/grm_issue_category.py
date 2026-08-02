import logging

import frappe
from frappe import _
from frappe.model.document import Document

log = logging.getLogger(__name__)


class GRMIssueCategory(Document):
	def validate(self):
		try:
			self.sync_project_field()
			self.validate_project_links()
			self.validate_routing_target()
			self.validate_departments()
			frappe.log(f"Validating GRM Issue Category {self.name}")
		except Exception as e:
			frappe.log_error(f"Error validating GRM Issue Category: {e!s}")
			raise

	def validate_routing_target(self):
		"""Enforce Role-only routing.

		Categories must route to a Role; ``assigned_role`` is required and
		must belong to the same project. Department routing is no longer
		supported — the resolver picks a User directly from the role +
		region + duty matrix. Saving a Department-typed category surfaces a
		clear error so the wizard can prompt the operator to migrate.
		"""
		# Coerce legacy NULL → Role so operators don't get a confusing
		# "Department required" error on pre-migration rows; they still
		# need to fill in a role before the row will save.
		if not self.routing_target_type:
			self.routing_target_type = "Role"
		if self.routing_target_type != "Role":
			frappe.throw(
				_(
					"Route To must be 'Role'. Department-based routing is no "
					"longer supported — pick a Role for this category."
				)
			)
		if not self.assigned_role:
			frappe.throw(_("Assigned Role is required."))
		role_project = frappe.db.get_value("GRM Project Role", self.assigned_role, "project")
		if role_project and self.project and role_project != self.project:
			frappe.throw(
				_("Assigned Role {0} does not belong to project {1}").format(self.assigned_role, self.project)
			)
		# Department field is no longer used for routing; clear it so the
		# value can't drift back into stale UIs.
		if self.assigned_department:
			self.assigned_department = None

	def sync_project_field(self):
		"""Mirror the first child-table project into the top-level `project`
		Link field so REST queries `filters=[["project","=","..."]]` work
		without joining the child table."""
		if self.grm_project_link:
			first_project = self.grm_project_link[0].project
			if first_project and self.project != first_project:
				self.project = first_project

	def validate_project_links(self):
		try:
			# Ensure there is at least one project linked
			if not self.grm_project_link or len(self.grm_project_link) == 0:
				frappe.throw(_("At least one project must be linked to the issue category"))

			# Check for duplicate project links
			projects = {}
			for link in self.grm_project_link:
				if link.project in projects:
					frappe.throw(_("Duplicate project {0} in project links").format(link.project))
				projects[link.project] = True
		except Exception as e:
			frappe.log_error(f"Error validating project links: {e!s}")
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
							_("Assigned department {0} is not linked to project {1}").format(
								self.assigned_department, project
							)
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
							_("Assigned appeal department {0} is not linked to project {1}").format(
								self.assigned_appeal_department, project
							)
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
							_("Assigned escalation department {0} is not linked to project {1}").format(
								self.assigned_escalation_department, project
							)
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
							_("Administrative level {0} is not linked to project {1}").format(
								self.administrative_level, project
							)
						)
		except Exception as e:
			frappe.log_error(f"Error validating departments: {e!s}")
			raise
