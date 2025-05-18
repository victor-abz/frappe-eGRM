import frappe
import logging
from datetime import datetime, timedelta
from frappe.utils import now_datetime, add_days

log = logging.getLogger(__name__)

def check_issue_escalations():
    """Check for issues that need escalation based on SLA"""
    try:
        log.info("Running scheduled check for issue escalations")
        
        # Get all active projects with auto escalation enabled
        projects = frappe.get_all(
            "GRM Project",
            filters={
                "is_active": 1,
                "auto_escalation_days": [">", 0]
            },
            fields=["name", "auto_escalation_days"]
        )
        
        if not projects:
            log.info("No active projects with auto escalation found")
            return
            
        for project in projects:
            process_project_escalations(project.name, project.auto_escalation_days)
            
        log.info("Completed scheduled check for issue escalations")
    except Exception as e:
        log.error(f"Error in scheduled check for issue escalations: {str(e)}")
        
def process_project_escalations(project, escalation_days):
    """Process escalations for a specific project"""
    try:
        log.info(f"Processing escalations for project {project}")
        
        # Get open statuses for this project
        open_statuses = frappe.get_all(
            "GRM Issue Status",
            filters={
                "open_status": 1
            },
            fields=["name"],
            joins=[
                ("GRM Project Link", "GRM Issue Status.name=GRM Project Link.parent")
            ],
            filters_1={
                "GRM Project Link.project": project
            }
        )
        
        if not open_statuses:
            log.info(f"No open statuses found for project {project}")
            return
            
        open_status_names = [s.name for s in open_statuses]
        status_list = "', '".join(open_status_names)
        
        # Calculate the date threshold for escalation
        threshold_date = add_days(now_datetime(), -escalation_days)
        
        # Find issues that need escalation
        issues = frappe.db.sql(f"""
            SELECT name
            FROM `tabGRM Issue`
            WHERE project = %s
            AND status IN ('{status_list}')
            AND escalate_flag = 0
            AND created_date < %s
        """, (project, threshold_date), as_dict=1)
        
        if not issues:
            log.info(f"No issues need escalation for project {project}")
            return
            
        log.info(f"Found {len(issues)} issues needing escalation for project {project}")
        
        # Process each issue
        for issue in issues:
            try:
                doc = frappe.get_doc("GRM Issue", issue.name)
                
                # Set escalation flag
                doc.db_set("escalate_flag", 1)
                
                # Add log entry
                days_open = (now_datetime() - doc.created_date).days
                doc.add_log(f"Issue automatically escalated after {days_open} days by scheduled task", "Administrator")
                
                # Get category's escalation department
                dept = frappe.db.get_value("GRM Issue Category", doc.category, "assigned_escalation_department")
                
                if dept:
                    # Get department head
                    head = frappe.db.get_value("GRM Issue Department", dept, "head")
                    
                    if head:
                        # Assign to department head
                        doc.db_set("assignee", head)
                        
                        # Add log entry
                        doc.add_log(f"Issue assigned to escalation department head {head} by scheduled task", "Administrator")
                        
                        # Notify department head
                        frappe.sendmail(
                            recipients=[head],
                            sender="noreply@example.com",
                            subject=f"Issue Escalated: {doc.name}",
                            message=f"Issue {doc.name} ({doc.title}) has been escalated to you due to SLA breach.",
                            reference_doctype="GRM Issue",
                            reference_name=doc.name
                        )
                
                log.info(f"Successfully escalated issue {issue.name}")
            except Exception as e:
                log.error(f"Error processing escalation for issue {issue.name}: {str(e)}")
    except Exception as e:
        log.error(f"Error processing escalations for project {project}: {str(e)}")