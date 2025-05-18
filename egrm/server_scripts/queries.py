import frappe
import logging
from frappe import _
from frappe.utils import cint, getdate, nowdate, now_datetime
import json

log = logging.getLogger(__name__)

def get_departments_by_projects(doctype, txt, searchfield, start, page_len, filters):
    """
    Get departments linked to specific projects
    """
    try:
        projects = filters.get('projects', [])
        if not projects:
            return []
            
        # Handle single project as string
        if isinstance(projects, str):
            projects = [projects]
            
        # Build conditions for SQL
        project_conditions = "', '".join(projects)
        search_condition = f"AND d.department_name LIKE '%{txt}%'" if txt else ""
        
        # Query departments linked to the projects
        departments = frappe.db.sql(f"""
            SELECT d.name, d.department_name
            FROM `tabGRM Issue Department` d
            INNER JOIN `tabGRM Project Link` p ON p.parent = d.name
            WHERE p.project IN ('{project_conditions}')
            {search_condition}
            GROUP BY d.name
            ORDER BY d.department_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return departments
    except Exception as e:
        log.error(f"Error getting departments by projects: {str(e)}")
        return []

def get_status_by_project(doctype, txt, searchfield, start, page_len, filters):
    """
    Get statuses linked to a specific project
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        search_condition = f"AND s.status_name LIKE '%{txt}%'" if txt else ""
        
        # Query statuses linked to the project
        statuses = frappe.db.sql(f"""
            SELECT s.name, s.status_name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = '{project}'
            {search_condition}
            ORDER BY s.status_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return statuses
    except Exception as e:
        log.error(f"Error getting statuses by project: {str(e)}")
        return []

def get_category_by_project(doctype, txt, searchfield, start, page_len, filters):
    """
    Get categories linked to a specific project
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        search_condition = f"AND c.category_name LIKE '%{txt}%'" if txt else ""
        
        # Query categories linked to the project
        categories = frappe.db.sql(f"""
            SELECT c.name, c.category_name
            FROM `tabGRM Issue Category` c
            INNER JOIN `tabGRM Project Link` p ON p.parent = c.name
            WHERE p.project = '{project}'
            {search_condition}
            ORDER BY c.category_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return categories
    except Exception as e:
        log.error(f"Error getting categories by project: {str(e)}")
        return []

def get_issue_type_by_project(doctype, txt, searchfield, start, page_len, filters):
    """
    Get issue types linked to a specific project
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        search_condition = f"AND t.type_name LIKE '%{txt}%'" if txt else ""
        
        # Query issue types linked to the project
        issue_types = frappe.db.sql(f"""
            SELECT t.name, t.type_name
            FROM `tabGRM Issue Type` t
            INNER JOIN `tabGRM Project Link` p ON p.parent = t.name
            WHERE p.project = '{project}'
            {search_condition}
            ORDER BY t.type_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return issue_types
    except Exception as e:
        log.error(f"Error getting issue types by project: {str(e)}")
        return []

def get_age_group_by_project(doctype, txt, searchfield, start, page_len, filters):
    """
    Get age groups linked to a specific project
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        search_condition = f"AND a.age_group LIKE '%{txt}%'" if txt else ""
        
        # Query age groups linked to the project
        age_groups = frappe.db.sql(f"""
            SELECT a.name, a.age_group
            FROM `tabGRM Issue Age Group` a
            INNER JOIN `tabGRM Project Link` p ON p.parent = a.name
            WHERE p.project = '{project}'
            {search_condition}
            ORDER BY a.age_group
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return age_groups
    except Exception as e:
        log.error(f"Error getting age groups by project: {str(e)}")
        return []

def get_citizen_group_by_project(doctype, txt, searchfield, start, page_len, filters):
    """
    Get citizen groups linked to a specific project with optional filter by group type
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        group_type = filters.get('group_type', '')
        group_type_condition = f"AND c.group_type = '{group_type}'" if group_type else ""
        search_condition = f"AND c.group_name LIKE '%{txt}%'" if txt else ""
        
        # Query citizen groups linked to the project
        citizen_groups = frappe.db.sql(f"""
            SELECT c.name, c.group_name
            FROM `tabGRM Issue Citizen Group` c
            INNER JOIN `tabGRM Project Link` p ON p.parent = c.name
            WHERE p.project = '{project}'
            {group_type_condition}
            {search_condition}
            ORDER BY c.group_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return citizen_groups
    except Exception as e:
        log.error(f"Error getting citizen groups by project: {str(e)}")
        return []

def get_project_users(doctype, txt, searchfield, start, page_len, filters):
    """
    Get users assigned to a specific project
    """
    try:
        project = filters.get('project', '')
        if not project:
            return []
            
        search_condition = f"AND u.full_name LIKE '%{txt}%'" if txt else ""
        
        # Query users assigned to the project
        users = frappe.db.sql(f"""
            SELECT u.name, u.full_name
            FROM `tabUser` u
            INNER JOIN `tabGRM User Project Assignment` a ON a.user = u.name
            WHERE a.project = '{project}'
            AND a.is_active = 1
            {search_condition}
            GROUP BY u.name
            ORDER BY u.full_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return users
    except Exception as e:
        log.error(f"Error getting project users: {str(e)}")
        return []

def get_department_head_suggestions(doctype, txt, searchfield, start, page_len, filters):
    """
    Get user suggestions for department head role
    """
    try:
        department = filters.get('department', '')
        search_condition = f"AND u.full_name LIKE '%{txt}%'" if txt else ""
        
        # First try to find users with Department Head role
        users = frappe.db.sql(f"""
            SELECT u.name, u.full_name
            FROM `tabUser` u
            INNER JOIN `tabHas Role` r ON r.parent = u.name
            WHERE r.role = 'GRM Department Head'
            AND u.enabled = 1
            {search_condition}
            ORDER BY u.full_name
            LIMIT {start}, {page_len}
        """, as_list=1)
        
        return users
    except Exception as e:
        log.error(f"Error getting department head suggestions: {str(e)}")
        return []

def get_initial_status(project):
    """
    Get the initial status for a project
    """
    try:
        if not project:
            return None
            
        # Find initial status for the project
        initial_status = frappe.db.sql("""
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.initial_status = 1
            LIMIT 1
        """, project, as_dict=1)
        
        if initial_status:
            return initial_status[0].name
        
        return None
    except Exception as e:
        log.error(f"Error getting initial status: {str(e)}")
        return None

def get_department_for_category(category):
    """
    Get the assigned department and redirection protocol for a category
    """
    try:
        if not category:
            return None
            
        # Get department and redirection protocol
        category_info = frappe.db.get_value(
            "GRM Issue Category",
            category,
            ["assigned_department", "redirection_protocol"],
            as_dict=1
        )
        
        if category_info:
            return {
                "department": category_info.assigned_department,
                "redirection": category_info.redirection_protocol
            }
        
        return None
    except Exception as e:
        log.error(f"Error getting department for category: {str(e)}")
        return None

def get_least_loaded_user(department, project):
    """
    Get the user with the least assigned issues in a department
    """
    try:
        if not department or not project:
            return None
            
        # Get department head as fallback
        department_head = frappe.db.get_value("GRM Issue Department", department, "head")
        
        # Get all users in the department for this project
        department_users = frappe.db.sql("""
            SELECT a.user
            FROM `tabGRM User Project Assignment` a
            WHERE a.department = %s
            AND a.project = %s
            AND a.is_active = 1
        """, (department, project), as_dict=1)
        
        if not department_users:
            return department_head
            
        user_list = [u.user for u in department_users]
        
        # Count open issues assigned to each user
        user_loads = {}
        for user in user_list:
            count = frappe.db.count(
                "GRM Issue",
                {
                    "assignee": user,
                    "project": project,
                    "status": ["in", get_open_statuses(project)]
                }
            )
            user_loads[user] = count
        
        # Find user with minimum load
        min_load_user = min(user_loads.items(), key=lambda x: x[1])[0] if user_loads else department_head
        
        return min_load_user
    except Exception as e:
        log.error(f"Error getting least loaded user: {str(e)}")
        return None

def get_open_statuses(project):
    """
    Get a list of open statuses for a project
    """
    try:
        if not project:
            return []
            
        open_statuses = frappe.db.sql("""
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.open_status = 1
        """, project, as_dict=1)
        
        return [s.name for s in open_statuses] if open_statuses else []
    except Exception as e:
        log.error(f"Error getting open statuses: {str(e)}")
        return []

def get_allowed_statuses(issue):
    """
    Get allowed next statuses for an issue based on workflow
    """
    try:
        if not issue:
            return []
            
        # For now, return all statuses for the issue's project
        issue_doc = frappe.get_doc("GRM Issue", issue)
        
        if not issue_doc:
            return []
            
        project = issue_doc.project
        current_status = issue_doc.status
        
        # Get all statuses for the project except the current one
        statuses = frappe.db.sql("""
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.name != %s
        """, (project, current_status), as_dict=1)
        
        return [s.name for s in statuses] if statuses else []
    except Exception as e:
        log.error(f"Error getting allowed statuses: {str(e)}")
        return []

def get_category_stats(category):
    """
    Get statistics for a category
    """
    try:
        if not category:
            return None
            
        # Get total issues in this category
        total = frappe.db.count("GRM Issue", {"category": category})
        
        # Get open issues
        category_doc = frappe.get_doc("GRM Issue Category", category)
        if not category_doc:
            return None
            
        # Find projects linked to this category
        project_links = category_doc.get("grm_project_link", [])
        if not project_links:
            return {"total": total, "open": 0, "avg_resolution_days": None}
            
        # Get open statuses for all linked projects
        open_statuses = []
        for link in project_links:
            project_open_statuses = get_open_statuses(link.project)
            open_statuses.extend(project_open_statuses)
            
        # Count open issues
        open_count = frappe.db.count(
            "GRM Issue",
            {
                "category": category,
                "status": ["in", open_statuses]
            }
        ) if open_statuses else 0
        
        # Calculate average resolution days
        avg_days = frappe.db.sql("""
            SELECT AVG(resolution_days) as avg_days
            FROM `tabGRM Issue`
            WHERE category = %s
            AND resolution_days > 0
        """, category, as_dict=1)
        
        avg_resolution_days = round(avg_days[0].avg_days, 1) if avg_days and avg_days[0].avg_days else None
        
        return {
            "total": total,
            "open": open_count,
            "avg_resolution_days": avg_resolution_days
        }
    except Exception as e:
        log.error(f"Error getting category stats: {str(e)}")
        return {"total": 0, "open": 0, "avg_resolution_days": None}