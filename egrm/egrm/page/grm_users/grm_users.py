"""Server endpoints for the 'GRM Users by Project' custom desk page.

Provides whitelisted CRUD plus activation-code actions over the
``GRM User Project Assignment`` doctype, scoped to platform-admin
roles. The doctype controller already keeps ``User Permission`` rows
in sync via its ``validate``/``before_save``/``on_update``/``on_trash``
hooks, so this page only needs to drive the assignment records.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from egrm.utils.project_access import (
    assert_assignment_admin,
    assert_project_admin,
)

ALLOWED_PAGE_ROLES = {
    "System Manager",
    "GRM Platform Administrator",
    "GRM Supervise",
}


def _gate() -> None:
    """Raise PermissionError unless caller has at least one allowed role."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not (user_roles & ALLOWED_PAGE_ROLES):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _coerce_payload(payload: Any) -> dict:
    """Return ``payload`` as a dict regardless of whether it arrived as JSON."""
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (ValueError, TypeError):
            frappe.throw(_("Invalid payload: expected a JSON object"))
    if isinstance(payload, dict):
        return payload
    frappe.throw(_("Invalid payload: expected a JSON object"))
    return {}  # pragma: no cover - frappe.throw raises


@frappe.whitelist()
def list_assignments(
    project: str | None = None,
    search: str | None = None,
    start: int = 0,
    page_length: int = 20,
) -> dict:
    """Return paginated assignment rows for one project (or all).

    Args:
        project: GRM Project name (or ``"all"`` / falsy for every project).
        search: Optional substring; matches user id, full name, or email.
            Filtering is performed in SQL via ``or_filters`` against the
            User table, so we never load all users into memory.
        start: Offset for pagination (default 0).
        page_length: Page size (default 20). Capped at 200 server-side.

    Returns:
        ``{"rows": [...enriched assignment rows...], "total": int,
           "start": int, "page_length": int}``.

    Each row is enriched with display labels (``user_full_name``, ``role_name``,
    ``department_name``, ``region_name``) for convenient client rendering.
    """
    _gate()

    # Coerce / sanitise pagination args (Frappe REST sends them as strings).
    try:
        start = max(0, int(start or 0))
    except (TypeError, ValueError):
        start = 0
    try:
        page_length = max(1, min(int(page_length or 20), 200))
    except (TypeError, ValueError):
        page_length = 20

    filters: dict[str, Any] = {}
    if project and project != "all":
        filters["project"] = project

    # If a search term is provided, resolve matching User ids first via a
    # SQL ``LIKE`` (case-insensitive on MariaDB by default) on name /
    # full_name / email, then constrain the assignment query to those users.
    matching_user_ids: list[str] | None = None
    search_term = (search or "").strip()
    if search_term:
        like = f"%{search_term}%"
        matching = frappe.get_all(
            "User",
            or_filters={
                "name": ["like", like],
                "full_name": ["like", like],
                "email": ["like", like],
            },
            fields=["name"],
            limit=0,
        )
        matching_user_ids = [u["name"] for u in matching]
        if not matching_user_ids:
            return {
                "rows": [],
                "total": 0,
                "start": start,
                "page_length": page_length,
            }
        filters["user"] = ["in", matching_user_ids]

    total = frappe.db.count("GRM User Project Assignment", filters=filters)

    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters=filters,
        fields=[
            "name",
            "user",
            "project",
            "role",
            "department",
            "administrative_region",
            "is_active",
            "position_title",
            "activation_code",
            "activation_status",
            "activation_expires_on",
        ],
        order_by="project asc, user asc",
        start=start,
        page_length=page_length,
    )

    # Enrich with display labels via batched lookups (one query per related
    # doctype instead of N+1).
    user_ids = {r["user"] for r in rows if r.get("user")}
    role_ids = {r["role"] for r in rows if r.get("role")}
    dept_ids = {r["department"] for r in rows if r.get("department")}
    region_ids = {
        r["administrative_region"] for r in rows if r.get("administrative_region")
    }

    user_map = (
        {
            u["name"]: u["full_name"]
            for u in frappe.get_all(
                "User",
                filters={"name": ["in", list(user_ids)]},
                fields=["name", "full_name"],
            )
        }
        if user_ids
        else {}
    )
    role_map = (
        {
            r["name"]: r["role_name"]
            for r in frappe.get_all(
                "GRM Project Role",
                filters={"name": ["in", list(role_ids)]},
                fields=["name", "role_name"],
            )
        }
        if role_ids
        else {}
    )
    dept_map = (
        {
            d["name"]: d["department_name"]
            for d in frappe.get_all(
                "GRM Issue Department",
                filters={"name": ["in", list(dept_ids)]},
                fields=["name", "department_name"],
            )
        }
        if dept_ids
        else {}
    )
    region_map = (
        {
            a["name"]: a["region_name"]
            for a in frappe.get_all(
                "GRM Administrative Region",
                filters={"name": ["in", list(region_ids)]},
                fields=["name", "region_name"],
            )
        }
        if region_ids
        else {}
    )

    for row in rows:
        row["user_full_name"] = user_map.get(row["user"], row["user"])
        if row.get("role"):
            row["role_name"] = role_map.get(row["role"], row["role"])
        if row.get("department"):
            row["department_name"] = dept_map.get(row["department"], row["department"])
        if row.get("administrative_region"):
            row["region_name"] = region_map.get(
                row["administrative_region"], row["administrative_region"]
            )

    return {
        "rows": rows,
        "total": total,
        "start": start,
        "page_length": page_length,
    }


