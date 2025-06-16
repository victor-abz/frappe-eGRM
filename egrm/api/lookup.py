"""
EGRM API - Lookup Data Endpoints
------------------------------
This module contains API endpoints for retrieving lookup data.
"""

import logging

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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
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
                "confidentiality_level",
            ],
        )

        # Enhance category data
        for category in categories:
            # Get department name if assigned_department exists
            if category.assigned_department:
                try:
                    department_doc = frappe.get_doc(
                        "GRM Issue Department", category.assigned_department
                    )
                    category.department_name = department_doc.department_name
                except:
                    category.department_name = category.assigned_department
            else:
                category.department_name = None

            # Set default values for missing fields
            category.description = category.label or category.category_name
            category.department = category.assigned_department
            category.auto_assign = 0  # Default value
            category.active = 1  # Default value

        frappe.log(f"Returning {len(categories)} categories")
        return {"status": "success", "data": categories}

    except Exception as e:
        frappe.log(f"Error in get_categories: {str(e)}")
        frappe.log_error(f"Error in get_categories: {str(e)}")
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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to access this project"),
            }

        # Get issue types - using actual fields that exist
        types = frappe.get_all("GRM Issue Type", fields=["name", "type_name"])

        # Set default values for missing fields
        for type_item in types:
            type_item.description = type_item.type_name  # Use type_name as description
            type_item.active = 1  # Default value

        frappe.log(f"Returning {len(types)} issue types")
        return {"status": "success", "data": types}

    except Exception as e:
        frappe.log(f"Error in get_types: {str(e)}")
        frappe.log_error(f"Error in get_types: {str(e)}")
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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
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

        print(statuses)

        # Set default values for missing fields
        for status in statuses:
            status.description = status.status_name  # Use status_name as description
            status.appealed_status = 0  # Default value
            status.color = "#007bff"  # Default blue color

        frappe.log(f"Returning {len(statuses)} statuses")
        return {"status": "success", "data": statuses}

    except Exception as e:
        frappe.log(f"Error in get_statuses: {str(e)}")
        frappe.log_error(f"Error in get_statuses: {str(e)}")
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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
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
        for age_group in age_groups:
            age_group.description = age_group.age_group_name

        frappe.log(f"Returning {len(age_groups)} age groups")
        return {"status": "success", "data": age_groups}

    except Exception as e:
        frappe.log(f"Error in get_age_groups: {str(e)}")
        frappe.log_error(f"Error in get_age_groups: {str(e)}")
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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
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
        frappe.log(f"Error in get_citizen_groups: {str(e)}")
        frappe.log_error(f"Error in get_citizen_groups: {str(e)}")
        return {"status": "error", "message": str(e)}


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
            frappe.log(
                f"User {user} does not have permission to read project {project_id}"
            )
            return {
                "status": "error",
                "message": _("You do not have permission to access this project"),
            }

        # Get departments
        departments = frappe.get_all(
            "GRM Issue Department", fields=["name", "department_name"]
        )

        # Set default description
        for dept in departments:
            dept.description = dept.department_name

        frappe.log(f"Returning {len(departments)} departments")
        return {"status": "success", "data": departments}

    except Exception as e:
        frappe.log(f"Error in get_departments: {str(e)}")
        frappe.log_error(f"Error in get_departments: {str(e)}")
        return {"status": "error", "message": str(e)}


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

        frappe.log(
            f"Returning {len(accessible_regions)} accessible regions for user {user}"
        )
        return {"status": "success", "data": accessible_regions}

    except Exception as e:
        frappe.log_error(f"Error in get_regions: {str(e)}")
        frappe.log(f"Error in get_regions: {str(e)}")
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

        frappe.log(
            f"Found {len(region_assignments)} region assignments for user {user}"
        )

        # Log the projects and regions for debugging
        projects = list(set([a.project for a in region_assignments]))
        regions = list(set([a.administrative_region for a in region_assignments]))
        frappe.log(f"User {user} has access to projects: {projects}")
        frappe.log(f"User {user} is assigned to regions: {regions}")

        return region_assignments

    except Exception as e:
        frappe.log_error(f"Error getting user region assignments: {str(e)}")
        return []


def get_user_accessible_regions(user_assignments):
    """
    Get all regions accessible to user (including hierarchical children)
    Automatically handles multiple projects and administrative levels

    Args:
        user_assignments (list): User's region assignments

    Returns:
        list: List of accessible regions with enhanced data
    """
    try:
        accessible_regions = []
        processed_regions = set()  # Avoid duplicates

        # Get unique projects from assignments
        user_projects = list(
            set([assignment.project for assignment in user_assignments])
        )
        frappe.log(f"Processing regions for projects: {user_projects}")

        for assignment in user_assignments:
            assigned_region_id = assignment.administrative_region
            project_id = assignment.project

            # Get the assigned region and all its children
            region_hierarchy = get_region_hierarchy(assigned_region_id, project_id)

            for region in region_hierarchy:
                # Avoid duplicates
                if region["name"] in processed_regions:
                    continue

                # Enhance region data
                enhanced_region = enhance_region_data(region, assignment)
                accessible_regions.append(enhanced_region)
                processed_regions.add(region["name"])

        # Sort regions by project, administrative level, and name for better UX
        accessible_regions.sort(
            key=lambda x: (
                x.get("project", ""),
                x.get("administrative_level", ""),
                x.get("region_name", ""),
            )
        )

        return accessible_regions

    except Exception as e:
        frappe.log_error(f"Error getting accessible regions: {str(e)}")
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

            children = frappe.get_all(
                "GRM Administrative Region", fields="*", filters=child_filters
            )

            # Recursively get children of children
            for child in children:
                child_hierarchy = get_region_hierarchy(
                    child.name, project_id, visited.copy()
                )
                regions.extend(child_hierarchy)

        return regions

    except Exception as e:
        frappe.log_error(
            f"Error getting region hierarchy for {parent_region_id}: {str(e)}"
        )
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
        children = frappe.get_all(
            "GRM Administrative Region", fields="*", filters=child_filters
        )

        # Enhance children data
        enhanced_children = []
        for child in children:
            enhanced_child = enhance_region_data(child, relevant_assignment)
            enhanced_children.append(enhanced_child)

        frappe.log(
            f"Returning {len(enhanced_children)} children for region {parent_id}"
        )
        return {"status": "success", "data": enhanced_children}

    except Exception as e:
        frappe.log_error(f"Error getting region children: {str(e)}")
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
            current_region = frappe.get_doc(
                "GRM Administrative Region", current_region.parent_region
            )

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
                    coordinates = (
                        location_data["features"][0]
                        .get("geometry", {})
                        .get("coordinates", [])
                    )
                    if len(coordinates) >= 2:
                        longitude = coordinates[0]
                        latitude = coordinates[1]
            except:
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
            "is_directly_assigned": region.get("name")
            == user_assignment.get("administrative_region"),
        }

        return enhanced_region

    except Exception as e:
        frappe.log_error(f"Error enhancing region data: {str(e)}")
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
        frappe.log(f"Error in get_projects: {str(e)}")
        frappe.log_error(f"Error in get_projects: {str(e)}")
        return {"status": "error", "message": str(e)}
