app_name = "egrm"
app_title = "EGRM"
app_publisher = "Victor Abizeyimana"
app_description = "Electronic Grievance Redress Mechanism"
app_email = "svicky.shema@gmail.com"
app_license = "MIT"

# Website Configurations
home_page = "login"

# Role home pages
role_home_page = {
    "GRM Administrator": "grm-administrator",
    "GRM Project Manager": "grm-project-manager",
    "GRM Department Head": "grm-department-head",
    "GRM Field Officer": "grm-field-officer",
    "GRM Analyst": "grm-analyst"
}

# Notification Configuration
notification_config = "egrm.notifications.get_notification_config"

# Permissions Scripts
permission_query_conditions = {
    "GRM Issue": "egrm.server_scripts.grm_issue_permissions.permission_query_conditions",
}

has_permission = {
    "GRM Issue": "egrm.server_scripts.grm_issue_permissions.has_permission",
}

# Document Events
# doc_events = {
#     "GRM Issue": {
#         "on_update": "egrm.doctype.grm_issue.grm_issue.on_update",
#         "on_submit": "egrm.doctype.grm_issue.grm_issue.on_submit",
#         "on_cancel": "egrm.doctype.grm_issue.grm_issue.on_cancel"
#     }
# }

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "egrm.server_scripts.scheduled_tasks.check_issue_escalations"
    ]
}

# User Data Protection
user_data_fields = [
    {
        "doctype": "GRM Issue",
        "filter_by": "citizen_type",
        "redact_fields": ["citizen", "contact_information"],
        "partial": 1,
    }
]
