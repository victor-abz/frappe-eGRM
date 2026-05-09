"""Hard-delete every artifact tied to a GRM test project.

Run: bench --site egrm.local execute "frappe.get_attr('egrm.cli.cleanup_rdap.purge')()"
For an arbitrary project: bench --site egrm.local execute egrm.cli.cleanup_rdap.purge_project --kwargs '{"project":"GoodLide"}'
For partial RDAP cleanup (still allowed): purge() (defaults to RDAP).
"""
import frappe

PROJECT = "RDAP"


def _drop_filtered(doctype, filter_field):
    """Drop rows in `doctype` filtered by `filter_field` == PROJECT (handles
    doctypes that don't have a `project` column by skipping)."""
    if not frappe.db.exists("DocType", doctype):
        return
    try:
        rows = frappe.get_all(doctype, filters={filter_field: PROJECT}, pluck="name")
    except Exception:
        return
    for n in rows:
        try:
            frappe.delete_doc(doctype, n, ignore_permissions=True, force=True)
        except Exception as e:
            print(f"  skip {doctype}/{n}: {e}")
    if rows:
        print(f"  dropped {len(rows)} {doctype}")


def _drop_via_link(doctype):
    """Drop rows in `doctype` that link to PROJECT via the GRM Project Link
    child table convention (project field via parent ref)."""
    if not frappe.db.exists("DocType", doctype):
        return
    # Try direct project field first
    try:
        rows = frappe.get_all(doctype, filters={"project": PROJECT}, pluck="name")
    except Exception:
        # Try parent link
        try:
            link_rows = frappe.get_all(
                "GRM Project Link",
                filters={"project": PROJECT, "parenttype": doctype},
                fields=["parent"],
            )
            rows = list({r.parent for r in link_rows})
        except Exception:
            return
    for n in rows:
        try:
            frappe.delete_doc(doctype, n, ignore_permissions=True, force=True)
        except Exception as e:
            print(f"  skip {doctype}/{n}: {e}")
    if rows:
        print(f"  dropped {len(rows)} {doctype}")


_PURGE_DOCTYPE_ORDER = [
    "GRM Issue Comment",
    "GRM Issue Citizen",
    "GRM Issue Attachment",
    "GRM Issue Log",
    "GRM Issue",
    "GRM User Project Assignment",
    "GRM Administrative Region",
    "GRM Administrative Level Type",
    "GRM Issue Citizen Group",
    "GRM Issue Age Group",
    "GRM Issue Department",
    "GRM Issue Status",
    "GRM Issue Type",
    "GRM Issue Category",
    "GRM Notification Template",
    "GRM Project Role",
]


def _purge_project(project):
    """Purge a single project's records. Tolerates a missing GRM Project row
    (in case prior partial runs left orphan records around)."""
    project_exists = frappe.db.exists("GRM Project", project)
    if not project_exists:
        # Still try to drop linked records — they may be orphans.
        print(f"NOTE {project}: GRM Project record absent; cleaning orphan-linked records anyway")

    for dt in _PURGE_DOCTYPE_ORDER:
        try:
            rows = frappe.get_all(dt, filters={"project": project}, pluck="name")
        except Exception:
            try:
                link_rows = frappe.get_all(
                    "GRM Project Link",
                    filters={"project": project, "parenttype": dt},
                    fields=["parent"],
                )
                rows = list({r.parent for r in link_rows})
            except Exception:
                continue
        for n in rows:
            try:
                frappe.delete_doc(dt, n, ignore_permissions=True, force=True)
            except Exception as e:
                print(f"  skip {dt}/{n}: {e}")
        if rows:
            print(f"  dropped {len(rows)} {dt}")

    if project_exists:
        try:
            frappe.delete_doc("GRM Project", project, ignore_permissions=True, force=True)
            print(f"DELETED project {project}")
        except Exception as e:
            print(f"  failed to drop project {project}: {e}")
    frappe.db.commit()


def purge():
    if not frappe.db.exists("GRM Project", PROJECT):
        print(f"NOT EXISTS {PROJECT}")
        return
    _purge_project(PROJECT)
    print("--- DONE ---")


def purge_project(project=None):
    """Purge the named project (defaults to RDAP if omitted)."""
    target = project or PROJECT
    _purge_project(target)
    print(f"--- DONE purge_project {target} ---")


_BULK_DOCTYPES_WITH_PROJECT = [
    "GRM Issue Comment",
    "GRM Issue Citizen",
    "GRM Issue Attachment",
    "GRM Issue Log",
    "GRM Issue",
    "GRM User Project Assignment",
    "GRM Administrative Region",
    "GRM Administrative Level Type",
    "GRM Issue Citizen Group",
    "GRM Issue Age Group",
    "GRM Issue Department",
    "GRM Issue Status",
    "GRM Issue Type",
    "GRM Issue Category",
    "GRM Notification Template",
    "GRM Project Role",
]


