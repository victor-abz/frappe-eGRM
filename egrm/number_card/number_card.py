import frappe
from frappe.utils import getdate, nowdate, add_to_date, flt

def get_open_issues_data():
    """
    Get count of open issues
    """
    return frappe.db.count('GRM Issue', {'status': ['in', ['Open', 'In Progress']]})

def get_escalated_issues_data():
    """
    Get count of escalated issues
    """
    return frappe.db.count('GRM Issue', {'escalate_flag': 1})

def get_assigned_issues_data():
    """
    Get count of issues assigned to current user
    """
    return frappe.db.count('GRM Issue', {
        'assignee': frappe.session.user,
        'status': ['not in', ['Resolved', 'Closed']]
    })

def get_avg_resolution_time():
    """
    Get average resolution time in days
    """
    data = frappe.db.sql("""
        SELECT AVG(resolution_days) as avg_days
        FROM `tabGRM Issue`
        WHERE resolution_days > 0
    """, as_dict=1)
    
    return round(flt(data[0].avg_days), 1) if data and data[0].avg_days else 0

def get_feedback_rating():
    """
    Get average feedback rating
    """
    data = frappe.db.sql("""
        SELECT AVG(rating) as avg_rating
        FROM `tabGRM Issue`
        WHERE rating > 0
    """, as_dict=1)
    
    return round(flt(data[0].avg_rating), 1) if data and data[0].avg_rating else 0

def get_my_projects():
    """
    Get projects assigned to current user
    """
    projects = frappe.db.sql("""
        SELECT project
        FROM `tabGRM User Project Assignment`
        WHERE user = %s
        AND is_active = 1
    """, frappe.session.user, as_dict=1)
    
    return [p.project for p in projects] if projects else []

def get_my_departments():
    """
    Get departments assigned to current user
    """
    departments = frappe.db.sql("""
        SELECT department
        FROM `tabGRM User Project Assignment`
        WHERE user = %s
        AND department IS NOT NULL
        AND is_active = 1
    """, frappe.session.user, as_dict=1)
    
    return [d.department for d in departments] if departments else []

def get_my_regions():
    """
    Get regions assigned to current user
    """
    regions = frappe.db.sql("""
        SELECT administrative_region
        FROM `tabGRM User Project Assignment`
        WHERE user = %s
        AND administrative_region IS NOT NULL
        AND is_active = 1
    """, frappe.session.user, as_dict=1)
    
    return [r.administrative_region for r in regions] if regions else []

def get_department_categories():
    """
    Get categories for departments assigned to current user
    """
    departments = get_my_departments()
    if not departments:
        return []
        
    department_list = "', '".join(departments)
    
    categories = frappe.db.sql(f"""
        SELECT name
        FROM `tabGRM Issue Category`
        WHERE assigned_department IN ('{department_list}')
    """, as_dict=1)
    
    return [c.name for c in categories] if categories else []