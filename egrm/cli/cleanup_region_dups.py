"""One-shot cleanup: collapse duplicate (project, region_name, level) regions.

Strategy:
- For each duplicate group keyed (project, region_name, administrative_level):
  - keep the OLDEST row (by creation)
  - re-point any GRM Administrative Region rows whose parent_region is one of
    the dup names to the survivor
  - re-point any GRM Issue.administrative_region pointing at a dup to the
    survivor
  - re-point any GRM User Project Assignment.administrative_region pointing
    at a dup to the survivor
  - delete the dup row (ignore_permissions=True)

Run with::

    bench --site egrm.local execute egrm.cli.cleanup_region_dups.run
"""
import frappe


def _replace_fk(doctype: str, field: str, old: str, new: str) -> int:
    n = frappe.db.sql(
        f"""UPDATE `tab{doctype}` SET {field}=%s WHERE {field}=%s""",
        (new, old),
    )
    return frappe.db.sql(
        f"""SELECT ROW_COUNT()""",
    )[0][0]


def run():
    rows = frappe.db.sql(
        """
        SELECT project, region_name, administrative_level,
               COUNT(*) as cnt,
               GROUP_CONCAT(name ORDER BY creation) as ids
        FROM `tabGRM Administrative Region`
        GROUP BY project, region_name, administrative_level
        HAVING cnt > 1
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )
    print(f"Found {len(rows)} duplicate groups across all projects")

    deleted = 0
    parent_repointed = 0
    issue_repointed = 0
    asn_repointed = 0

    for r in rows:
        ids = r["ids"].split(",")
        keep, *dups = ids
        for dup in dups:
            # Repoint children: any region whose parent_region == dup
            ch = _replace_fk(
                "GRM Administrative Region", "parent_region", dup, keep
            )
            parent_repointed += ch

            # Repoint issues
            iss = _replace_fk(
                "GRM Issue", "administrative_region", dup, keep
            )
            issue_repointed += iss

            # Repoint user assignments
            asn = _replace_fk(
                "GRM User Project Assignment", "administrative_region",
                dup, keep,
            )
            asn_repointed += asn

            # Now delete the dup region row directly via DB to avoid hooks
            frappe.db.sql(
                """DELETE FROM `tabGRM Administrative Region` WHERE name=%s""",
                (dup,),
            )
            deleted += 1

    frappe.db.commit()
    print(
        f"deleted={deleted} | "
        f"parent_repointed={parent_repointed} | "
        f"issue_repointed={issue_repointed} | "
        f"assignment_repointed={asn_repointed}"
    )

    # Verification
    remaining = frappe.db.sql(
        """
        SELECT COUNT(*) FROM (
            SELECT project, region_name, administrative_level
            FROM `tabGRM Administrative Region`
            GROUP BY project, region_name, administrative_level
            HAVING COUNT(*) > 1
        ) AS dups
        """
    )[0][0]
    print(f"remaining duplicate groups: {remaining}")