def _bulk_drop_table_for_project(doctype, project):
    """Raw-SQL bulk delete: drop all rows in `tab<doctype>` where project=<project>
    and any rows in child tables that reference them via parent FK. Skips hooks."""
    if not frappe.db.exists("DocType", doctype):
        return 0
    try:
        # Collect parent names first so we can clean child tables.
        parents = frappe.db.sql(
            f"SELECT name FROM `tab{doctype}` WHERE `project`=%s",
            (project,),
            as_dict=False,
        )
        parent_names = [r[0] for r in parents]
        if not parent_names:
            return 0

        # Drop child-table rows referencing any of these parents.
        meta = frappe.get_meta(doctype)
        # Batch parents into chunks for the IN clause.
        chunk_size = 1000
        for df in meta.get_table_fields():
            child_dt = df.options
            if not child_dt:
                continue
            try:
                for i in range(0, len(parent_names), chunk_size):
                    batch = parent_names[i : i + chunk_size]
                    placeholders = ",".join(["%s"] * len(batch))
                    frappe.db.sql(
                        f"DELETE FROM `tab{child_dt}` "
                        f"WHERE parenttype=%s AND parent IN ({placeholders})",
                        tuple([doctype] + list(batch)),
                    )
            except Exception as e:
                print(f"  skip child {child_dt}: {e}")

        # Drop the parent rows.
        frappe.db.sql(
            f"DELETE FROM `tab{doctype}` WHERE `project`=%s", (project,)
        )

        # Drop singletons of legacy tags that may dangle.
        try:
            frappe.db.sql(
                "DELETE FROM `tabSingles` WHERE `doctype`=%s",
                (doctype,),
            )
        except Exception:
            pass

        return len(parent_names)
    except Exception as e:
        print(f"  bulk drop {doctype} failed: {e}")
        return 0


def bulk_purge_project(project=None):
    """Fast bulk purge via raw SQL (no hooks). Use for test cleanup only.
    Iterates `_BULK_DOCTYPES_WITH_PROJECT` in dependency order, deletes
    matching rows + child tables, then drops the GRM Project row itself."""
    target = project or PROJECT
    print(f"=== bulk_purge_project {target} ===")
    project_exists = frappe.db.exists("GRM Project", target)
    if not project_exists:
        print(f"NOTE {target}: GRM Project absent; cleaning orphan-linked records anyway")

    total = 0
    for dt in _BULK_DOCTYPES_WITH_PROJECT:
        n = _bulk_drop_table_for_project(dt, target)
        if n:
            print(f"  bulk-dropped {n} {dt}")
            total += n

    # Project Link child rows (used by some doctypes for many-to-many to project).
    try:
        n = frappe.db.sql(
            "DELETE FROM `tabGRM Project Link` WHERE `project`=%s",
            (target,),
        )
        print(f"  bulk-dropped GRM Project Link rows for {target}")
    except Exception as e:
        print(f"  skip GRM Project Link: {e}")

    if project_exists:
        try:
            frappe.db.sql(
                "DELETE FROM `tabGRM Project` WHERE name=%s", (target,)
            )
            print(f"DELETED project row {target}")
        except Exception as e:
            print(f"  failed to drop project row {target}: {e}")
    frappe.db.commit()
    print(f"--- DONE bulk_purge_project {target}: {total} parent rows dropped ---")


def purge_orphan_admin_levels():
    """Best-effort cleanup of orphan GRM Administrative Level Type records
    that have no parent project (or whose project has been deleted). This
    side-steps the global-uniqueness autoname clash that blocks fresh
    wizard setups when stale level names from old test projects are still
    occupying the autoname slot."""
    try:
        rows = frappe.get_all(
            "GRM Administrative Level Type",
            fields=["name", "level_name", "project"],
            limit_page_length=0,
        )
    except Exception as e:
        print(f"  failed to list admin levels: {e}")
        return
    deleted = 0
    for r in rows:
        if not r.project or not frappe.db.exists("GRM Project", r.project):
            try:
                frappe.delete_doc(
                    "GRM Administrative Level Type",
                    r.name,
                    ignore_permissions=True,
                    force=True,
                )
                deleted += 1
                print(f"  dropped orphan admin level {r.name} (project={r.project})")
            except Exception as e:
                print(f"  skip {r.name}: {e}")
    frappe.db.commit()
    print(f"--- DONE purge_orphan_admin_levels: {deleted} dropped ---")
