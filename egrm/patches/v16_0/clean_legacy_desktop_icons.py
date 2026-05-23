"""Clean leftover Desktop Icon rows from the legacy role-based workspaces.

Frappe's `Desktop Icon` table predates Workspaces but Frappe still uses it
to render the central "app picker" modal at /desk. When a public Workspace
is deleted, `Workspace.on_trash` calls `delete_doc_if_exists("Desktop Icon",
self.title)` — but earlier patches that removed the legacy role-named
workspaces (`delete_legacy_workspaces`) ran with `force=True`, which
bypassed that hook on already-migrated sites. Result: the parent EGRM
desktop icon still shows four orphan child tiles ("GRM Administrator",
"GRM Department Head", "GRM Field Officer", "GRM Project Manager") and
its own `link` points to `/desk/grm-field-officer` instead of `/desk/egrm`.

This patch:
  1. Deletes the four orphan child Desktop Icons.
  2. Repoints the EGRM parent icon's `link` to `/desk/egrm`.
"""

import frappe


LEGACY_CHILD_ICONS = (
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
)


def execute() -> None:
    for child in LEGACY_CHILD_ICONS:
        if frappe.db.exists("Desktop Icon", child):
            frappe.delete_doc(
                "Desktop Icon", child, ignore_permissions=True, force=True
            )
            print(f"Deleted legacy Desktop Icon: {child}")

    if frappe.db.exists("Desktop Icon", "EGRM"):
        frappe.db.set_value(
            "Desktop Icon",
            "EGRM",
            {"link": "/desk/egrm", "parent_icon": None, "hidden": 0},
        )
        print("Repointed EGRM Desktop Icon -> /desk/egrm")

    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.db.commit()
