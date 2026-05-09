"""Diagnostic: print user assignments + accessible regions for grm-officer.

Run with::

    bench --site egrm.local execute egrm.cli.diag_regions.run
"""
import frappe


def run():
    user = "grm-officer@egrm.test"
    print(f"=== User: {user} ===")
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "is_active": 1},
        fields=[
            "name",
            "project",
            "administrative_region",
            "role",
            "activation_status",
        ],
        order_by="creation",
    )
    print(f"\n{len(rows)} active assignments:")
    for r in rows:
        # resolve administrative_region to (project, region_name, level, parent)
        meta = frappe.db.get_value(
            "GRM Administrative Region",
            r.administrative_region,
            ["project", "region_name", "administrative_level", "parent_region"],
            as_dict=True,
        )
        print(
            f"  - {r.name} | proj={r.project} | region={r.administrative_region} "
            f"| {meta} | role={r.role} | act={r.activation_status}"
        )

    # Accessible regions hierarchy
    from egrm.api.lookup import (
        get_user_accessible_regions,
        get_user_region_assignments,
    )

    asn = get_user_region_assignments(user)
    accessible = get_user_accessible_regions(asn) or []
    ids = sorted({a.get("name") or a.get("id") for a in accessible})
    print(f"\nAccessible regions (via get_user_accessible_regions): {len(ids)}")

    # Cross-check the regions used by the IL/MD test seeds
    print("\n=== Region presence in accessible set ===")
    for region in (
        "3ci0k7lb56",  # IL seed region
        "64bvg7cblj",  # MD-3 deep region (latest run)
        "64ajfh0fh9",  # latest Rwanda root
        "5egtgn1aqh",  # original Rwanda root
        "3f11ptah9u",  # earlier MD-3 region
    ):
        meta = frappe.db.get_value(
            "GRM Administrative Region",
            region,
            ["project", "region_name", "administrative_level", "parent_region"],
            as_dict=True,
        )
        print(
            f"  - {region}: in_accessible={region in ids} | meta={meta}"
        )

    # All RW-WB region roots (no parent)
    print("\n=== All RW-WB regions with parent_region IS NULL ===")
    roots = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": "RW-WB", "parent_region": ["in", [None, ""]]},
        fields=["name", "region_name", "creation"],
        order_by="creation",
    )
    for r in roots:
        print(f"  - {r.name}: {r.region_name} (created {r.creation})")
