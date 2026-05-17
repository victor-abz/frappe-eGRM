"""Phase C (Step 9 Users): existing-users list/edit/bulk endpoints.

``list_project_users`` (C.1 listing) — paginated + searchable + filtered
list of ``GRM User Project Assignment`` rows for one project, joined with
``User`` / ``GRM Project Role`` / ``GRM Administrative Region`` /
``GRM Administrative Level Type`` so the UI can render the row in one
fetch (no per-row N+1).

``update_assignment_field`` / ``bulk_update_assignments`` /
``bulk_remove_assignments`` (C.1 mutations) — inline pill-edit and
bulk-actions helpers. Field allowlist guards against arbitrary writes.

Re-exported from ``grm_project_wizard.py`` so JS RPC paths
(``egrm.egrm.page.grm_project_wizard.grm_project_wizard.<method>``)
keep working unchanged. Split out from
``grm_project_wizard_user_import.py`` (Phase A) to keep each module under
the 400-line cap (plan §Engineering Conventions clause 4).
"""

from __future__ import annotations

import logging
from typing import Any

import frappe
from frappe import _

from egrm.utils.project_access import assert_assignment_admin

logger = logging.getLogger(__name__)


def _require_wizard_role() -> None:
    """Lazy shim — avoids circular import with ``grm_project_wizard``
    (which re-exports our endpoints at module bottom)."""
    from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
        _require_wizard_role as _impl,
    )
    return _impl()


# Inline-edit allowlist. Limiting to a fixed set guards against arbitrary
# field writes (e.g. ``name``, ``creation``, ``user``) that would either
# corrupt the row or bypass higher-level invariants. Plan §C.1 fixes this
# list explicitly.
_ASSIGNMENT_INLINE_EDIT_FIELDS: frozenset[str] = frozenset({
    "role",
    "administrative_region",
    "department",
    "position_title",
    "is_active",
    "activation_status",
})

# `activation_status` Select options (kept in lock-step with
# grm_user_project_assignment.json). The pill-edit popover surfaces only
# the operator-relevant subset (Pending Activation, Activated,
# Suspended); the others (Draft / Expired) are state-machine outputs the
# system writes — but we still accept them here for completeness so the
# server tests can also exercise the full set.
_ASSIGNMENT_STATUS_VALUES: frozenset[str] = frozenset({
    "Draft", "Pending Activation", "Activated", "Expired", "Suspended",
})


def _summary_counts(project: str) -> dict:
    """Return ``{active, pending, draft, unmapped}`` counts for ``project``.

    - ``active``    — ``activation_status == "Activated"``
    - ``pending``   — ``activation_status == "Pending Activation"``
    - ``draft``     — ``activation_status == "Draft"``
    - ``unmapped``  — ``administrative_region IS NULL`` (a row that's saved
                      but has no routing reach yet).

    Computed via four targeted ``frappe.db.count`` calls so we avoid
    pulling all rows just to bucket them.
    """
    base_filter = {"project": project}
    return {
        "active": frappe.db.count(
            "GRM User Project Assignment",
            {**base_filter, "activation_status": "Activated"},
        ),
        "pending": frappe.db.count(
            "GRM User Project Assignment",
            {**base_filter, "activation_status": "Pending Activation"},
        ),
        "draft": frappe.db.count(
            "GRM User Project Assignment",
            {**base_filter, "activation_status": "Draft"},
        ),
        "unmapped": frappe.db.count(
            "GRM User Project Assignment",
            [
                ["project", "=", project],
                ["administrative_region", "is", "not set"],
            ],
        ),
    }


