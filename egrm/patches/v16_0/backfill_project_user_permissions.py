"""Backfill User Permission rows for every active GRM User Project Assignment.

Idempotent — safe to re-run on already-upgraded sites because
sync_assignment is idempotent.
"""

import frappe

from egrm.utils.user_permissions import sync_assignment


def execute() -> None:
    names = frappe.get_all(
        "GRM User Project Assignment",
        filters={"is_active": 1},
        pluck="name",
    )
    print(f"Backfilling User Permission for {len(names)} assignment(s)...")
    for name in names:
        try:
            sync_assignment(frappe.get_doc("GRM User Project Assignment", name))
        except Exception as exc:
            frappe.log_error(title="UP backfill failed", message=f"{name}: {exc}")
