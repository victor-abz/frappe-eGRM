"""Grant `read` on the Frappe `Role` DocType to GRM Platform Administrator.

The AC-2 contract test (ARCH-CONTRACT) calls
`frappe.client.get_list` with doctype="Role" filtered by `role_name LIKE
'GRM%'` to assert that the canonical 7-role catalogue is in place. By
default Frappe locks `Role` down to System Manager, which means the
project-admin actor (who only holds `GRM Platform Administrator` +
`GRM Supervise`) cannot list roles, even though they are the principal
who manages duty-role assignments.

This patch adds an idempotent Custom DocPerm for the platform admin so
that they can read (but NOT create / write / delete) `Role` rows.

The permission is the minimum required for the AC-2 catalogue check and
for any future "list all roles" UI on the platform workspace.
"""
import frappe


PLATFORM_ADMIN_ROLE = "GRM Platform Administrator"
TARGET_DOCTYPE = "Role"


def execute():
    if not frappe.db.exists("Role", PLATFORM_ADMIN_ROLE):
        # `seed_grm_role_catalog` should have run first; if not, the
        # next patch will fix this. Skip silently.
        print(f"[grant_role_read_to_platform_admin] {PLATFORM_ADMIN_ROLE} "
              "missing — skip")
        return

    existing = frappe.db.get_value(
        "Custom DocPerm",
        {
            "parent": TARGET_DOCTYPE,
            "role": PLATFORM_ADMIN_ROLE,
            "permlevel": 0,
        },
        "name",
    )
    if existing:
        print(f"[grant_role_read_to_platform_admin] already granted "
              f"({existing}) — skip")
        return

    perm = frappe.new_doc("Custom DocPerm")
    perm.parent = TARGET_DOCTYPE
    perm.parenttype = "DocType"
    perm.parentfield = "permissions"
    perm.role = PLATFORM_ADMIN_ROLE
    perm.permlevel = 0
    perm.read = 1
    # Strictly read-only — platform admins manage duty roles via the
    # GRM Project Role doctype, NOT by mutating the global Role catalog.
    perm.write = 0
    perm.create = 0
    perm.delete = 0
    perm.report = 1
    perm.export = 0
    perm.share = 0
    perm.flags.ignore_permissions = True
    perm.insert()

    # Force a reload so the permissions cache picks up the new row.
    frappe.clear_cache(doctype=TARGET_DOCTYPE)
    frappe.db.commit()

    print(f"[grant_role_read_to_platform_admin] granted read on "
          f"{TARGET_DOCTYPE} to {PLATFORM_ADMIN_ROLE}")
