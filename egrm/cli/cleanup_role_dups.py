"""One-shot cleanup: collapse duplicate (project, role_name) GRM Project Role rows.

Run with::

    bench --site egrm.local execute egrm.cli.cleanup_role_dups.run
"""
import frappe


def _replace_fk_with_count(doctype: str, field: str, old: str, new: str) -> int:
    frappe.db.sql(
        f"""UPDATE `tab{doctype}` SET {field}=%s WHERE {field}=%s""",
        (new, old),
    )
    return frappe.db.sql("""SELECT ROW_COUNT()""")[0][0]


def run():
    rows = frappe.db.sql(
        """
        SELECT project, role_name, COUNT(*) as cnt,
               GROUP_CONCAT(name ORDER BY creation) as ids
        FROM `tabGRM Project Role`
        GROUP BY project, role_name
        HAVING cnt > 1
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )
    print(f"Found {len(rows)} duplicate role groups")

    deleted = 0
    asn_repointed = 0
    duty_repointed = 0

    for r in rows:
        ids = r["ids"].split(",")
        keep, *dups = ids
        for dup in dups:
            # Move user assignments to the kept role
            asn = _replace_fk_with_count(
                "GRM User Project Assignment", "role", dup, keep,
            )
            asn_repointed += asn

            # Move duty rows (parent=dup -> parent=keep) — but if keep already
            # has duties, we'd duplicate. Instead, just delete the dup duty rows.
            n = frappe.db.sql(
                """DELETE FROM `tabGRM Project Role Duty` WHERE parent=%s""",
                (dup,),
            )
            duty_repointed += frappe.db.sql("SELECT ROW_COUNT()")[0][0]

            # Delete the duplicate role
            frappe.db.sql(
                """DELETE FROM `tabGRM Project Role` WHERE name=%s""",
                (dup,),
            )
            deleted += 1

    frappe.db.commit()
    print(
        f"deleted={deleted} | assignment_repointed={asn_repointed} | "
        f"duty_rows_dropped={duty_repointed}"
    )

    remaining = frappe.db.sql(
        """
        SELECT COUNT(*) FROM (
            SELECT project, role_name FROM `tabGRM Project Role`
            GROUP BY project, role_name HAVING COUNT(*) > 1
        ) AS dups
        """,
    )[0][0]
    print(f"remaining duplicate role groups: {remaining}")
