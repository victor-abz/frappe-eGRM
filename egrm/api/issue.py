def get_reopened_status(project_id):
    """
    Get reopened status for a project
    
    Args:
        project_id (str): Project ID
        
    Returns:
        str: Reopened status ID
    """
    # Find a status with "reopen" or "reopened" in the name
    statuses = frappe.get_all(
        "GRM Issue Status",
        filters=[
            ["status_name", "like", "%reopen%"]
        ],
        fields=["name"]
    )
    
    if statuses:
        return statuses[0].name
    
    # Fallback: Get first non-final status
    statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"final_status": 0},
        fields=["name"]
    )
    
    if statuses:
        return statuses[0].name
    
    return None

def user_has_project_access(user, project_id):
    """
    Check if a user has access to a project
    
    Args:
        user (str): User ID
        project_id (str): Project ID
        
    Returns:
        bool: True if user has access, False otherwise
    """
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    
    # Check if user is assigned to project
    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "project": project_id, "active": 1},
        fields=["name"]
    )
    
    return len(assignments) > 0

def user_has_region_access(user, region_id):
    """
    Check if a user has access to a region
    
    Args:
        user (str): User ID
        region_id (str): Region ID
        
    Returns:
        bool: True if user has access, False otherwise
    """
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    
    # For now, return True
    # This would need to be implemented based on how regional assignments are stored
    return True

def create_log_entry(issue_id, log_type, user, description):
    """
    Create a log entry for an issue
    
    Args:
        issue_id (str): Issue ID
        log_type (str): Log type
        user (str): User ID
        description (str): Log description
        
    Returns:
        None
    """
    try:
        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)
        
        # Add log entry
        issue.append("grm_issue_log", {
            "log_type": log_type,
            "log_by": user,
            "log_date": get_datetime(),
            "description": description
        })
        
        # Save issue
        issue.save()
        
        log.info(f"Created log entry for issue {issue_id}: {log_type} - {description}")
    except Exception as e:
        log.error(f"Error creating log entry for issue {issue_id}: {str(e)}")
