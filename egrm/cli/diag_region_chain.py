"""Diagnostic: walk parent chain for a region, print tree."""
import frappe


def run(region_id="edr142fr5f"):
    print(f"=== Walking parent chain from {region_id} ===")
    cur = region_id
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        meta = frappe.db.get_value(
            "GRM Administrative Region",
            cur,
            ["name", "region_name", "administrative_level", "parent_region", "creation"],
            as_dict=True,
        )
        if not meta:
            print(f"  {cur} -> NOT FOUND")
            break
        print(f"  {meta}")
        cur = meta.get("parent_region")

    # Compare with grm-officer's accessible regions set
    from egrm.api.lookup import get_user_accessible_regions, get_user_region_assignments

    user = "grm-officer@egrm.test"
    asn = get_user_region_assignments(user)
    print(f"\n=== {user} assignments: {len(asn)} ===")
    for a in asn:
        meta = frappe.db.get_value(
            "GRM Administrative Region",
            a.administrative_region,
            ["region_name", "administrative_level", "parent_region"],
            as_dict=True,
        )
        print(f"  {a.administrative_region} | {meta}")

    accessible = get_user_accessible_regions(asn) or []
    ids = sorted({a.get("name") or a.get("id") for a in accessible})
    print(f"\nAccessible regions: {len(ids)}")
    print(f"region {region_id} in accessible? {region_id in ids}")

    # Also: find the actual GRM Issue.administrative_region used by the
    # latest seeded issue
    rows = frappe.db.sql(
        """
        SELECT name, administrative_region, project, creation
        FROM `tabGRM Issue`
        WHERE owner=%s
        ORDER BY creation DESC
        LIMIT 5
        """,
        (user,), as_dict=True,
    )
    print(f"\n=== Recent issues by {user} ===")
    for r in rows:
        print(f"  {r}")
