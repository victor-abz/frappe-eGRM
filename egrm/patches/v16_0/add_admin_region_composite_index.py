# Copyright (c) 2026, eGRM and contributors
# For license information, please see license.txt
"""Add composite index (project, parent_region) on tabGRM Administrative Region.

Bulk seeded eGRM tenants observe sub-200ms p95 budgets on the
"children-under-cell" lookup pattern that powers village hydration on the
mobile app. With ~5k regions per project the
``WHERE project=? AND parent_region=? ORDER BY region_name`` query falls back
to a full table scan + filesort. A leading composite index on
``(project, parent_region)`` pushes the query plan to a covering index range
scan and eliminates the filesort for the typical sort-by-name case.

Idempotent: bench migrate and ``frappe.db.add_index`` will silently no-op if
the index already exists.
"""

import frappe


def execute():  # type: ignore[no-untyped-def]
    table = "tabGRM Administrative Region"

    # Frappe's helper picks the next available index_<N> name when the columns
    # do not already match an existing index.
    try:
        frappe.db.add_index(
            "GRM Administrative Region",
            ["project", "parent_region"],
            index_name="idx_grm_admin_region_project_parent",
        )
    except Exception as exc:  # pragma: no cover - defensive
        frappe.logger().warning(
            f"add_admin_region_composite_index: skipped ({exc})"
        )
        return

    frappe.db.commit()
