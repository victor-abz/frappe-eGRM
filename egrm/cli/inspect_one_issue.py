"""Inspect a freshly-submitted GRM Issue's routing decision.

Prints assignee, reason, category, region, project — and resolves the
expected user pool at that region+role so we can confirm the live pick
was inside the eligible set.

Run::

    bench --site egrm.local execute egrm.cli.inspect_one_issue.main \
        --kwargs '{"issue": "qlqc63bjfs"}'
"""
from __future__ import annotations
import frappe


def main(issue: str) -> None:
    iss = frappe.get_doc("GRM Issue", issue)
    print(f"\n=== GRM Issue {iss.name} ===")
    print(f"  project       : {iss.project}")
    print(f"  category      : {iss.category}")
    print(f"  region        : {iss.administrative_region}")
    print(f"  reporter      : {iss.reporter}")
    print(f"  status        : {iss.status}")
    print(f"  assignee      : {iss.assignee!r}")
    print(f"  routing_reason: {getattr(iss, 'routing_reason', None)!r}")
    print(f"  tracking_code : {iss.tracking_code}")
    print(f"  created       : {iss.creation}")

    # Look up category routing target.
    cat = frappe.get_doc("GRM Issue Category", iss.category)
    print(f"\n=== Category {cat.name} ===")
    print(f"  label                 : {cat.label}")
    print(f"  routing_target_type   : {getattr(cat, 'routing_target_type', None)!r}")
    print(f"  assigned_role         : {getattr(cat, 'assigned_role', None)!r}")
    print(f"  assigned_department   : {getattr(cat, 'assigned_department', None)!r}")

    # Region chain.
    chain = []
    cur = iss.administrative_region
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        r = frappe.db.get_value(
            "GRM Administrative Region", cur,
            ["name", "region_name", "parent_region"], as_dict=True
        )
        if not r: break
        chain.append(r)
        cur = r.parent_region
    print(f"\n=== Region chain (leaf→root) ===")
    for r in chain:
        print(f"  - {r.name}  {r.region_name!r}")

    # Eligible users at this category+region chain.
    role = getattr(cat, "assigned_role", None)
    if role:
        print(f"\n=== Eligible users at role={role!r} along chain ===")
        from egrm.services.assignee_routing import ACTIVE_STATUSES, RESOLVE_DUTY
        for r in chain:
            users = frappe.db.sql("""
                SELECT DISTINCT a.user
                FROM `tabGRM User Project Assignment` a
                JOIN `tabGRM Project Role Duty` prd ON prd.parent = a.role
                WHERE a.project=%s AND a.role=%s AND a.administrative_region=%s
                  AND a.is_active=1 AND a.activation_status IN %s
                  AND prd.duty=%s
                ORDER BY a.user
            """, (iss.project, role, r.name, ACTIVE_STATUSES, RESOLVE_DUTY), as_dict=True)
            users = [u.user for u in users]
            marker = " ← assignee here" if iss.assignee in users else ""
            print(f"  {r.region_name:30} ({r.name}): {users}{marker}")

    # Final verdict.
    print()
    if iss.assignee:
        print(f"[OK] assignee resolved: {iss.assignee} (reason: {getattr(iss, 'routing_reason', None)})")
    else:
        print(f"[WARN] assignee not set; reason: {getattr(iss, 'routing_reason', None)}")
