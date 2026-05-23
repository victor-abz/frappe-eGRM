"""Seed the canonical 6 duties (WB GRM Customization Questionnaire § 4)."""

import frappe

DUTIES: list[dict[str, str]] = [
    {"duty_name": "Intake", "label": "Intake", "lifecycle_phase": "Intake", "icon": "inbox",
     "description": "Create new GRM Issues. Combines Uptake and Data Entry from the WB template (digital-only)."},
    {"duty_name": "Review", "label": "Review", "lifecycle_phase": "Triage", "icon": "check-circle",
     "description": "Validate categorisation, eligibility, severity. Move issues from Submitted to Reviewed/Rejected."},
    {"duty_name": "Assignment", "label": "Assignment", "lifecycle_phase": "Triage", "icon": "users",
     "description": "Set or change the issue assignee, route to a department or admin level."},
    {"duty_name": "Investigate & Resolve", "label": "Investigate & Resolve", "lifecycle_phase": "Resolution", "icon": "search",
     "description": "Add comments, evidence, and propose a resolution. Submit the issue."},
    {"duty_name": "Feedback", "label": "Feedback", "lifecycle_phase": "Feedback", "icon": "message-square",
     "description": "Track citizen rating, manage the appeal flow, close the issue."},
    {"duty_name": "Supervise", "label": "Supervise", "lifecycle_phase": "Oversight", "icon": "bar-chart",
     "description": "Read all in-scope issues, force-reassign/close, view dashboards, manage user assignments within scope."},
]


def execute() -> None:
    print(f"Seeding {len(DUTIES)} duties into GRM Duty catalog...")
    for duty in DUTIES:
        if frappe.db.exists("GRM Duty", duty["duty_name"]):
            continue
        doc = frappe.new_doc("GRM Duty")
        doc.update(duty)
        doc.flags.ignore_permissions = True
        doc.insert()
