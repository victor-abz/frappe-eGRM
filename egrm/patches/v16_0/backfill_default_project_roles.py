"""For every existing GRM Project, create the four default GRM Project
Roles (Administrator / Project Manager / Department Head / Field Officer)
with their canonical duty composition. Idempotent — skips roles that
already exist."""

import frappe


DEFAULT_ROLES: list[dict] = [
    {
        "role_name": "GRM Administrator",
        "duties": ["Intake", "Review", "Assignment", "Investigate & Resolve", "Feedback", "Supervise"],
        "description": "Full GRM authority within the project.",
    },
    {
        "role_name": "GRM Project Manager",
        "duties": ["Review", "Assignment", "Investigate & Resolve", "Feedback", "Supervise"],
        "description": "Manages the project's GRM operations, team, and configuration.",
    },
    {
        "role_name": "GRM Department Head",
        "duties": ["Review", "Assignment", "Investigate & Resolve", "Feedback"],
        "description": "Oversees the assigned department; routes and tracks issues.",
    },
    {
        "role_name": "GRM Field Officer",
        "duties": ["Intake", "Investigate & Resolve", "Feedback"],
        "description": "Logs and resolves grievances on the ground in their assigned region.",
    },
]


def execute() -> None:
    projects = frappe.get_all("GRM Project", pluck="name")
    print(f"Backfilling default Project Roles for {len(projects)} project(s)...")
    for project in projects:
        for spec in DEFAULT_ROLES:
            full_name = f"{project}-{spec['role_name']}"
            if frappe.db.exists("GRM Project Role", full_name):
                continue
            doc = frappe.new_doc("GRM Project Role")
            doc.role_name = spec["role_name"]
            doc.project = project
            doc.description = spec["description"]
            doc.is_active = 1
            for duty in spec["duties"]:
                if frappe.db.exists("GRM Duty", duty):
                    doc.append("duties", {"duty": duty})
            doc.flags.ignore_permissions = True
            doc.insert()
