"""Bulk-activate all Pending Activation assignments for a project via the
wizard's own ``bulk_update_assignments`` endpoint.

This is the same code path the wizard UI uses (Step 9 → Change status →
Activated) — no DB hacks, no side-channels. It exists because Step 9's
Apply button is hard to drive reliably through Playwright when there are
many rows; running the endpoint directly from bench takes seconds.

Run::

    bench --site egrm.local execute egrm.cli.activate_pending_users.main \
        --kwargs '{"project": "RGRP26", "role_label": "Digital Ambassador"}'
"""
from __future__ import annotations

# Module marker: tooling / reviewers can grep for ``__DEV_ONLY__`` to
# distinguish operational diagnostic scripts from production code paths.
__DEV_ONLY__ = True

import frappe


def main(project: str = "RGRP26", role_label: str | None = None) -> None:
    from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_assignments import (
        bulk_update_assignments,
    )

    # Find all Pending Activation rows; optionally filter by role label.
    filters = {
        "project": project,
        "activation_status": "Pending Activation",
        "is_active": 1,
    }
    if role_label:
        role = frappe.db.get_value(
            "GRM Project Role",
            {"project": project, "role_name": role_label},
            "name",
        )
        if not role:
            print(f"[err] role {role_label!r} not found in project {project!r}")
            return
        filters["role"] = role
        print(f"[info] filtering by role {role_label} ({role})")

    names = frappe.db.get_list(
        "GRM User Project Assignment",
        filters=filters,
        pluck="name",
    )
    print(f"[info] {len(names)} pending rows to activate")
    if not names:
        return

    # Run as Administrator so _require_wizard_role passes; the wizard
    # endpoint is the same one the UI hits.
    frappe.set_user("Administrator")
    result = bulk_update_assignments(
        names=names,
        fieldname="activation_status",
        value="Activated",
    )
    frappe.db.commit()
    updated = result.get("updated", 0)
    errors = result.get("errors", [])
    print(f"[done] updated={updated} errors={len(errors)}")
    for e in errors[:10]:
        print(f"   ! {e}")
    if len(errors) > 10:
        print(f"   ... and {len(errors) - 10} more")

    # Re-count by status to confirm.
    by_status = frappe.db.sql(
        """
        SELECT activation_status, COUNT(*) AS n
        FROM `tabGRM User Project Assignment`
        WHERE project=%s AND is_active=1
        GROUP BY activation_status
        ORDER BY activation_status
        """,
        (project,),
        as_dict=True,
    )
    print(f"[verify] activation counts for {project}:")
    for r in by_status:
        print(f"   {r['activation_status']!r:24} {r['n']}")