@frappe.whitelist()
def list_projects() -> list[dict]:
    """Return all GRM Projects (active + inactive) for the project filter."""
    _gate()
    return frappe.get_all(
        "GRM Project",
        fields=["name", "title", "project_code", "is_active"],
        order_by="title asc",
        limit=0,
    )


@frappe.whitelist()
def list_project_lookups(project: str) -> dict:
    """Return roles, departments, and regions scoped to ``project``.

    - Roles: filtered by project + ``is_active = 1``.
    - Departments: filtered via the ``GRM Project Link`` child table on
      ``GRM Issue Department``. We use a parameterized SQL query because
      ``frappe.get_all`` does not natively support child-table filters.
    - Regions: filtered by ``project`` (required field on the doctype).
    """
    _gate()
    if not project:
        return {"roles": [], "departments": [], "regions": []}

    roles = frappe.get_all(
        "GRM Project Role",
        filters={"project": project, "is_active": 1},
        fields=["name", "role_name"],
        order_by="role_name asc",
        limit=0,
    )

    departments = frappe.db.sql(
        """
        SELECT DISTINCT d.name, d.department_name
        FROM `tabGRM Issue Department` d
        INNER JOIN `tabGRM Project Link` pl
            ON pl.parent = d.name
           AND pl.parenttype = 'GRM Issue Department'
        WHERE pl.project = %(project)s
        ORDER BY d.department_name ASC
        """,
        {"project": project},
        as_dict=True,
    )

    regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": project},
        fields=["name", "region_name"],
        order_by="region_name asc",
        limit=200,
    )

    return {"roles": roles, "departments": departments, "regions": regions}


