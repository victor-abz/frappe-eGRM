app_name = "egrm"
app_title = "EGRM"
app_publisher = "Victor Abizeyimana"
app_description = "Electronic Grievance Redress Mechanism"
app_email = "svicky.shema@gmail.com"
app_license = "MIT"

fixtures = [
    {
        "dt": "Email Template",
        "filters": [["name", "like", "GRM%"]]
    }
]

# Default homepage for guest and logged-in users (overrides Website Settings fallback)
home_page = "grm-portal"
website_home_page = "grm-portal"

# Website Configurations
website_route_rules = [
    {"from_route": "/download-app", "to_route": "download_app"},
    {"from_route": "/grm-portal/<path:app_path>", "to_route": "grm-portal"},
]

# Ensure Website Settings points to the portal on (re)install and migrations
after_install = "egrm.install.after_install"
after_migrate = [
    "egrm.install.set_default_home_page",
    "egrm.install.seed_desktop_icons",
]

# Branding for the v16 Desktop / Apps screen tile
app_logo_url = "/assets/egrm/images/egrm-logo.svg"

# Allow guest access
has_website_permission = {
    "Android App Version": "egrm.egrm.doctype.android_app_version.android_app_version.has_website_permission"
}

# Role home pages
role_home_page = {
    "GRM Administrator": "grm-administrator",
    "GRM Project Manager": "grm-project-manager",
    "GRM Department Head": "grm-department-head",
    "GRM Field Officer": "grm-field-officer"
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
        "egrm.server_scripts.scheduled_tasks.check_issue_escalations",
        "egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla"
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

app_home = "/desk/grm-field-officer"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/egrm/images/egrm-logo.svg",
		"title": app_title,
		"route": app_home,
		"has_permission": "egrm.api.app_permission.check_app_permission",
	}
]
