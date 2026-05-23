"""boot_session hook — populate frappe.boot.egrm with per-user duty data
so the Workspace JSON's display_depends_on predicates can evaluate them
client-side without a round trip."""

import frappe


PLATFORM_ROLES = {"System Manager", "GRM Platform Administrator"}


def boot_session(bootinfo) -> None:
    user = frappe.session.user
    if user in ("Guest", "", None):
        bootinfo.egrm = {
            "active_project": None,
            "duties": [],
            "is_platform_admin": False,
            "available_projects": [],
        }
        return

    available = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user,
            "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        fields=["project"],
        distinct=True,
    )
    available_projects = sorted({a.project for a in available})

    user_default = (
        frappe.db.get_value("User", user, "default_project")
        if frappe.get_meta("User").has_field("default_project")
        else None
    )
    if user_default in available_projects:
        active = user_default
    elif available_projects:
        active = available_projects[0]
    else:
        active = None

    duties = _get_duties(user, active) if active else []

    bootinfo.egrm = {
        "active_project": active,
        "duties": duties,
        "is_platform_admin": bool(set(frappe.get_roles(user)) & PLATFORM_ROLES),
        "available_projects": available_projects,
    }


def _get_duties(user: str, project: str) -> list[str]:
    """Return the deduplicated, alphabetised list of duty_name strings the
    user holds via active assignments on this project."""
    role_names = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user,
            "project": project,
            "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        pluck="role",
    )
    if not role_names:
        return []
    return sorted(
        set(
            frappe.get_all(
                "GRM Project Role Duty",
                filters={"parent": ["in", role_names]},
                pluck="duty",
            )
        )
    )
