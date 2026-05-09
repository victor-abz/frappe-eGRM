"""Diagnostic: are there duplicate (project, region_name, level) regions?

Run with::

    bench --site egrm.local execute egrm.cli.diag_dups.run
"""
import frappe


def run():
    rows = frappe.db.sql(
        """
        SELECT project, region_name, administrative_level,
               COUNT(*) as cnt,
               GROUP_CONCAT(name ORDER BY creation) as ids,
               GROUP_CONCAT(creation ORDER BY creation) as creations
        FROM `tabGRM Administrative Region`
        WHERE project = 'RW-WB'
        GROUP BY project, region_name, administrative_level
        HAVING cnt > 1
        ORDER BY cnt DESC, region_name
        """,
        as_dict=True,
    )
    print(f"=== {len(rows)} duplicate region groups in RW-WB ===")
    for r in rows[:20]:
        print(
            f"  region={r['region_name']!r} level={r['administrative_level']} "
            f"cnt={r['cnt']} ids={r['ids']} creations={r['creations']}"
        )

    # Also check level types
    rows = frappe.db.sql(
        """
        SELECT project, level_name, COUNT(*) as cnt,
               GROUP_CONCAT(name ORDER BY creation) as ids
        FROM `tabGRM Administrative Level Type`
        WHERE project = 'RW-WB'
        GROUP BY project, level_name
        HAVING cnt > 1
        """,
        as_dict=True,
    )
    print(f"\n=== {len(rows)} duplicate level types in RW-WB ===")
    for r in rows:
        print(f"  level={r['level_name']!r} cnt={r['cnt']} ids={r['ids']}")

    # And the canonical Rwanda root for the user's assignment
    rwanda_rows = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": "RW-WB", "region_name": "Rwanda"},
        fields=["name", "administrative_level", "parent_region", "creation"],
        order_by="creation",
    )
    print(f"\n=== {len(rwanda_rows)} Rwanda region rows ===")
    for r in rwanda_rows:
        print(f"  {r}")

    # And how many children does each Rwanda root have (transitively)?
    for r in rwanda_rows:
        # count all regions whose chain ascends to this root
        all_rw = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": "RW-WB"},
            fields=["name", "parent_region"],
        )
        m = {x["name"]: x["parent_region"] for x in all_rw}
        descendants = 0
        for child, _parent in m.items():
            cur = child
            while cur in m and m[cur]:
                cur = m[cur]
            if cur == r["name"]:
                descendants += 1
        print(f"  Rwanda {r['name']!r}: {descendants} regions in its tree")
