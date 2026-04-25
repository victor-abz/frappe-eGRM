"""Keep User Permission rows in sync with GRM User Project Assignment.

Frappe's User Permission doctype scopes record-level access natively: a row
(user, allow="GRM Project", for_value=<project>, apply_to_all_doctypes=1)
auto-filters every doctype that links to GRM Project — including GRM Issue,
Issue Category, Administrative Region, Issue Department.
"""

import frappe


PROJECT_DOCTYPE = "GRM Project"


def _is_active(assignment) -> bool:
    if not getattr(assignment, "is_active", 0):
        return False
    status = getattr(assignment, "activation_status", None)
    return status in (None, "", "Activated")


def grant_project_access(user: str, project: str) -> None:
    """Upsert a User Permission granting `user` access to `project`."""
    if not user or user in ("Administrator", "Guest") or not project:
        return
    if frappe.db.exists(
        "User Permission",
        {"user": user, "allow": PROJECT_DOCTYPE, "for_value": project},
    ):
        return
    doc = frappe.new_doc("User Permission")
    doc.user = user
    doc.allow = PROJECT_DOCTYPE
    doc.for_value = project
    doc.apply_to_all_doctypes = 1
    doc.flags.ignore_permissions = True
    doc.insert()


def revoke_project_access(
    user: str,
    project: str,
    exclude_assignment: str | None = None,
) -> None:
    """Delete the User Permission for (user, project) iff no OTHER active
    assignment for the same pair still exists.

    `exclude_assignment` lets the caller exclude the row about to be deleted
    (in `on_trash`, the row is still in the DB at hook time)."""
    if not user or not project:
        return
    filters = {
        "user": user,
        "project": project,
        "is_active": 1,
        "activation_status": ["in", ("Activated", "")],
    }
    if exclude_assignment:
        filters["name"] = ["!=", exclude_assignment]
    if frappe.db.exists("GRM User Project Assignment", filters):
        return
    rows = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": PROJECT_DOCTYPE, "for_value": project},
        pluck="name",
    )
    for name in rows:
        frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)


def sync_assignment(assignment) -> None:
    """Apply or remove the User Permission for this assignment based on its
    current is_active + activation_status state."""
    if _is_active(assignment):
        grant_project_access(assignment.user, assignment.project)
    else:
        revoke_project_access(
            assignment.user,
            assignment.project,
            exclude_assignment=assignment.name,
        )
