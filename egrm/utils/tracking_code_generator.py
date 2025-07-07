"""
Simple tracking code generator for GRM Issues
Format: {PROJECT_CODE}-{YYMMDD}-{RRRR}
Example: GOODLIDE-250707-4729
"""

import random
from datetime import datetime

import frappe


def generate_tracking_code(project_id, project_code=None, issue_date=None):
    """
    Generate a tracking code with project, date, and random number.

    Format: {PROJECT_CODE}-{YYMMDD}-{RRRR}
    Example: GOODLIDE-250707-4729

    Args:
        project_id (str): The GRM Project ID
        project_code (str, optional): Project code override
        issue_date (datetime, optional): Issue date (defaults to today)

    Returns:
        str: Generated tracking code
    """
    try:
        # Get project code
        if not project_code:
            project_code = (
                frappe.db.get_value("GRM Project", project_id, "project_code")
                or project_id
                or "PROJ"
            )

        # Clean project code
        clean_code = (
            "".join(c.upper() for c in str(project_code) if c.isalnum())[:10] or "PROJ"
        )

        # Format date as YYMMDD
        if not issue_date:
            issue_date = datetime.now()
        elif isinstance(issue_date, str):
            issue_date = datetime.strptime(issue_date, "%Y-%m-%d")

        date_str = issue_date.strftime("%y%m%d")

        # Generate random 4-digit number
        random_num = random.randint(1000, 9999)

        tracking_code = f"{clean_code}-{date_str}-{random_num}"

        frappe.log(
            f"Generated tracking code: {tracking_code} for project: {project_id}"
        )
        return tracking_code

    except Exception as e:
        frappe.log_error(f"Error generating tracking code: {str(e)}")
        frappe.log(f"Using fallback tracking code: {frappe.get_traceback()}")
        raise
