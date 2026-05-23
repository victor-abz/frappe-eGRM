"""Drop the standalone Platform workspace.

Phase 2 originally shipped one duty-driven `eGRM` workspace plus a
separate `Platform` workspace for System Manager + GRM Platform
Administrator. Per the post-Phase-2 UX directive, all users (including
platform admins) now land on `eGRM`, with the previously platform-only
sections (Projects / Users & Access / System) appended to the eGRM
workspace itself and gated by `frappe.boot.egrm.is_platform_admin`.

This patch removes the orphaned Platform workspace from the DB. The
JSON file has been deleted in the same change-set, so Frappe's
`Removing orphan Workspaces` step would normally drop it on
`bench migrate`; we run an explicit delete here to keep the migration
deterministic on already-migrated sites.
"""

import frappe


def execute() -> None:
    if frappe.db.exists("Workspace", "Platform"):
        frappe.delete_doc("Workspace", "Platform", ignore_permissions=True, force=True)
        print("Deleted standalone Workspace: Platform")
    frappe.db.commit()
