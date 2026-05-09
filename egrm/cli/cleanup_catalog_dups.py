"""One-shot cleanup: collapse duplicate catalog rows that lack DB unique indices.

Each (project, <natural-key>) pair below is collapsed:
  - GRM Issue Category    keyed (project, category_name)
  - GRM Issue Type        keyed (project, type_name)
  - GRM Issue Status      keyed (project, status_name)  *(via project link table)*
  - GRM Issue Department  keyed (department_name)        *(global)*
  - GRM Issue Age Group   keyed (project, age_group)
  - GRM Issue Citizen Group keyed (project, group_name)
  - GRM Administrative Level Type keyed (project, level_name)

For each duplicate group:
  - keep the OLDEST row
  - re-point any GRM Issue.<fk_field> that points at a dup to the survivor
  - delete the dup

Run::

    bench --site egrm.local execute egrm.cli.cleanup_catalog_dups.run
"""
import frappe


def _replace_fk(doctype: str, field: str, old: str, new: str) -> int:
    frappe.db.sql(
        f"""UPDATE `tab{doctype}` SET {field}=%s WHERE {field}=%s""",
        (new, old),
    )
    return frappe.db.sql("SELECT ROW_COUNT()")[0][0]


def _dedupe(doctype: str, key_fields: list[str], issue_fk: str | None) -> dict:
    """Collapse duplicate rows of ``doctype`` keyed on ``key_fields``."""
    cols = ", ".join(f"`{f}`" for f in key_fields)
    rows = frappe.db.sql(
        f"""
        SELECT {cols}, COUNT(*) as cnt,
               GROUP_CONCAT(name ORDER BY creation) as ids
        FROM `tab{doctype}`
        GROUP BY {cols}
        HAVING cnt > 1
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )
    deleted = 0
    issue_repointed = 0
    for r in rows:
        ids = r["ids"].split(",")
        keep, *dups = ids
        for dup in dups:
            if issue_fk:
                issue_repointed += _replace_fk(
                    "GRM Issue", issue_fk, dup, keep,
                )
            frappe.db.sql(
                f"""DELETE FROM `tab{doctype}` WHERE name=%s""", (dup,),
            )
            deleted += 1
    return {"groups": len(rows), "deleted": deleted, "issue_repointed": issue_repointed}


def run():
    plan = [
        ("GRM Administrative Level Type", ["project", "level_name"], None),
        ("GRM Issue Category", ["project", "category_name"], "category"),
        ("GRM Issue Type", ["project", "type_name"], "issue_type"),
        ("GRM Issue Department", ["project", "department_name"], None),
        ("GRM Issue Age Group", ["project", "age_group"], None),
        ("GRM Issue Citizen Group", ["project", "group_name"], None),
    ]
    for doctype, keys, issue_fk in plan:
        # Only proceed if all key fields exist on the doctype's columns.
        try:
            stats = _dedupe(doctype, keys, issue_fk)
        except Exception as exc:
            print(f"  {doctype}: skipped — {exc}")
            continue
        print(f"  {doctype}: {stats}")

    # GRM Issue Status keys (status_name) but project linkage lives in the
    # child table `GRM Project Link`. We dedupe by status_name + the first
    # linked project per row.
    rows = frappe.db.sql(
        """
        SELECT s.name AS status_name_id, s.status_name,
               (SELECT pl.project FROM `tabGRM Project Link` pl
                WHERE pl.parent=s.name AND pl.parenttype='GRM Issue Status'
                LIMIT 1) AS proj
        FROM `tabGRM Issue Status` s
        ORDER BY s.creation
        """,
        as_dict=True,
    )
    by_key: dict[tuple, list] = {}
    for r in rows:
        key = (r.get("proj"), r.get("status_name"))
        by_key.setdefault(key, []).append(r["status_name_id"])
    deleted = 0
    issue_repointed = 0
    for key, names in by_key.items():
        if len(names) <= 1:
            continue
        keep, *dups = names
        for dup in dups:
            issue_repointed += _replace_fk("GRM Issue", "status", dup, keep)
            # remove the project link rows
            frappe.db.sql(
                """DELETE FROM `tabGRM Project Link` WHERE parent=%s""", (dup,),
            )
            frappe.db.sql(
                """DELETE FROM `tabGRM Issue Status` WHERE name=%s""", (dup,),
            )
            deleted += 1
    print(
        f"  GRM Issue Status: deleted={deleted} issue_repointed={issue_repointed}"
    )

    frappe.db.commit()
    print("done.")
