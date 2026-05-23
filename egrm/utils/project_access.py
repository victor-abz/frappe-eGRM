"""Project-scoped admin authorization helpers.

Used by all duty-driven wizard / user-management endpoints that mutate
assignment-level state. Centralizes the rule:

    "A caller may mutate a GRM User Project Assignment record only if they
    hold an active 'Supervise' duty on the *same* project, or are a
    platform-wide role (System Manager / GRM Platform Administrator)."

This closes the cross-project-tampering hole where a project admin on
Project A could PATCH/DELETE assignments belonging to Project B simply by
passing the assignment's name.
"""

from __future__ import annotations

import frappe

from egrm.api._roles import GRM_ALL_PROJECTS_ROLES

# Platform-wide roles always bypass project scoping.
PLATFORM_ROLES = {"System Manager", "GRM Platform Administrator"}


def get_user_accessible_projects(user: str) -> list[str]:
    """Return the list of GRM Project names a user can access (web/stats scope).

    Admins and all-projects roles see every project; otherwise the user
    sees the projects they hold an active assignment for.

    Note: the mobile sync layer (`egrm.api.sync`) uses a stricter variant
    that also requires `activation_status = 'Activated'` on the assignment.
    Web/stats contexts don't gate on mobile activation, so they call this
    helper instead.
    """
    if user == "Administrator" or GRM_ALL_PROJECTS_ROLES & set(frappe.get_roles(user)):
        projects = frappe.get_all("GRM Project", fields=["name"])
        return [p.name for p in projects]

    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "is_active": 1},
        fields=["project"],
    )
    return [a.project for a in assignments]


def is_platform_admin(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return bool(set(frappe.get_roles(user)) & PLATFORM_ROLES)


def has_project_admin(project: str, user: str | None = None) -> bool:
    """Return True if user is platform-admin OR holds active Supervise duty on project."""
    user = user or frappe.session.user
    if not project:
        return False
    if is_platform_admin(user):
        return True
    rows = frappe.db.sql(
        """
        SELECT a.name FROM `tabGRM User Project Assignment` a
        JOIN `tabGRM Project Role` r ON r.name = a.role
        JOIN `tabGRM Project Role Duty` d ON d.parent = r.name
        WHERE a.user = %s AND a.project = %s AND a.is_active = 1
          AND d.duty = 'Supervise'
        LIMIT 1
        """,
        (user, project),
    )
    return bool(rows)


def assert_project_admin(project: str, user: str | None = None) -> None:
    """Raise PermissionError if user lacks Supervise duty on the given project."""
    if not has_project_admin(project, user):
        frappe.throw(
            f"Not authorized for project {project}",
            frappe.PermissionError,
        )


def assert_assignment_admin(assignment_name: str, user: str | None = None) -> None:
    """Load assignment by name, then assert caller is project-admin for its project.

    Prevents a project admin on Project A from acting on an assignment in Project B
    by passing only the assignment's `name`.
    """
    project = frappe.db.get_value(
        "GRM User Project Assignment", assignment_name, "project"
    )
    if not project:
        frappe.throw(
            f"Assignment {assignment_name} not found",
            frappe.DoesNotExistError,
        )
    assert_project_admin(project, user)
