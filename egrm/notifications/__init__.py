import frappe

def get_notification_config():
    """
    Return notification configuration for GRM module.
    """
    return {
        "for_doctype": {
            "GRM Issue": {
                "assigned": {
                    "doctype": "GRM Issue",
                    "field": "assignee",
                    "compare_with": "frappe.session.user",
                    "status": ["not in", ["Resolved", "Closed"]]
                },
                "open": {
                    "doctype": "GRM Issue",
                    "status": "Open"
                },
                "escalated": {
                    "doctype": "GRM Issue",
                    "escalate_flag": 1,
                    "status": ["not in", ["Resolved", "Closed"]]
                },
                "overdue": {
                    "doctype": "GRM Issue",
                    "resolution_days": [">", 10],
                    "status": ["not in", ["Resolved", "Closed"]]
                },
            },
            "GRM User Project Assignment": {
                "new_assignments": {
                    "doctype": "GRM User Project Assignment",
                    "field": "user",
                    "compare_with": "frappe.session.user",
                    "creation": [">=", "-7 days"]
                }
            }
        },
        
        # Function to get count of open issues for the sidebar
        "count": {
            "GRM Issue": {
                "filters": {
                    "status": ["not in", ["Resolved", "Closed"]]
                }
            }
        },
        
        "conditions": {
            "GRM Issue": [
                {
                    "type": "assiged",
                    "filters": {
                        "assignee": "frappe.session.user",
                        "status": ["not in", ["Resolved", "Closed"]]
                    }
                },
                {
                    "type": "escalated",
                    "filters": {
                        "escalate_flag": 1,
                        "status": ["not in", ["Resolved", "Closed"]]
                    }
                },
                {
                    "type": "open_for_me",
                    "filters": {
                        "assignee": "frappe.session.user",
                        "status": "Open"
                    }
                }
            ]
        },
        
        # DocTypes with notifications enabled
        "notification_subtypes": {
            "GRM Issue": [
                "assigned",
                "status_change",
                "escalated",
                "comment",
                "feedback"
            ]
        },
        
        # Default sorting criteria
        "default_sort_filters": {
            "GRM Issue": ["creation", "DESC"]
        }
    }