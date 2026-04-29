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
def list_assignments(project: str | None = None) -> list[dict]:
    """Return assignment rows for one project (or all if ``project`` is falsy/'all').

    Each row is enriched with display labels (``user_full_name``, ``role_name``,
    ``department_name``, ``region_name``) for convenient client rendering.
    """
    _gate()

    filters: dict[str, Any] = {}
    if project and project != "all":
        filters["project"] = project

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
        limit=0,
    )

    # Enrich with display labels (one round-trip per related doc; the
    # numbers we expect are small, so this stays simple and readable).
    for row in rows:
        row["user_full_name"] = (
            frappe.db.get_value("User", row["user"], "full_name") or row["user"]
        )
        if row.get("role"):
            row["role_name"] = (
                frappe.db.get_value("GRM Project Role", row["role"], "role_name")
                or row["role"]
            )
        if row.get("department"):
            row["department_name"] = (
                frappe.db.get_value(
                    "GRM Issue Department", row["department"], "department_name"
                )
                or row["department"]
            )
        if row.get("administrative_region"):
            row["region_name"] = (
                frappe.db.get_value(
                    "GRM Administrative Region",
                    row["administrative_region"],
                    "region_name",
                )
                or row["administrative_region"]
            )
    return rows


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
    - Regions: filtered by ``project`` if the column exists (defensive
      guard for schemas without that field).
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

    region_filters: dict[str, Any] = {}
    if frappe.db.has_column("GRM Administrative Region", "project"):
        region_filters["project"] = project
    regions = frappe.get_all(
        "GRM Administrative Region",
        filters=region_filters,
        fields=["name", "region_name"],
        order_by="region_name asc",
        limit=200,
    )

    return {"roles": roles, "departments": departments, "regions": regions}


@frappe.whitelist()
def search_users(txt: str = "") -> list[dict]:
    """Search active users by name/full_name/email. Limit 25 results."""
    _gate()
    txt = (txt or "").strip()

    base_filters = {"enabled": 1, "name": ["!=", "Administrator"]}
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
    frappe.delete_doc("GRM User Project Assignment", name)


@frappe.whitelist()
def resend_activation(name: str) -> None:
    """Generate a fresh activation code and email it to the user."""
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    doc = frappe.get_doc("GRM User Project Assignment", name)
    doc.resend_activation_code()


@frappe.whitelist()
def expire_activation(name: str) -> None:
    """Mark the assignment's activation code as expired."""
    _gate()
    if not name:
        frappe.throw(_("Assignment name is required"))
    doc = frappe.get_doc("GRM User Project Assignment", name)
    doc.expire_activation_code()
