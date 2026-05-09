"""Rename existing `GRM Administrative Level Type` records from globally-unique
``<level_name>`` to project-scoped ``<project>-<level_name>``.

Background
==========
The doctype originally used ``autoname: field:level_name`` and a unique
constraint on ``level_name``. That made level names globally unique, which
collides across projects (e.g. two projects both wanting "Province").

The doctype JSON has been updated to ``autoname: format:{project}-{level_name}``
and the unique flag dropped; controller-level uniqueness is now enforced per
``(project, level_name)``.

This patch migrates every legacy row to the new naming scheme using
``frappe.rename_doc(force=True)`` which auto-updates the Link references in:

  - GRM Administrative Region.administrative_level
  - GRM Issue Category.administrative_level
  - GRM Project Role.admin_level

Idempotent: rows whose name already matches ``<project>-<level_name>`` are
skipped. Rows missing a project are left untouched (cleaned up separately by
``egrm.cli.cleanup_rdap.purge_orphan_admin_levels``).
"""

import frappe


def execute() -> None:
    if not frappe.db.exists("DocType", "GRM Administrative Level Type"):
        return

    rows = frappe.get_all(
        "GRM Administrative Level Type",
        fields=["name", "project", "level_name"],
        limit_page_length=0,
    )
    if not rows:
        print("rename_admin_level_types_to_project_scoped: no rows to migrate")
        return

    renamed = 0
    skipped = 0
    orphans = 0
    for r in rows:
        if not r.project or not r.level_name:
            orphans += 1
            continue
        new_name = f"{r.project}-{r.level_name}"
        if r.name == new_name:
            skipped += 1
            continue
        if frappe.db.exists("GRM Administrative Level Type", new_name):
            print(
                f"  WARN target {new_name} already exists; leaving {r.name} untouched"
            )
            skipped += 1
            continue
        try:
            frappe.rename_doc(
                "GRM Administrative Level Type",
                r.name,
                new_name,
                force=True,
                merge=False,
                show_alert=False,
            )
            renamed += 1
        except Exception as e:
            print(f"  skip rename {r.name} -> {new_name}: {e}")
            skipped += 1

    frappe.db.commit()
    print(
        f"rename_admin_level_types_to_project_scoped: renamed={renamed} "
        f"skipped={skipped} orphans={orphans}"
    )
