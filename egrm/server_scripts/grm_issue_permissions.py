import logging

import frappe

from egrm.server_scripts.issue_scope import (
	handled_by_user_condition,
	is_in_user_scope,
	region_condition,
	sql_literal,
	user_region_scope,
)

log = logging.getLogger(__name__)

# Duty-driven scope. Each ptype is satisfied if the user holds at least
# one of these duties on the issue's project. Field-level mutation is
# constrained separately by GRMIssue._enforce_duty_field_constraints.
PTYPE_DUTIES: dict[str, tuple[str, ...]] = {
	"create": ("Intake",),
	"read": ("Intake", "Review", "Assignment", "Investigate & Resolve", "Feedback"),
	"write": ("Review", "Assignment", "Investigate & Resolve", "Feedback"),
	"submit": ("Review", "Assignment", "Investigate & Resolve"),
	"cancel": ("Review",),
	"delete": (),  # bypass roles only
	"print": ("Intake", "Review", "Assignment", "Investigate & Resolve", "Feedback"),
	"email": ("Review", "Assignment", "Investigate & Resolve", "Feedback"),
	"report": ("Intake", "Review", "Assignment", "Investigate & Resolve", "Feedback"),
}

BYPASS_ROLES: tuple[str, ...] = (
	"System Manager",
	"GRM Platform Administrator",
	"GRM Supervise",
)


def _user_duties_for_project(user: str, project: str) -> set[str]:
	"""Resolve the set of duty names this user holds on this project,
	via active+activated assignments → roles → role-duty rows."""
	if not user or not project or user == "Guest":
		return set()
	role_names = frappe.get_all(
		"GRM User Project Assignment",
		filters={
			"user": user,
			"project": project,
			"is_active": 1,
			"activation_status": ["in", ("Activated", "")],
		},
		pluck="role",
		ignore_permissions=True,
	)
	if not role_names:
		return set()
	rows = frappe.get_all(
		"GRM Project Role Duty",
		filters={"parent": ["in", role_names]},
		pluck="duty",
		ignore_permissions=True,
	)
	return set(rows)


def has_permission(doc, ptype, user):
	"""Duty-driven permission check for GRM Issue.

	Routes ptype checks through the duty model used everywhere else in
	the controller (see grm_issue.py:_enforce_duty_field_constraints
	and grm_user_project_assignment.GOVERNMENT_WORKER_DUTIES).

	Draft rule: a GRM Issue at docstatus=0 is private to its owner.
	Non-owners (including duty-holders on the same project) cannot see
	or fetch it via desk or API. Bypass roles still see everything.

	Region rule: holding a duty on the project is not enough — the issue
	must also sit in the user's assigned region (or below it), unless the
	user personally handled it at some point — see issue_scope, which
	expresses the same two rules in SQL for list/report queries.
	"""
	try:
		if not doc:
			return False

		user = user or frappe.session.user
		if user == "Administrator":
			return True

		roles = set(frappe.get_roles(user))
		if roles & set(BYPASS_ROLES):
			return True

		project = getattr(doc, "project", None)
		if not project:
			return False

		# Drafts are private to their owner — hide from everyone else,
		# even fellow duty-holders. The owner can still see/edit their
		# own draft and submit it when intake is complete.
		docstatus = getattr(doc, "docstatus", 0) or 0
		owner = getattr(doc, "owner", None)
		if docstatus == 0 and owner != user:
			return False

		required = PTYPE_DUTIES.get(ptype)
		if required is None:
			# Unknown ptype: defer to standard DocPerm matrix.
			return True
		if not required:
			# Empty tuple means "bypass roles only" — already handled.
			return False

		held = _user_duties_for_project(user, project)
		if not held.intersection(required):
			return False

		return is_in_user_scope(doc, user, project)
	except Exception as e:
		frappe.log_error(f"Error checking GRM Issue permissions: {e!s}")
		return False


def check_region_access(user, issue_region, user_region):
	"""Check if user has access to the issue's region based on hierarchy"""
	try:
		if not user_region or not issue_region:
			return False

		# Direct match
		if issue_region == user_region:
			return True

		# Check if issue_region is a child of user_region
		return is_child_region(issue_region, user_region)
	except Exception as e:
		frappe.log_error(f"Error checking region access: {e!s}")
		return False


def is_child_region(region, potential_parent):
	"""Check if region is a child of potential_parent in the hierarchy"""
	try:
		current = region
		visited = set()

		while current:
			# Avoid circular references
			if current in visited:
				return False

			visited.add(current)

			# Get parent region
			parent = frappe.db.get_value("GRM Administrative Region", current, "parent_region")

			# No more parents
			if not parent:
				return False

			# Found the parent we're looking for
			if parent == potential_parent:
				return True

			# Move up the hierarchy
			current = parent

		return False
	except Exception as e:
		frappe.log_error(f"Error checking region hierarchy: {e!s}")
		return False


def permission_query_conditions(user):
	"""Restrict GRM Issue list/report queries to what the user may see.

	Three rules, ANDed together:

	1. Project — the user must hold a duty-bearing assignment on it.
	2. Region — the issue must sit in an assigned region or below it,
	   OR the user must have personally handled it (owner, reporter,
	   assignee, escalated/resolved/rejected by, or named in the
	   escalation history). The second half is what stops an issue from
	   disappearing off its handler's desk the moment they escalate it
	   into the region above them.
	3. Drafts — a docstatus=0 issue stays private to its creator, even
	   from duty-holders on the same project.

	Per-issue field-level access is still enforced by has_permission +
	GRMIssue._enforce_duty_field_constraints.
	"""
	try:
		user = user or frappe.session.user
		if user == "Administrator":
			return ""
		roles = set(frappe.get_roles(user))
		if roles & set(BYPASS_ROLES):
			return ""

		scope = user_region_scope(user)
		if not scope:
			return "1=0"

		projects = ", ".join(sql_literal(p) for p in sorted(scope))
		region_clauses = " OR ".join(
			f"(`tabGRM Issue`.project = {sql_literal(project)} AND {region_condition(entry)})"
			for project, entry in sorted(scope.items())
		)
		return (
			f"(`tabGRM Issue`.project IN ({projects})"
			f" AND (({region_clauses}) OR {handled_by_user_condition(user)})"
			f" AND (`tabGRM Issue`.docstatus > 0 OR `tabGRM Issue`.owner = {sql_literal(user)}))"
		)
	except Exception as e:
		frappe.log_error(f"Error generating permission query conditions: {e!s}")
		return "1=0"


def get_child_regions(parent_region):
	"""Get all child regions for a given parent"""
	try:
		result = []

		# Get direct children
		children = frappe.get_all(
			"GRM Administrative Region",
			filters={"parent_region": parent_region},
			pluck="name",
		)

		result.extend(children)

		# Recursively get children of children
		for child in children:
			result.extend(get_child_regions(child))

		return result
	except Exception as e:
		frappe.log_error(f"Error getting child regions: {e!s}")
		return []
