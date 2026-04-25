"""Delete the four legacy GRM Frappe Roles. Runs after migrate_users_to_duty_roles
has stripped them from User.roles."""

import frappe


LEGACY = [
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
]


def execute() -> None:
    for legacy in LEGACY:
        if not frappe.db.exists("Role", legacy):
            continue
        ref = frappe.db.exists("Has Role", {"role": legacy})
        if ref:
            frappe.log_error(
                title="Cannot drop legacy GRM role",
                message=f"{legacy} still referenced by Has Role row {ref}",
            )
            continue
        perm = frappe.db.exists("DocPerm", {"role": legacy})
        if perm:
            frappe.log_error(
                title="Cannot drop legacy GRM role",
                message=f"{legacy} still referenced by DocPerm row {perm}",
            )
            continue
        frappe.delete_doc("Role", legacy, ignore_permissions=True, force=True)
        print(f"Deleted legacy role: {legacy}")