@frappe.whitelist()
def search_users(txt: str = "", project: str | None = None) -> list[dict]:
    """Search active users by name/full_name/email. Limit 25 results.

    Review fix B2: scope the user directory by project. Two modes:

    - ``project`` supplied: assert the caller is project-admin on it
      (cross-project enumeration block) and return ALL enabled users —
      this is the "add a user to project P" affordance.
    - ``project`` omitted (default): platform admins see everything;
      non-platform admins see only users who already hold an assignment
      on at least one of the caller's own admin projects (prevents a
      project admin on P1 from enumerating the entire User table).
    """
    _gate()
    txt = (txt or "").strip()

    if project:
        # Reuse the project-admin gate from utils.project_access — this
        # ensures the caller actually controls the project they're
        # passing as a scope.
        from egrm.utils.project_access import assert_project_admin
        assert_project_admin(project)

    base_filters: dict[str, Any] = {
        "enabled": 1,
        "name": ["!=", "Administrator"],
    }

    # For non-platform admins with no explicit ``project`` filter, scope
    # the result set to users assigned to *some* project the caller
    # supervises.
    from egrm.utils.project_access import is_platform_admin

    if not project and not is_platform_admin():
        # Caller's admin projects (the ones where they hold Supervise
        # duty). If they have none, return empty rather than leak the
        # whole User table.
        admin_projects = frappe.db.sql_list(
            """
            SELECT DISTINCT a.project FROM `tabGRM User Project Assignment` a
            JOIN `tabGRM Project Role` r ON r.name = a.role
            JOIN `tabGRM Project Role Duty` d ON d.parent = r.name
            WHERE a.user = %s AND a.is_active = 1 AND d.duty = 'Supervise'
            """,
            (frappe.session.user,),
        )
        if not admin_projects:
            return []
        scoped_users = frappe.db.sql_list(
            """
            SELECT DISTINCT user FROM `tabGRM User Project Assignment`
            WHERE project IN %s AND user IS NOT NULL AND user != ''
            """,
            (tuple(admin_projects),),
        )
        if not scoped_users:
            return []
        base_filters["name"] = ["in", scoped_users]

    kwargs: dict[str, Any] = {
        "filters": base_filters,
        "fields": ["name", "full_name", "email"],
        "order_by": "full_name asc",
        "limit": 25,
    }
    if txt:
        like = f"%{txt}%"
        kwargs["or_filters"] = {
            "name": ["like", like],
            "full_name": ["like", like],
            "email": ["like", like],
        }

    return frappe.get_all("User", **kwargs)


@frappe.whitelist()
def create_assignment(payload: Any) -> str:
    """Create a new GRM User Project Assignment and return its name.

    The doctype controller installs the appropriate Frappe duty role on
    the user via ``assign_role_to_user`` during ``before_save`` /
    ``after_insert`` and emits the activation email when applicable.
    """
    _gate()
    data = _coerce_payload(payload)

    if not data.get("user"):
        frappe.throw(_("User is required"))
    if not data.get("project"):
        frappe.throw(_("Project is required"))
    if not data.get("role"):
        frappe.throw(_("Project Role is required"))

    # Scope: caller must hold Supervise duty on the *target* project, even
    # if they hold it on another project.
    assert_project_admin(data["project"])

    doc = frappe.new_doc("GRM User Project Assignment")
    for fieldname in (
        "user",
        "project",
        "role",
        "department",
        "administrative_region",
        "position_title",
    ):
        value = data.get(fieldname)
        if value:
            doc.set(fieldname, value)
    doc.is_active = 1 if data.get("is_active", 1) else 0
    doc.insert()
    return doc.name


@frappe.whitelist()
def update_assignment(name: str, payload: Any) -> None:
    """Update mutable fields on an existing assignment.

    Note: ``user`` and ``project`` are intentionally NOT updatable —
    reassigning a record to a different user/project should be done by
    deleting and re-creating, so the controller's permission sync runs
    cleanly.
    """
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    assert_assignment_admin(name)
    data = _coerce_payload(payload)

    doc = frappe.get_doc("GRM User Project Assignment", name)
    for fieldname in (
        "role",
        "department",
        "administrative_region",
        "position_title",
        "is_active",
    ):
        if fieldname in data:
            value = data[fieldname]
            if fieldname == "is_active":
                value = 1 if value else 0
            doc.set(fieldname, value)
    doc.save()


@frappe.whitelist()
def delete_assignment(name: str) -> None:
    """Delete an assignment. Controller's ``on_trash`` strips the duty role."""
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    assert_assignment_admin(name)
    frappe.delete_doc("GRM User Project Assignment", name)


@frappe.whitelist()
def resend_activation(name: str) -> None:
    """Generate a fresh activation code and email it to the user."""
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    assert_assignment_admin(name)
    doc = frappe.get_doc("GRM User Project Assignment", name)
    doc.resend_activation_code()


@frappe.whitelist()
def expire_activation(name: str) -> None:
    """Mark the assignment's activation code as expired."""
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    assert_assignment_admin(name)
    doc = frappe.get_doc("GRM User Project Assignment", name)
    doc.expire_activation_code()
