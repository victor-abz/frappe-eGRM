"""Repoint each GRM User Project Assignment.role from a Frappe Role string
(e.g. 'GRM Field Officer') to the corresponding GRM Project Role
('<project>-GRM Field Officer'). Run AFTER backfill_default_project_roles."""

import frappe


LEGACY: set[str] = {
    "GRM Administrator", "GRM Project Manager", "GRM Department Head", "GRM Field Officer",
}


def execute() -> None:
    rows = frappe.db.sql(
        "SELECT name, project, role FROM `tabGRM User Project Assignment`",
        as_dict=True,
    )
    print(f"Migrating role values on {len(rows)} assignment(s)...")
    for r in rows:
        legacy = r.get("role") or ""
        if legacy not in LEGACY:
            continue  # already migrated, blank, or unrecognised — skip
        target = f"{r['project']}-{legacy}"
        if not frappe.db.exists("GRM Project Role", target):
            frappe.log_error(
                title="Project Role missing during migration",
                message=f"Assignment {r['name']}: expected {target}",
            )
            continue
        frappe.db.set_value(
            "GRM User Project Assignment", r["name"], "role", target,
            update_modified=False,
        )
