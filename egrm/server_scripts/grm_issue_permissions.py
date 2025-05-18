import frappe
import logging

log = logging.getLogger(__name__)

def has_permission(doc, ptype, user):
    """Custom permission check for GRM Issue"""
    try:
        if not doc:
            return False
            
        # System Manager always has access
        if "System Manager" in frappe.get_roles(user):
            return True
            
        # GRM Administrator always has access
        if "GRM Administrator" in frappe.get_roles(user):
            return True
            
        # Check if user is assigned to the project
        user_project_assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters={
                "user": user,
                "project": doc.project,
                "is_active": 1
            },
            fields=["role", "department", "administrative_region"]
        )
        
        if not user_project_assignments:
            return False
            
        # Process each role assignment
        for assignment in user_project_assignments:
            role = assignment.role
            
            # Project Manager has full access to their projects
            if role == "GRM Project Manager":
                return True
                
            # Department Head has access to issues in their department
            if role == "GRM Department Head":
                # Get the department for this category
                category_dept = frappe.db.get_value("GRM Issue Category", doc.category, "assigned_department")
                
                if category_dept and assignment.department == category_dept:
                    return True
                    
            # Field Officer has access to issues in their region and assigned to them
            if role == "GRM Field Officer":
                # Check if directly assigned
                if doc.assignee == user:
                    return True
                    
                # Check region hierarchy
                if check_region_access(user, doc.administrative_region, assignment.administrative_region):
                    return True
                    
            # Analyst has read-only access
            if role == "GRM Analyst" and ptype == "read":
                return True
                
        # If we reach here, no access
        return False
    except Exception as e:
        log.error(f"Error checking GRM Issue permissions: {str(e)}")
        # Default to denying access on error
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
        log.error(f"Error checking region access: {str(e)}")
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
        log.error(f"Error checking region hierarchy: {str(e)}")
        return False

def permission_query_conditions(user):
    """Return SQL conditions for GRM Issue list views"""
    try:
        # System Manager and GRM Administrator see all issues
        if "System Manager" in frappe.get_roles(user) or "GRM Administrator" in frappe.get_roles(user):
            return ""
            
        # Get all projects the user is assigned to
        user_projects = frappe.get_all(
            "GRM User Project Assignment",
            filters={
                "user": user,
                "is_active": 1
            },
            fields=["project", "role", "department", "administrative_region"]
        )
        
        if not user_projects:
            return "1=0"  # No access
            
        conditions = []
        
        for assignment in user_projects:
            project_condition = f"(`tabGRM Issue`.project = '{assignment.project}')"
            role = assignment.role
            
            if role == "GRM Project Manager":
                conditions.append(project_condition)
                
            elif role == "GRM Department Head" and assignment.department:
                # Get categories assigned to this department
                categories = frappe.get_all(
                    "GRM Issue Category",
                    filters={
                        "assigned_department": assignment.department
                    },
                    pluck="name"
                )
                
                if categories:
                    categories_str = "', '".join(categories)
                    conditions.append(
                        f"({project_condition} AND `tabGRM Issue`.category IN ('{categories_str}'))"
                    )
                    
            elif role == "GRM Field Officer" and assignment.administrative_region:
                # Get all child regions
                regions = get_child_regions(assignment.administrative_region)
                regions.append(assignment.administrative_region)
                
                regions_str = "', '".join(regions)
                assignee_condition = f"`tabGRM Issue`.assignee = '{user}'"
                
                conditions.append(
                    f"({project_condition} AND (`tabGRM Issue`.administrative_region IN ('{regions_str}') OR {assignee_condition}))"
                )
                
            elif role == "GRM Analyst":
                conditions.append(project_condition)
                
        if not conditions:
            return "1=0"  # No access
            
        # Combine all conditions with OR
        return "(" + " OR ".join(conditions) + ")"
    except Exception as e:
        log.error(f"Error generating permission query conditions: {str(e)}")
        return "1=0"  # Default to no access on error
        
def get_child_regions(parent_region):
    """Get all child regions for a given parent"""
    try:
        result = []
        
        # Get direct children
        children = frappe.get_all(
            "GRM Administrative Region",
            filters={
                "parent_region": parent_region
            },
            pluck="name"
        )
        
        result.extend(children)
        
        # Recursively get children of children
        for child in children:
            result.extend(get_child_regions(child))
            
        return result
    except Exception as e:
        log.error(f"Error getting child regions: {str(e)}")
        return []