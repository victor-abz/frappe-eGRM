"""
EGRM Assignment Utilities
-----------------------
This module contains utilities for auto-assignment of issues.
"""

import frappe
import logging
from frappe import _
from frappe.utils import cstr
import random

# Configure logging
log = logging.getLogger(__name__)

def get_department_workers(department_id, region_id):
    """
    Get users assigned to a department in a specific region
    
    Args:
        department_id (str): Department ID
        region_id (str): Region ID
        
    Returns:
        list: List of user IDs
    """
    try:
        # This is a simplified implementation
        # In a complete implementation, we would have a proper assignment model
        # that maps users to departments and regions
        
        # Get department
        department = frappe.get_doc("GRM Issue Department", department_id)
        
        # Get all users with the department head or field officer role
        roles = ["GRM Department Head", "GRM Field Officer"]
        users = frappe.get_all(
            "Has Role",
            filters={"role": ["in", roles]},
            fields=["parent"]
        )
        
        # Filter users based on project assignment
        # Get the project for the region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        project_id = region.project
        
        # Get users assigned to the project
        user_ids = [u.parent for u in users]
        assigned_users = []
        
        for user_id in user_ids:
            assignments = frappe.get_all(
                "GRM User Project Assignment",
                filters={"user": user_id, "project": project_id, "active": 1},
                fields=["name"]
            )
            
            if assignments:
                assigned_users.append(user_id)
        
        # TODO: Filter users by region assignment when that model is implemented
        
        log.info(f"Found {len(assigned_users)} workers for department {department_id} in region {region_id}")
        return assigned_users
        
    except Exception as e:
        log.error(f"Error in get_department_workers: {str(e)}")
        return []

def count_open_assignments(user_id):
    """
    Count number of open issues assigned to a user
    
    Args:
        user_id (str): User ID
        
    Returns:
        int: Number of open issues
    """
    try:
        # Get issue statuses
        open_statuses = get_open_statuses()
        
        if not open_statuses:
            log.warning("No open statuses found")
            return 0
        
        # Count open issues
        count = frappe.db.count(
            "GRM Issue",
            {
                "assignee": user_id,
                "status": ["in", open_statuses]
            }
        )
        
        log.info(f"User {user_id} has {count} open issues")
        return count
        
    except Exception as e:
        log.error(f"Error in count_open_assignments: {str(e)}")
        return 0

def get_open_statuses():
    """
    Get list of status IDs that are considered "open"
    
    Returns:
        list: List of status IDs
    """
    try:
        # Get statuses with open_status flag
        statuses = frappe.get_all(
            "GRM Issue Status",
            filters={"open_status": 1},
            fields=["name"]
        )
        
        return [s.name for s in statuses]
        
    except Exception as e:
        log.error(f"Error in get_open_statuses: {str(e)}")
        return []

def select_assignee_by_workload(department_id, region_id):
    """
    Select assignee with lowest workload in a department and region
    
    Args:
        department_id (str): Department ID
        region_id (str): Region ID
        
    Returns:
        str: User ID of selected assignee, or None if no assignee is available
    """
    try:
        # Get department workers
        workers = get_department_workers(department_id, region_id)
        
        if not workers:
            log.warning(f"No workers found for department {department_id} in region {region_id}")
            return None
        
        # Get workload for each worker
        workloads = {}
        for worker in workers:
            workloads[worker] = count_open_assignments(worker)
        
        # Sort workers by workload
        sorted_workers = sorted(workloads.items(), key=lambda x: x[1])
        
        # Get workers with lowest workload
        lowest_workload = sorted_workers[0][1]
        lowest_workload_workers = [w[0] for w in sorted_workers if w[1] == lowest_workload]
        
        # Randomly select one of the workers with lowest workload
        selected_worker = random.choice(lowest_workload_workers)
        
        log.info(f"Selected worker {selected_worker} with workload {lowest_workload}")
        return selected_worker
        
    except Exception as e:
        log.error(f"Error in select_assignee_by_workload: {str(e)}")
        return None

def get_department_head(department_id, region_id):
    """
    Get department head for a department in a region
    
    Args:
        department_id (str): Department ID
        region_id (str): Region ID
        
    Returns:
        str: User ID of department head, or None if no department head is available
    """
    try:
        # This is a simplified implementation
        # In a complete implementation, we would have a proper assignment model
        # that maps users to departments and regions as department heads
        
        # Get users with department head role
        users = frappe.get_all(
            "Has Role",
            filters={"role": "GRM Department Head"},
            fields=["parent"]
        )
        
        # Filter users based on project assignment
        # Get the project for the region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        project_id = region.project
        
        # Get users assigned to the project
        user_ids = [u.parent for u in users]
        assigned_users = []
        
        for user_id in user_ids:
            assignments = frappe.get_all(
                "GRM User Project Assignment",
                filters={"user": user_id, "project": project_id, "active": 1},
                fields=["name"]
            )
            
            if assignments:
                assigned_users.append(user_id)
        
        # TODO: Filter users by region assignment when that model is implemented
        
        if not assigned_users:
            log.warning(f"No department head found for department {department_id} in region {region_id}")
            return None
        
        # For now, randomly select one department head
        selected_head = random.choice(assigned_users)
        
        log.info(f"Selected department head {selected_head} for department {department_id} in region {region_id}")
        return selected_head
        
    except Exception as e:
        log.error(f"Error in get_department_head: {str(e)}")
        return None

def handle_escalation_assignment(issue_id):
    """
    Handle assignment for escalated issues
    
    Args:
        issue_id (str): Issue ID
        
    Returns:
        str: User ID of new assignee, or None if no assignee is available
    """
    try:
        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)
        
        # Get current region
        region_id = issue.administrative_region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        
        # If region has no parent, assign to department head
        if not region.parent_region:
            log.info(f"Region {region_id} has no parent, assigning to department head")
            return get_department_head(issue.category.department, region_id)
        
        # Get parent region
        parent_region_id = region.parent_region
        
        # Get a worker in the parent region
        assignee = select_assignee_by_workload(issue.category.department, parent_region_id)
        if assignee:
            log.info(f"Selected assignee {assignee} in parent region {parent_region_id}")
            return assignee
        
        # If no assignee found, try department head
        log.info(f"No assignee found in parent region, trying department head")
        return get_department_head(issue.category.department, parent_region_id)
        
    except Exception as e:
        log.error(f"Error in handle_escalation_assignment: {str(e)}")
        return None

def auto_assign_issue(issue_id):
    """
    Auto-assign an issue based on its category and region
    
    Args:
        issue_id (str): Issue ID
        
    Returns:
        str: User ID of assignee, or None if assignment failed
    """
    try:
        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)
        
        # Get category and department
        category = frappe.get_doc("GRM Issue Category", issue.category)
        
        if not category.auto_assign:
            log.info(f"Auto-assignment is disabled for category {category.name}")
            return None
        
        department_id = category.department
        if not department_id:
            log.warning(f"Category {category.name} has no department assigned")
            return None
        
        # For escalated issues, handle differently
        if issue.escalate_flag:
            log.info(f"Issue {issue_id} is escalated, handling escalation assignment")
            return handle_escalation_assignment(issue_id)
        
        # Get region
        region_id = issue.administrative_region
        
        # Decide whether to assign to department head or regular worker
        if category.assign_to_head:
            log.info(f"Category {category.name} is set to assign to department head")
            return get_department_head(department_id, region_id)
        else:
            log.info(f"Selecting assignee by workload for category {category.name}")
            return select_assignee_by_workload(department_id, region_id)
        
    except Exception as e:
        log.error(f"Error in auto_assign_issue: {str(e)}")
        return None
