"""List users with the Review duty for a project.

Used to confirm there is someone who can drive the triage Accept step
during the live-browser routing tests.
"""
from __future__ import annotations

import frappe


def review_duty_holders(project: str = "RDAP") -> None:
    rows = frappe.db.sql(
        """
        SELECT a.user, r.role_name, a.administrative_region,
               reg.region_name, a.is_active, a.activation_status
        FROM `tabGRM User Project Assignment` a
        JOIN `tabGRM Project Role` r ON r.name = a.role
        JOIN `tabGRM Project Role Duty` prd ON prd.parent = a.role
        LEFT JOIN `tabGRM Administrative Region` reg
             ON reg.name = a.administrative_region
        WHERE a.project = %s AND prd.duty = 'Review'
        ORDER BY reg.region_name, a.user
        """,
        (project,),
        as_dict=True,
    )
    print(f"Review-duty holders for {project}:")
    if not rows:
        print("  (none)")
        return
    for r in rows:
        print(" ", r)


def all_duties_for_user(user: str, project: str) -> None:
    rows = frappe.db.sql(
        """
        SELECT a.role, r.role_name, GROUP_CONCAT(prd.duty) duties,
               a.administrative_region, reg.region_name,
               a.is_active, a.activation_status
        FROM `tabGRM User Project Assignment` a
        JOIN `tabGRM Project Role` r ON r.name = a.role
        LEFT JOIN `tabGRM Project Role Duty` prd ON prd.parent = a.role
        LEFT JOIN `tabGRM Administrative Region` reg
             ON reg.name = a.administrative_region
        WHERE a.user = %s AND a.project = %s
        GROUP BY a.name
        """,
        (user, project),
        as_dict=True,
    )
    print(f"All assignments for {user} in {project}:")
    for r in rows:
        print(" ", r)
