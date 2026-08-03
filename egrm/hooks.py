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
    },
    # Canonical 6 duties (WB GRM Customization Questionnaire § 4). Shipped
    # as a fixture so they land on `bench install-app` AND every subsequent
    # migrate — the equivalent post_model_sync patch
    # (egrm.patches.v16_0.seed_duty_catalog) only runs on migrate, not on
    # a fresh install, which left GRM Duty empty and broke Project Role
    # creation in the AQE onboarding wizard.
    {
        "dt": "GRM Duty"
    },
]

# Default homepage for guest and logged-in users (overrides Website Settings fallback)
home_page = "grm-portal"
website_home_page = "grm-portal"

# Website Configurations
website_route_rules = [
    {"from_route": "/download-app", "to_route": "download_app"},
    {"from_route": "/grm-portal/<path:app_path>", "to_route": "grm-portal"},
]

# 302 redirects from the canonical citizen-facing pretty URLs (see
# 00-test-plan.md, UI-09..UI-12) to the actual `/grm-portal/<route>`
# paths the React SPA's own router knows about. Without these,
# /grievance-dashboard etc. render Frappe's 404 page even though the
# SPA is installed and the corresponding sections exist.
website_redirects = [
    {"source": "/grievance-dashboard", "target": "/grm-portal/dashboard"},
    {"source": "/grievance",           "target": "/grm-portal/submit"},
    {"source": "/track-complaint",     "target": "/grm-portal/track"},
    {"source": "/grievance-reports",   "target": "/grm-portal/reports"},
]

# Ensure Website Settings points to the portal on (re)install and migrations
after_install = "egrm.install.after_install"
after_migrate = [
    "egrm.install.set_default_home_page",
    "egrm.install.set_default_desk_app",
    "egrm.install.seed_desktop_icons",
    "egrm.install.seed_grm_role_catalog",
]

# Branding for the v16 Desktop / Apps screen tile
app_logo_url = "/assets/egrm/images/egrm-logo.svg"

# Client-side duty filter — hides phase-group cards in the eGRM workspace
# whose duty the user doesn't hold (v16 Workspace Link has no
# display_depends_on, so JSON-level gating doesn't work).
#
# `egrm_app_route` is the JS companion to `app_route_passthrough.py`:
# server-side we rewrite `/app/<rest>` → `/desk/<rest>` without a 301
# so the URL bar keeps `/app/...`; client-side we teach
# `frappe.router.strip_prefix` to peel `app/` exactly like `desk/` so
# the SPA's route parser doesn't mis-route `/app/grm-project-wizard` as
# the page named "app".
app_include_js = [
    "egrm_workspace_filter.bundle.js",
    "egrm_app_route.bundle.js",
]

# Boot session hook — inject frappe.boot.egrm with per-user duty payload
boot_session = "egrm.utils.boot.boot_session"

# Auto-JSON-decode form_dict child-table values on /api/resource/* POSTs so
# that Frappe's `create_doc` v1 endpoint accepts JSON-stringified scalars
# (e.g. ``grm_project_link='[{"project":"RW-WB"}]'``) the same way it
# accepts pure-JSON request bodies. Without this, form-encoded child
# tables raise ``TypeError: 'str' object does not support item assignment``
# in BaseDocument._init_child when the document layer tries to extend.
before_request = [
    "egrm.utils.rest_form_decode.normalize_resource_form_dict",
    # Suppress the framework's `/app/* -> /desk/*` 301 so the browser
    # URL stays at `/app/<workspace>` after login (the AQE UI-0
    # Playwright assertion waits for `**/app**`).
    "egrm.utils.app_route_passthrough.app_route_passthrough",
    # `role_home_page` below sends staff to `app/egrm`, which PathResolver
    # cannot render for the bare domain (redirects are evaluated before the
    # home-page substitution), so `/` 404'd for anyone logged in. Pin the
    # web root to the portal for every user; login is unaffected.
    "egrm.utils.web_root_home.portal_home_at_web_root",
]

# Expose `frappe.boot.get_bootinfo` as a whitelisted endpoint so the
# AC-5 (ARCH-CONTRACT) test — and any external tooling that wants to
# verify the boot payload shape — can call it via /api/method/. The
# wrapper at `egrm.api.boot.get_bootinfo` is a thin pass-through that
# preserves Frappe's existing `boot_session` hook chain (which is where
# our `egrm.utils.boot.boot_session` injects `bootinfo.egrm`).
override_whitelisted_methods = {
    "frappe.boot.get_bootinfo": "egrm.api.boot.get_bootinfo",
}

# Project Setup Wizard — split into per-step modules under
# ``egrm/public/js/grm_project_wizard/``. Frappe's ``page_js`` hook
# concatenates these onto the page's own script (see
# ``frappe.core.doctype.page.page.Page.load_assets``), so the page
# directory's ``grm_project_wizard.js`` stays a thin entrypoint and
# bare cross-references between step classes resolve in the shared
# script scope. Order is human-readability only — class declarations
# are referenced from inside method bodies (call-time lookup), not
# at parse time.
page_js = {
    "grm-project-wizard": [
        "public/js/grm_project_wizard/_helpers.js",
        "public/js/grm_project_wizard/_wizard.js",
        "public/js/grm_project_wizard/step1_project_info.js",
        "public/js/grm_project_wizard/step2_admin_units.js",
        "public/js/grm_project_wizard/step2_admin_levels.js",
        "public/js/grm_project_wizard/step2_admin_regions.js",
        "public/js/grm_project_wizard/step3_issue_categories.js",
        "public/js/grm_project_wizard/step4_issue_types.js",
        "public/js/grm_project_wizard/step5_citizen_lookups.js",
        "public/js/grm_project_wizard/step6_notification_templates.js",
        "public/js/grm_project_wizard/step7_project_roles.js",
        "public/js/grm_project_wizard/step8_departments.js",
        "public/js/grm_project_wizard/step9_users.js",
        "public/js/grm_project_wizard/step9_users_list.js",
        "public/js/grm_project_wizard/step9_user_add.js",
        "public/js/grm_project_wizard/step9_user_import.js",
        "public/js/grm_project_wizard/step10_routing.js",
        "public/js/grm_project_wizard/step11_slas.js",
        "public/js/grm_project_wizard/step12_issue_statuses.js",
        "public/js/grm_project_wizard/step13_activate.js",
    ],
}

# Allow guest access
has_website_permission = {
    "Android App Version": "egrm.egrm.doctype.android_app_version.android_app_version.has_website_permission"
}

# Role home pages (post-duty-role migration: legacy 4 roles are gone;
# duty-roles all land on the unified eGRM workspace; platform admins land
# on the Platform workspace).
#
# Use `app/<workspace>` so the browser ends up at the canonical
# `/app/<workspace>` URL the AQE UI-0 Playwright assertion expects
# (`wait_for_url("**/app**")`). Frappe ships a built-in
# `/app/* -> /desk/*` 301; we suppress it via the
# `egrm.utils.app_route_passthrough.app_route_passthrough` before_request
# hook so the URL stays as /app/.
role_home_page = {
    "System Manager": "app/egrm",
    "GRM Platform Administrator": "app/egrm",
    "GRM Intake": "app/egrm",
    "GRM Review": "app/egrm",
    "GRM Assignment": "app/egrm",
    "GRM Investigate & Resolve": "app/egrm",
    "GRM Feedback": "app/egrm",
    "GRM Supervise": "app/egrm",
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

app_home = "/desk/egrm"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/egrm/images/egrm-logo.svg",
		"title": app_title,
		"route": app_home,
		"has_permission": "egrm.api.app_permission.check_app_permission",
	}
]