def _coerce_int(value: Any, default: int, label: str) -> int:
    """Accept ``int`` or numeric string; raise ValidationError otherwise."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        frappe.throw(_("{0} must be an integer, got {1!r}").format(label, value))


@frappe.whitelist()
def list_project_users(
    project: str,
    search: str | None = None,
    level_type: str | None = None,
    role: str | None = None,
    status: str | None = None,
    start: int | str = 0,
    limit: int | str = 25,
) -> dict:
    """Return a paginated, searchable list of project user assignments.

    Joined fields (one query, manual SELECT for cross-doctype joins so
    ``frappe.get_all`` can't help us):

    - ``GRM User Project Assignment`` (alias ``a``): ``name``, ``user``,
      ``role``, ``administrative_region``, ``department``,
      ``position_title``, ``activation_status``, ``is_active``.
    - ``User`` (alias ``u``): ``full_name``, ``email``.
    - ``GRM Project Role`` (alias ``r``): ``role_name``, ``admin_level``.
    - ``GRM Administrative Region`` (alias ``ar``): ``region_name``,
      ``administrative_level``.
    - ``GRM Administrative Level Type`` (alias ``lt``): ``level_name`` —
      the "Level" pill text.

    Filters:
    - ``search`` — case-insensitive LIKE across ``u.full_name``,
      ``u.email``, ``a.position_title``.
    - ``level_type`` — only rows whose region's ``administrative_level``
      matches.
    - ``role`` — exact match on ``a.role``.
    - ``status`` — exact match on ``a.activation_status``.

    Returns ``{"rows": [...], "total": int, "summary": {...}}``.
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(_("project is required"))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(_("Project {0} not found").format(project))

    start_i = _coerce_int(start, 0, "start")
    limit_i = _coerce_int(limit, 25, "limit")
    if start_i < 0:
        start_i = 0
    if limit_i <= 0 or limit_i > 500:
        limit_i = 25

    # Build WHERE clause incrementally with parameterized inputs.
    where = ["a.project = %(project)s"]
    params: dict[str, Any] = {"project": project}

    if search:
        s = f"%{search.strip().lower()}%"
        where.append(
            "(LOWER(COALESCE(u.full_name, '')) LIKE %(search)s "
            "OR LOWER(COALESCE(u.email, '')) LIKE %(search)s "
            "OR LOWER(COALESCE(a.position_title, '')) LIKE %(search)s)"
        )
        params["search"] = s

    if level_type:
        where.append("ar.administrative_level = %(level_type)s")
        params["level_type"] = level_type

    if role:
        where.append("a.role = %(role)s")
        params["role"] = role

    if status:
        where.append("a.activation_status = %(status)s")
        params["status"] = status

    where_sql = " AND ".join(where)
    join_sql = (
        "FROM `tabGRM User Project Assignment` a "
        "LEFT JOIN `tabUser` u ON u.name = a.user "
        "LEFT JOIN `tabGRM Project Role` r ON r.name = a.role "
        "LEFT JOIN `tabGRM Administrative Region` ar ON ar.name = a.administrative_region "
        "LEFT JOIN `tabGRM Administrative Level Type` lt ON lt.name = ar.administrative_level "
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            a.name, a.user, a.role, a.administrative_region, a.department,
            a.position_title, a.activation_status, a.is_active,
            u.full_name AS user_full_name, u.email AS user_email,
            r.role_name, r.admin_level AS role_admin_level,
            ar.region_name, ar.administrative_level,
            lt.level_name
        {join_sql}
        WHERE {where_sql}
        ORDER BY u.full_name ASC, a.name ASC
        LIMIT %(limit)s OFFSET %(start)s
        """,
        {**params, "limit": limit_i, "start": start_i},
        as_dict=True,
    )

    total_row = frappe.db.sql(
        f"SELECT COUNT(*) AS n {join_sql} WHERE {where_sql}",
        params,
        as_dict=True,
    )
    total = int(total_row[0]["n"]) if total_row else 0

    return {
        "rows": rows,
        "total": total,
        "summary": _summary_counts(project),
    }


@frappe.whitelist()
def update_assignment_field(name: str, fieldname: str, value: Any) -> dict:
    """Update a single field on a single assignment row.

    Validates ``fieldname`` against ``_ASSIGNMENT_INLINE_EDIT_FIELDS``;
    other fields would let a caller corrupt the row (e.g. flipping
    ``user`` to a different account) so they're hard-rejected.

    For ``activation_status``, the value is checked against the Select
    option list on the doctype to prevent free-form strings sneaking in.

    Returns ``{"ok": True, "name", "fieldname", "value"}``.
    """
    _require_wizard_role()
    name = (name or "").strip()
    fieldname = (fieldname or "").strip()
    if not name:
        frappe.throw(_("name is required"))
    if not fieldname:
        frappe.throw(_("fieldname is required"))
    if fieldname not in _ASSIGNMENT_INLINE_EDIT_FIELDS:
        frappe.throw(_("Field {0} is not editable inline").format(fieldname))

    # Scope: caller must hold Supervise duty on the assignment's project.
    # Prevents cross-project tampering where a Project A admin passes a
    # Project B assignment name.
    assert_assignment_admin(name)

    # Empty-string Link clears go to None so Frappe stores NULL rather
    # than the literal "" (which would fail Link validation later).
    if isinstance(value, str) and value.strip() == "":
        coerced: Any = None
    else:
        coerced = value

    if fieldname == "activation_status" and coerced is not None:
        if str(coerced) not in _ASSIGNMENT_STATUS_VALUES:
            frappe.throw(_("Invalid activation_status value: {0}").format(coerced))

    if fieldname == "is_active" and coerced is not None:
        # Accept truthy/falsy strings too (RPC form-encoding sends "0"/"1").
        if isinstance(coerced, str):
            coerced = 1 if coerced.strip() in {"1", "true", "yes", "on"} else 0
        else:
            coerced = 1 if int(coerced) else 0

    doc = frappe.get_doc("GRM User Project Assignment", name)
    setattr(doc, fieldname, coerced)
    doc.save(ignore_permissions=False)
    logger.info(
        "update_assignment_field: %s.%s=%r (assignment=%s)",
        doc.doctype, fieldname, coerced, name,
    )
    return {"ok": True, "name": name, "fieldname": fieldname, "value": coerced}


def _per_row_savepoint(label: str):
    """Context manager: run a block under a SQL savepoint so a failure
    rolls back ONLY that row's writes — not the whole bulk transaction.

    Plain ``frappe.db.rollback()`` is destructive (it nukes earlier
    successful writes in the same request); savepoints scope the
    rollback to the single row, matching the documented contract that
    bulk endpoints accumulate per-row errors without aborting.
    """
    return frappe.db.savepoint(label)


@frappe.whitelist()
def bulk_update_assignments(
    names: list | str, fieldname: str, value: Any,
) -> dict:
    """Apply ``update_assignment_field`` to many rows; accumulate per-row errors.

    Returns ``{"updated": int, "errors": [{"name", "error"}]}`` so the UI
    can show a per-row failure list rather than aborting on the first
    bad row. Each row runs inside its own savepoint so a failure
    rolls back ONLY that row, not the whole transaction.
    """
    _require_wizard_role()
    # Lazy import: avoids a circular dep with the data_import sibling
    # module that hosts ``_coerce_list``.
    from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import import (
        _coerce_list,
    )
    names_list = _coerce_list(names, "names")
    updated = 0
    errors: list[dict[str, str]] = []
    for idx, name in enumerate(names_list):
        sp = f"bulk_update_{idx}"
        try:
            frappe.db.savepoint(sp)
        except Exception:
            # Older Frappe builds may not expose savepoint(); fall back
            # to a non-savepoint loop. The cost is correctness on
            # mid-batch failures, which is documented in the docstring.
            sp = None
        try:
            # update_assignment_field also enforces this, but we keep the
            # call explicit here so bulk_update surfaces a per-row
            # permission error rather than aborting on the first throw.
            assert_assignment_admin(name)
            update_assignment_field(name, fieldname, value)
            updated += 1
        except Exception as exc:  # noqa: BLE001 — per-row error capture
            errors.append({"name": str(name), "error": str(exc)})
            if sp:
                try:
                    frappe.db.rollback(save_point=sp)
                except Exception:
                    # Best-effort: a missing savepoint shouldn't crash
                    # the rest of the batch.
                    pass
    return {"updated": updated, "errors": errors}


@frappe.whitelist()
def bulk_remove_assignments(names: list | str) -> dict:
    """Delete many assignments, accumulating per-row errors.

    Uses ``ignore_missing=True`` so a stale UI list (where the row was
    already deleted by another tab) doesn't throw — that case is
    surfaced as an idempotent "removed" without an error.

    Returns ``{"removed": int, "errors": [{"name", "error"}]}``.
    """
    _require_wizard_role()
    from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import import (
        _coerce_list,
    )
    names_list = _coerce_list(names, "names")
    removed = 0
    errors: list[dict[str, str]] = []
    for idx, name in enumerate(names_list):
        sp = f"bulk_remove_{idx}"
        try:
            frappe.db.savepoint(sp)
        except Exception:
            sp = None
        try:
            # Scope check per row. Skip the assertion if the row was
            # already removed (ignore_missing semantics).
            if frappe.db.exists("GRM User Project Assignment", name):
                assert_assignment_admin(name)
            frappe.delete_doc(
                "GRM User Project Assignment", name,
                ignore_missing=True, ignore_permissions=False,
            )
            removed += 1
        except Exception as exc:  # noqa: BLE001 — per-row error capture
            errors.append({"name": str(name), "error": str(exc)})
            if sp:
                try:
                    frappe.db.rollback(save_point=sp)
                except Exception:
                    pass
    return {"removed": removed, "errors": errors}
