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

        # Strip every Has Role row that still references this legacy role
        # — across any parenttype (User, Report, Workspace, Page, etc.).
        # Workspaces are handled by delete_legacy_workspaces.py running
        # earlier; this catches Reports and any other surface still pinning
        # the legacy role.
        stale_has_role = frappe.get_all(
            "Has Role",
            filters={"role": legacy},
            fields=["name", "parent", "parenttype"],
        )
        for row in stale_has_role:
            frappe.db.delete("Has Role", {"name": row["name"]})

        # Re-check after the cleanup. If the role is somehow still pinned
        # via DocPerm or a Custom DocPerm, log and skip — don't force-drop
        # since that could corrupt referencing rows.
        perm = frappe.db.exists("DocPerm", {"role": legacy})
        if perm:
            frappe.log_error(
                title="Cannot drop legacy GRM role",
                message=f"{legacy} still referenced by DocPerm row {perm}",
            )
            continue

        frappe.delete_doc("Role", legacy, ignore_permissions=True, force=True)
        print(f"Deleted legacy role: {legacy}")
