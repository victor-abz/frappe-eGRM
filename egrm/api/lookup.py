"""
EGRM API - Lookup Data Endpoints
------------------------------
This module contains API endpoints for retrieving lookup data.
"""

import logging
import traceback

import frappe
from frappe import _
from frappe.utils import cint

# Configure logging
log = logging.getLogger(__name__)


@frappe.whitelist()
def categories(project_id=None):
	"""
	Get issue categories for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of categories
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting categories for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get categories - using actual fields that exist
		categories = frappe.get_all(
			"GRM Issue Category",
			fields=[
				"name",
				"category_name",
				"label",
				"abbreviation",
				"assigned_department",
				"assigned_role",
				"routing_target_type",
				"confidentiality_level",
			],
		)

		from egrm.services.category_routing import resolve_category_routing

		enhanced_categories = []
		for category in categories:
			# Resolve routing via the single source of truth so role-routed
			# categories are surfaced correctly to mobile clients.
			routing = resolve_category_routing(category["name"])
			category["routing_target_type"] = routing["target_type"]
			category["routing_target"] = routing["target_name"]

			if routing["target_type"] == "Department" and routing["target_doc"]:
				category["department"] = routing["target_name"]
				category["department_name"] = routing["target_doc"].department_name
				category["role"] = None
				category["role_name"] = None
			elif routing["target_type"] == "Role" and routing["target_doc"]:
				category["role"] = routing["target_name"]
				category["role_name"] = routing["target_doc"].role_name
				category["department"] = None
				category["department_name"] = None
			else:
				# No resolved target — fall back to whatever is on the row.
				category["department"] = category.get("assigned_department")
				category["department_name"] = None
				category["role"] = category.get("assigned_role")
				category["role_name"] = None

			# Set default values for missing fields
			category["description"] = category.get("label") or category.get("category_name")
			category["auto_assign"] = 0  # Default value
			category["active"] = 1  # Default value

			enhanced_categories.append(category)

		frappe.log(f"Returning {len(enhanced_categories)} categories")
		return {"status": "success", "data": enhanced_categories}

	except Exception as e:
		frappe.log(f"Error in get_categories: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_categories: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def types(project_id=None):
	"""
	Get issue types for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of issue types
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting issue types for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get issue types - using actual fields that exist
		types = frappe.get_all("GRM Issue Type", fields=["name", "type_name"])

		# Set default values for missing fields
		enhanced_types = []
		for type_item in types:
			type_item["description"] = type_item.get("type_name")  # Use type_name as description
			type_item["active"] = 1  # Default value
			enhanced_types.append(type_item)

		frappe.log(f"Returning {len(enhanced_types)} issue types")
		return {"status": "success", "data": enhanced_types}

	except Exception as e:
		frappe.log(f"Error in get_types: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_types: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def statuses(project_id=None):
	"""
	Get issue statuses for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of statuses
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting statuses for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get statuses - using actual fields that exist
		statuses = frappe.get_all(
			"GRM Issue Status",
			fields=[
				"name",
				"status_name",
				"initial_status",
				"open_status",
				"rejected_status",
				"final_status",
			],
		)

		# Set default values for missing fields
		enhanced_statuses = []
		for status in statuses:
			status["description"] = status.get("status_name")  # Use status_name as description
			status["appealed_status"] = 0  # Default value
			status["color"] = "#007bff"  # Default blue color
			enhanced_statuses.append(status)

		frappe.log(f"Returning {len(enhanced_statuses)} statuses")
		return {"status": "success", "data": enhanced_statuses}

	except Exception as e:
		frappe.log(f"Error in get_statuses: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_statuses: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def age_groups(project_id=None):
	"""
	Get age groups for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of age groups
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting age groups for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get age groups
		age_groups = frappe.get_all(
			"GRM Issue Age Group",
			fields=["name", "age_group as age_group_name"],
		)

		# Set default description
		enhanced_age_groups = []
		for age_group in age_groups:
			age_group["description"] = age_group.get("age_group_name")
			enhanced_age_groups.append(age_group)

		frappe.log(f"Returning {len(enhanced_age_groups)} age groups")
		return {"status": "success", "data": enhanced_age_groups}

	except Exception as e:
		frappe.log(f"Error in get_age_groups: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_age_groups: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def citizen_groups(project_id=None):
	"""
	Get citizen groups for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of citizen groups
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting citizen groups for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get citizen groups - using the correct single DocType
		citizen_groups = frappe.get_all(
			"GRM Issue Citizen Group", fields=["name", "group_name", "group_type"]
		)

		# Split into two groups based on group_type
		citizen_groups_1 = []
		citizen_groups_2 = []

		for group in citizen_groups:
			group.description = group.group_name  # Set default description
			if group.group_type == "1":
				citizen_groups_1.append(group)
			elif group.group_type == "2":
				citizen_groups_2.append(group)

		frappe.log(
			f"Returning {len(citizen_groups_1)} citizen groups type 1 and {len(citizen_groups_2)} citizen groups type 2"
		)
		return {
			"status": "success",
			"data": {
				"citizen_group_1": citizen_groups_1,
				"citizen_group_2": citizen_groups_2,
			},
		}

	except Exception as e:
		error_trace = traceback.format_exc()
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_citizen_groups: {e!s}\n{error_trace}")
		return {
			"status": "error",
			"message": _("Error retrieving citizen groups. Please try again later."),
		}


@frappe.whitelist()
def departments(project_id=None):
	"""
	Get departments for a project

	Args:
	    project_id (str, optional): Project ID

	Returns:
	    dict: List of departments
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting departments for project {project_id} by user: {user}")

		# Check if project exists
		if project_id and not frappe.db.exists("GRM Project", project_id):
			frappe.log(f"Project {project_id} not found")
			return {"status": "error", "message": _("Project not found")}

		# Check if user has permission to read the project
		if project_id and not frappe.has_permission("GRM Project", "read", project_id):
			frappe.log(f"User {user} does not have permission to read project {project_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this project"),
			}

		# Get departments
		departments = frappe.get_all("GRM Issue Department", fields=["name", "department_name"])

		# Set default description
		for dept in departments:
			dept.description = dept.department_name

		frappe.log(f"Returning {len(departments)} departments")
		return {"status": "success", "data": departments}

	except Exception as e:
		error_trace = traceback.format_exc()
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_departments: {e!s}\n{error_trace}")
		return {
			"status": "error",
			"message": _("Error retrieving departments. Please try again later."),
		}


@frappe.whitelist()
def regions(parent_id=None):
	"""
	Get administrative regions accessible to the current user

	This API automatically determines user access based on their project assignments.
	Returns all regions the user has access to based on their active assignments.
	If a user is assigned to a parent region, they get access to all child regions.

	Args:
	    parent_id (str, optional): Parent region ID (for getting children of specific region)

	Returns:
	    dict: List of regions with hierarchical access control
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting regions for user: {user}")

		# Check if user is guest (not allowed)
		if user == "Guest":
			return {"status": "error", "message": _("Authentication required")}

		# Get user's project assignments and assigned regions automatically
		user_assignments = get_user_region_assignments(user)

		if not user_assignments:
			frappe.log(f"User {user} has no region assignments")
			return {
				"status": "error",
				"message": _(
					"User has no administrative regions assigned. Please contact administrator to assign administrative regions."
				),
			}

		# If parent_id is specified, return children of that region (if user has access)
		if parent_id:
			return get_region_children(parent_id, user_assignments)

		# Get all accessible regions for the user (including hierarchy)
		accessible_regions = get_user_accessible_regions(user_assignments)

		frappe.log(f"Returning {len(accessible_regions)} accessible regions for user {user}")
		return {"status": "success", "data": accessible_regions}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_regions: {e!s}")
		frappe.log(f"Error in get_regions: {e!s}")
		return {"status": "error", "message": str(e)}


def get_user_region_assignments(user):
	"""
	Get user's region assignments from GRM User Project Assignment
	Automatically gets all active assignments for the user across all projects

	Args:
	    user (str): User email (from session)

	Returns:
	    list: List of user assignments with region details
	"""
	try:
		# Build filters for user assignments - get all active assignments
		assignment_filters = {
			"user": user,
			"is_active": 1,
			"activation_status": "Activated",
		}

		# Get user assignments that have administrative regions
		assignments = frappe.get_all(
			"GRM User Project Assignment",
			fields=[
				"name",
				"user",
				"project",
				"role",
				"administrative_region",
				"department",
			],
			filters=assignment_filters,
		)

		# Filter out assignments without regions
		region_assignments = [a for a in assignments if a.administrative_region]

		frappe.log(f"Found {len(region_assignments)} region assignments for user {user}")

		# Log the projects and regions for debugging
		projects = list(set([a.project for a in region_assignments]))
		regions = list(set([a.administrative_region for a in region_assignments]))
		frappe.log(f"User {user} has access to projects: {projects}")
		frappe.log(f"User {user} is assigned to regions: {regions}")

		return region_assignments

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting user region assignments: {e!s}")
		return []


def get_user_accessible_regions(user_assignments):
	"""Resolve every region accessible to the user across all assignments.

	Performance: this used to recurse via ``frappe.get_doc`` per region
	(N+1 in both directions — root walk + child walk). The bulk-seed at
	PF-0 puts ~500 regions under one cell of the RW-WB project, which
	blew the PF-2 budget by ~4x. We now hit each project ONCE with a
	single ``frappe.get_all`` and walk the tree in memory.

	Args:
	    user_assignments: list of GRM User Project Assignment dicts.

	Returns:
	    list[dict]: enhanced region records, deduped & sorted.
	"""
	try:
		if not user_assignments:
			return []

		# Group assignments by project so we only fetch each project's
		# region table once, then assemble the descendant set in memory.
		assignments_by_project: dict[str, list] = {}
		for a in user_assignments:
			if not a.administrative_region or not a.project:
				continue
			assignments_by_project.setdefault(a.project, []).append(a)

		accessible: list[dict] = []
		processed: set[str] = set()

		for project_id, project_assignments in assignments_by_project.items():
			project_regions = frappe.get_all(
				"GRM Administrative Region",
				fields=[
					"name",
					"region_name",
					"administrative_level",
					"parent_region",
					"project",
					"location",
					"path",
				],
				filters={"project": project_id},
			)
			if not project_regions:
				continue
			by_parent: dict[str | None, list[dict]] = {}
			for r in project_regions:
				by_parent.setdefault(r.get("parent_region"), []).append(r)
			by_name: dict[str, dict] = {r["name"]: r for r in project_regions}

			for assignment in project_assignments:
				root_id = assignment.administrative_region
				if root_id not in by_name:
					continue
				# BFS walk of the in-memory adjacency map.
				stack = [by_name[root_id]]
				while stack:
					region = stack.pop()
					if region["name"] in processed:
						continue
					processed.add(region["name"])
					accessible.append(enhance_region_data(region, assignment))
					stack.extend(by_parent.get(region["name"], []))

		accessible.sort(
			key=lambda x: (
				x.get("project") or "",
				x.get("administrative_level") or "",
				x.get("region_name") or "",
			)
		)
		return accessible

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting accessible regions: {e!s}")
		return []


def get_region_hierarchy(parent_region_id, project_id, visited=None):
	"""
	Recursively get a region and all its children
	Uses the project_id from user assignment for proper filtering

	Args:
	    parent_region_id (str): Parent region ID
	    project_id (str): Project ID from user assignment
	    visited (set, optional): Set to track visited regions (prevent cycles)

	Returns:
	    list: List of regions in hierarchy
	"""
	if visited is None:
		visited = set()

	if parent_region_id in visited:
		return []  # Prevent infinite recursion

	visited.add(parent_region_id)

	try:
		# Get the parent region
		regions = []
		parent_region = frappe.get_doc("GRM Administrative Region", parent_region_id)

		# Verify the region belongs to the correct project
		if parent_region.project == project_id:
			# Convert to dict and add to list
			parent_data = parent_region.as_dict()
			regions.append(parent_data)

			# Get all children of this region in the same project
			child_filters = {"parent_region": parent_region_id, "project": project_id}

			children = frappe.get_all("GRM Administrative Region", fields="*", filters=child_filters)

			# Recursively get children of children
			for child in children:
				child_hierarchy = get_region_hierarchy(child.name, project_id, visited.copy())
				regions.extend(child_hierarchy)

		return regions

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting region hierarchy for {parent_region_id}: {e!s}")
		return []


def get_region_children(parent_id, user_assignments):
	"""
	Get direct children of a specific region (if user has access)
	Simplified to only require parent_id since we have user context

	Args:
	    parent_id (str): Parent region ID
	    user_assignments (list): User's region assignments

	Returns:
	    dict: API response with children regions
	"""
	try:
		# Check if user has access to the parent region
		user_has_access = False
		relevant_assignment = None

		for assignment in user_assignments:
			assigned_region_id = assignment.administrative_region

			# User has access if they're assigned to this region or a parent of this region
			if assigned_region_id == parent_id:
				user_has_access = True
				relevant_assignment = assignment
				break

			# Check if assigned region is an ancestor of parent_id
			if is_region_ancestor(assigned_region_id, parent_id):
				user_has_access = True
				relevant_assignment = assignment
				break

		if not user_has_access:
			return {
				"status": "error",
				"message": _("You do not have access to this region"),
			}

		# Get the project from the relevant assignment
		project_id = relevant_assignment.project

		# Build filters for children
		child_filters = {"parent_region": parent_id, "project": project_id}

		# Get children
		children = frappe.get_all("GRM Administrative Region", fields="*", filters=child_filters)

		# Enhance children data
		enhanced_children = []
		for child in children:
			enhanced_child = enhance_region_data(child, relevant_assignment)
			enhanced_children.append(enhanced_child)

		frappe.log(f"Returning {len(enhanced_children)} children for region {parent_id}")
		return {"status": "success", "data": enhanced_children}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting region children: {e!s}")
		return {"status": "error", "message": str(e)}


def is_region_ancestor(ancestor_id, descendant_id):
	"""
	Check if ancestor_id is an ancestor of descendant_id

	Args:
	    ancestor_id (str): Potential ancestor region ID
	    descendant_id (str): Descendant region ID

	Returns:
	    bool: True if ancestor_id is an ancestor of descendant_id
	"""
	try:
		current_region = frappe.get_doc("GRM Administrative Region", descendant_id)

		# Walk up the hierarchy
		while current_region.parent_region:
			if current_region.parent_region == ancestor_id:
				return True
			current_region = frappe.get_doc("GRM Administrative Region", current_region.parent_region)

		return False

	except Exception:
		return False


def enhance_region_data(region, user_assignment):
	"""
	Enhance region data with additional fields needed by the mobile app

	Args:
	    region (dict): Region data from database
	    user_assignment (dict): User assignment context

	Returns:
	    dict: Enhanced region data
	"""
	try:
		# Parse geolocation if available
		latitude = None
		longitude = None

		if region.get("location"):
			try:
				import json

				location_data = json.loads(region["location"])
				if location_data.get("features") and len(location_data["features"]) > 0:
					coordinates = location_data["features"][0].get("geometry", {}).get("coordinates", [])
					if len(coordinates) >= 2:
						longitude = coordinates[0]
						latitude = coordinates[1]
			except (ValueError, TypeError, KeyError, IndexError):
				pass  # Ignore geolocation parsing errors

		# Build enhanced region object
		enhanced_region = {
			"name": region.get("name"),
			"region_name": region.get("region_name"),
			"administrative_level": region.get("administrative_level"),
			"parent_region": region.get("parent_region"),
			"project": region.get("project"),
			"latitude": latitude,
			"longitude": longitude,
			"path": region.get("path"),  # Materialized path for hierarchy
			# Add assignment context
			"user_role": user_assignment.get("role"),
			"user_department": user_assignment.get("department"),
			"is_directly_assigned": region.get("name") == user_assignment.get("administrative_region"),
		}

		return enhanced_region

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error enhancing region data: {e!s}")
		# Return basic region data if enhancement fails
		return {
			"name": region.get("name"),
			"region_name": region.get("region_name"),
			"administrative_level": region.get("administrative_level"),
			"parent_region": region.get("parent_region"),
			"project": region.get("project"),
			"latitude": None,
			"longitude": None,
		}


@frappe.whitelist()
def projects():
	"""
	Get projects accessible to the current user

	Returns:
	    dict: List of projects
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting projects for user: {user}")

		# Get projects that the user has permission to read
		projects = frappe.get_all(
			"GRM Project",
			fields=[
				"name",
				"title as project_name",
				"description",
				"start_date",
				"end_date",
				"is_active",
			],
			filters={"is_active": 1},  # Only active projects
		)

		# Filter projects based on user permissions
		accessible_projects = []
		for project in projects:
			if frappe.has_permission("GRM Project", "read", project.name):
				project.active = project.is_active  # Map to expected field name
				accessible_projects.append(project)

		frappe.log(f"Returning {len(accessible_projects)} projects")
		return {"status": "success", "data": accessible_projects}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_projects: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_projects: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_user_context():
	"""
	Get comprehensive user context including:
	- User details
	- Department
	- Role
	- Project assignments
	- Region assignments with hierarchy
	- Access levels and permissions

	Returns:
	    dict: Complete user context data
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting user context for: {user}")

		if user == "Guest":
			return {"status": "error", "message": _("Authentication required")}

		# Get user document
		user_doc = frappe.get_doc("User", user)

		# Get user's project assignments
		assignments = frappe.get_all(
			"GRM User Project Assignment",
			fields=[
				"name",
				"project",
				"role",
				"department",
				"administrative_region",
				"is_active",
				"activation_status",
			],
			filters={"user": user, "is_active": 1, "activation_status": "Activated"},
		)

		# Get user's regions with hierarchy
		region_assignments = get_user_region_assignments(user)
		accessible_regions = get_user_accessible_regions(region_assignments)

		# Get user's roles and permissions
		roles = frappe.get_roles(user)

		# ----------------------------------------------------------------
		# Batch-fetch lookups (PF-2 hot path).
		#
		# Previously every assignment row triggered three single-row
		# `frappe.db.get_value` calls (project + department + region).
		# With three project assignments and the bulk-seeded RW-WB hierarchy
		# this was ~9 round-trips on top of the recursive region walk.
		# Collapse them into one batched `frappe.get_all` per doctype so
		# the whole call holds steady under the p50/p95 budget.
		# ----------------------------------------------------------------
		project_ids = {a.project for a in assignments if a.project}
		dept_ids = {a.department for a in assignments if a.department}
		region_ids = {a.administrative_region for a in assignments if a.administrative_region}

		platform_role_set = {"System Manager", "GRM Platform Administrator"}
		is_platform_admin = bool(set(roles) & platform_role_set)

		# Platform admins implicitly see every project; pull them all so the
		# accessible_projects list is complete for the AQE MP-1 contract.
		if is_platform_admin:
			all_project_rows = frappe.get_all(
				"GRM Project",
				fields=["name", "title", "project_code", "is_active"],
			)
			project_lookup = {p["name"]: p for p in all_project_rows}
		else:
			if project_ids:
				project_lookup = {
					p["name"]: p
					for p in frappe.get_all(
						"GRM Project",
						fields=["name", "title", "project_code", "is_active"],
						filters={"name": ["in", list(project_ids)]},
					)
				}
			else:
				project_lookup = {}

		dept_lookup = {
			d["name"]: d
			for d in (
				frappe.get_all(
					"GRM Issue Department",
					fields=["name", "department_name"],
					filters={"name": ["in", list(dept_ids)]},
				)
				if dept_ids
				else []
			)
		}
		region_lookup = {
			r["name"]: r
			for r in (
				frappe.get_all(
					"GRM Administrative Region",
					fields=["name", "region_name"],
					filters={"name": ["in", list(region_ids)]},
				)
				if region_ids
				else []
			)
		}

		# Build the accessible_projects payload from the batched lookup.
		# Order: every platform project first (when admin), then any
		# assignment-only projects we somehow missed (defensive — keeps
		# the contract identical to the prior implementation).
		seen_projects: set[str] = set()
		accessible_projects: list[dict] = []

		def _emit_project(p):
			if not p or p["name"] in seen_projects:
				return
			seen_projects.add(p["name"])
			accessible_projects.append(
				{
					"id": p["name"],
					"name": p["name"],
					"project_name": p.get("title"),
					"project_code": p.get("project_code"),
					"active": int(bool(p.get("is_active"))),
				}
			)

		if is_platform_admin:
			for p in project_lookup.values():
				_emit_project(p)
		for a in assignments:
			if a.project:
				_emit_project(project_lookup.get(a.project))

		# has_permission() for `user` does not vary by `role` (it consults
		# the full role bag via the session/user). The previous code
		# called it 4×len(roles) times. Compute once.
		perm_create = frappe.has_permission("GRM Issue", "create", user=user)
		perm_write = frappe.has_permission("GRM Issue", "write", user=user)
		perm_delete = frappe.has_permission("GRM Issue", "delete", user=user)
		perm_assign = frappe.has_permission("GRM Issue", "assign", user=user)
		per_role_perms = {
			role: {
				"create_issue": perm_create,
				"update_issue": perm_write,
				"delete_issue": perm_delete,
				"assign_issue": perm_assign,
			}
			for role in roles
		}

		# Build comprehensive user context
		user_context = {
			"status": "success",
			"data": {
				"user": {
					"id": user_doc.name,
					"email": user_doc.email,
					"full_name": user_doc.full_name,
					"roles": roles,
				},
				"assignments": [
					{
						"id": assignment.name,
						"project": {
							"id": assignment.project,
							"name": (
								project_lookup.get(assignment.project, {}).get("title")
								if assignment.project
								else None
							),
						},
						"role": assignment.role,
						"department": {
							"id": assignment.department,
							"name": (
								dept_lookup.get(assignment.department, {}).get("department_name")
								if assignment.department
								else None
							),
						},
						"region": {
							"id": assignment.administrative_region,
							"name": (
								region_lookup.get(assignment.administrative_region, {}).get("region_name")
								if assignment.administrative_region
								else None
							),
						},
					}
					for assignment in assignments
				],
				"accessible_regions": accessible_regions,
				"accessible_projects": accessible_projects,
				"permissions": per_role_perms,
			},
		}

		frappe.log(f"User context built successfully for {user}")
		return user_context

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting user context: {e!s}")
		print(frappe.get_traceback())
		frappe.log_error(f"Error getting user context: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def user_context():
	"""Stable public alias for `get_user_context`.

	The mobile client (and AQE MD-1 / API-3 contract tests) call
	`/api/method/egrm.api.lookup.user_context`. The legacy implementation
	lives at `get_user_context`; this thin alias keeps both names callable
	without duplicating logic.
	"""
	return get_user_context()
