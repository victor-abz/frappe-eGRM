"""For each active GRM User Project Assignment, grant the corresponding
duty-Frappe-Roles to the user (matching the assignment's Project Role's
duties[] table). Then strip the four legacy Frappe Roles from every user."""

import frappe


LEGACY_ROLES = [
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
]


def execute() -> None:
    names = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        pluck="name",
    )
    print(f"Granting duty-roles for {len(names)} active assignment(s)...")
    for name in names:
        try:
            doc = frappe.get_doc("GRM User Project Assignment", name)
            doc.assign_role_to_user()
        except Exception as exc:
            frappe.log_error(title="duty-role migration failed", message=f"{name}: {exc}")

    print(f"Stripping {len(LEGACY_ROLES)} legacy Frappe Roles from all users...")
    for legacy in LEGACY_ROLES:
        rows = frappe.get_all(
            "Has Role",
            filters={"role": legacy, "parenttype": "User"},
            pluck="name",
        )
        for row_name in rows:
            frappe.db.delete("Has Role", {"name": row_name})
