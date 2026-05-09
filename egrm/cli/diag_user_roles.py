"""Diagnostic: print Frappe roles + project assignments for AQE actors."""
import frappe


def run():
    for user in (
        "grm-officer@egrm.test",
        "field-officer@egrm.test",
        "triage-officer@egrm.test",
        "resolver@egrm.test",
        "grm-dept@egrm.test",
        "project-admin@egrm.test",
    ):
        print(f"\n=== {user} ===")
        if not frappe.db.exists("User", user):
            print("  (not provisioned)")
            continue
        roles = frappe.get_roles(user)
        print(f"  Frappe roles: {roles}")
        rows = frappe.get_all(
            "GRM User Project Assignment",
            filters={"user": user, "is_active": 1},
            fields=["project", "administrative_region", "role"],
            order_by="project",
        )
        print(f"  Project assignments ({len(rows)}):")
        for r in rows:
            role_meta = frappe.db.get_value(
                "GRM Project Role", r["role"],
                ["role_name"], as_dict=True,
            )
            duties = frappe.get_all(
                "GRM Project Role Duty",
                filters={"parent": r["role"]},
                fields=["duty"],
            )
            duty_list = sorted(d["duty"] for d in duties)
            print(
                f"    - {r['project']} | region={r['administrative_region']} "
                f"| role={role_meta} | duties={duty_list}"
            )
