"""Create the 6 duty-named Frappe Roles + the GRM Platform Administrator role.

These are the new L1 (doctype permission) primitives: each duty maps to
exactly one Frappe Role. Doctype permissions[] arrays are rewritten in
Task 1.7b to use these. Idempotent — safe to re-run."""

import frappe


NEW_ROLES: list[str] = [
    "GRM Intake",
    "GRM Review",
    "GRM Assignment",
    "GRM Investigate & Resolve",
    "GRM Feedback",
    "GRM Supervise",
    "GRM Platform Administrator",
]


def execute() -> None:
    print(f"Seeding {len(NEW_ROLES)} GRM duty/platform roles...")
    for role_name in NEW_ROLES:
        if frappe.db.exists("Role", role_name):
            continue
        doc = frappe.new_doc("Role")
        doc.role_name = role_name
        doc.desk_access = 1
        doc.disabled = 0
        doc.flags.ignore_permissions = True
        doc.insert()
