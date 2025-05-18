"""
EGRM API - Lookup Data Endpoints
------------------------------
This module contains API endpoints for retrieving lookup data.
"""

import frappe
import logging
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
        log.info(f"Getting categories for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get categories
        filters = {}
        if project_id:
            filters["project"] = project_id
            
        categories = frappe.get_all(
            "GRM Issue Category",
            filters=filters,
            fields=["name", "category_name", "description", "department", "auto_assign", "active"]
        )
        
        # Enhance category data
        for category in categories:
            # Get department name
            if category.department:
                department_doc = frappe.get_doc("GRM Issue Department", category.department)
                category.department_name = department_doc.department_name
        
        log.info(f"Returning {len(categories)} categories")
        return {"status": "success", "data": categories}
        
    except Exception as e:
        log.error(f"Error in get_categories: {str(e)}")
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
        log.info(f"Getting issue types for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get issue types
        filters = {}
        if project_id:
            filters["project"] = project_id
            
        types = frappe.get_all(
            "GRM Issue Type",
            filters=filters,
            fields=["name", "type_name", "description", "active"]
        )
        
        log.info(f"Returning {len(types)} issue types")
        return {"status": "success", "data": types}
        
    except Exception as e:
        log.error(f"Error in get_types: {str(e)}")
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
        log.info(f"Getting statuses for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get statuses
        # For now, we'll get all statuses regardless of project
        # In a complete implementation, statuses might be project-specific
        statuses = frappe.get_all(
            "GRM Issue Status",
            fields=[
                "name", "status_name", "description", 
                "initial_status", "open_status", "rejected_status", 
                "final_status", "appealed_status", "color"
            ]
        )
        
        log.info(f"Returning {len(statuses)} statuses")
        return {"status": "success", "data": statuses}
        
    except Exception as e:
        log.error(f"Error in get_statuses: {str(e)}")
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
        log.info(f"Getting age groups for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get age groups
        # For now, we'll get all age groups regardless of project
        age_groups = frappe.get_all(
            "GRM Issue Age Group",
            fields=["name", "age_group_name", "min_age", "max_age", "description"]
        )
        
        log.info(f"Returning {len(age_groups)} age groups")
        return {"status": "success", "data": age_groups}
        
    except Exception as e:
        log.error(f"Error in get_age_groups: {str(e)}")
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
        log.info(f"Getting citizen groups for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get citizen groups
        # For now, we'll get all citizen groups regardless of project
        citizen_groups = frappe.get_all(
            "GRM Issue Citizen Group",
            fields=["name", "group_name", "description"]
        )
        
        log.info(f"Returning {len(citizen_groups)} citizen groups")
        return {"status": "success", "data": citizen_groups}
        
    except Exception as e:
        log.error(f"Error in get_citizen_groups: {str(e)}")
        return {"status": "error", "message": str(e)}
