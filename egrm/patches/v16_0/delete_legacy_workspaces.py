"""Drop the four legacy role-based GRM workspaces (replaced by the unified
eGRM workspace + Platform workspace introduced in Phase 2)."""

import frappe


LEGACY_WORKSPACES = [
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
]


def execute() -> None:
    for ws in LEGACY_WORKSPACES:
        if frappe.db.exists("Workspace", ws):
            frappe.delete_doc("Workspace", ws, ignore_permissions=True, force=True)
            print(f"Deleted legacy workspace: {ws}")
    frappe.db.commit()
