"""Grant `read` on the Frappe `Page` DocType to platform-admin GRM roles.

Custom desk pages (e.g. ``grm-project-wizard``, ``grm-users``) declare
their accessing roles in their own page JSON, but Frappe **additionally**
gates page rendering on the calling user holding ``read`` on the
**Page DocType itself**. By default that's locked to System Manager.

The canonical AQE actor ``project-admin@egrm.test`` only holds
``GRM Platform Administrator`` + ``GRM Supervise``; without this patch
they hit the *"User project-admin@egrm.test does not have doctype access
via role permission for document Page"* dialog on every custom desk page
they try to open — which renders both the project-setup wizard and the
users-by-project page unusable for the principal who is supposed to own
them.

This patch is idempotent: it only inserts a Custom DocPerm row when one
isn't already present for `(parent='Page', role=<role>, permlevel=0)`.
"""
import frappe


PLATFORM_ROLES = (
    "GRM Platform Administrator",
    "GRM Supervise",
    "GRM Administrator",
)
TARGET_DOCTYPE = "Page"


def execute() -> None:
    granted: list[str] = []
    skipped: list[str] = []

    for role in PLATFORM_ROLES:
        if not frappe.db.exists("Role", role):
            skipped.append(f"{role} (role missing)")
            continue

        existing = frappe.db.get_value(
            "Custom DocPerm",
            {
                "parent": TARGET_DOCTYPE,
                "role": role,
                "permlevel": 0,
            },
            "name",
        )
        if existing:
            skipped.append(f"{role} (already granted: {existing})")
            continue

        perm = frappe.new_doc("Custom DocPerm")
        perm.parent = TARGET_DOCTYPE
        perm.parenttype = "DocType"
        perm.parentfield = "permissions"
        perm.role = role
        perm.permlevel = 0
        perm.read = 1
        # Strictly read-only — desk-page CRUD is a System Manager
        # responsibility, not a platform-admin one.
        perm.write = 0
        perm.create = 0
        perm.delete = 0
        perm.report = 0
        perm.export = 0
        perm.share = 0
        perm.flags.ignore_permissions = True
        perm.insert()
        granted.append(role)

    if granted:
        frappe.clear_cache(doctype=TARGET_DOCTYPE)
        frappe.db.commit()

    print(
        f"[grant_page_read_to_platform_admin] granted={granted} "
        f"skipped={skipped}"
    )
