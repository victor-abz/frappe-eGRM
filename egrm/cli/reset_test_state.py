"""Reset eGRM site state to a known-clean baseline for the AQE full-suite.

This CLI deletes every project the AQE suites create (RW-WB, KE-EAC,
STJ-HOSP, PERF-IMPORT, AC-7-NoLevels, AC-7-NoRole, RDAP) along with
every record that hangs off them — admin level types, admin regions,
issue categories/types/statuses, age groups, citizen groups,
departments, project roles, project assignments, project links, issues,
issue logs, comments, attachments — and clears stale User Permission
rows pointing at any of those projects.

Run it BEFORE any contiguous PHASE C run so the suites start from the
same baseline they hit on a fresh install.

Run:
    bench --site egrm.local execute egrm.cli.reset_test_state.reset

Idempotent: running on an already-clean site is a no-op.
"""
import frappe


# Projects every AQE suite is allowed to create + spillover from earlier
# experimentation. Anything outside this list is left alone.
TARGET_PROJECTS = (
    "RW-WB",
    "KE-EAC",
    "STJ-HOSP",
    "PERF-IMPORT",
    "AC-7-NoLevels",
    "AC-7-NoRole",
    "RDAP",  # legacy seed from an earlier run
)


# Order matters: child rows first, then parents, finally the project
# itself. Each entry is (DocType, project field name).
DEPENDENT_DOCTYPES = [
    # Issue child rows (no direct `project` FK — cascade off GRM Issue
    # below via Frappe's on-trash cascade or Link delete).
    ("GRM Issue Comment", "_via_issue"),
    ("GRM Issue Log", "_via_issue"),
    ("GRM Issue Attachment", "_via_issue"),
    ("GRM Issue", "project"),

    # Reference data (catalog-style).
    ("GRM Administrative Region", "project"),
    ("GRM Administrative Level Type", "project"),
    ("GRM Issue Citizen Group", None),    # via GRM Project Link
    ("GRM Issue Age Group", None),
    ("GRM Issue Status", None),
    ("GRM Issue Type", None),
    ("GRM Issue Category", None),
    ("GRM Issue Department", None),

    # Roles + assignments.
    ("GRM User Project Assignment", "project"),
    ("GRM Project Role", "project"),

    # Project itself — must come last.
    ("GRM Project", None),
]


def _delete_via_project_link(doctype: str, projects: tuple[str, ...]) -> int:
    """Delete docs whose `grm_project_link` child table mentions any of
    the given projects."""
    if not projects:
        return 0
    parents = frappe.get_all(
        "GRM Project Link",
        filters={
            "parenttype": doctype,
            "project": ["in", list(projects)],
        },
        pluck="parent",
        distinct=True,
    )
    deleted = 0
    for name in parents:
        try:
            frappe.delete_doc(
                doctype, name,
                ignore_permissions=True,
                force=True,
                ignore_on_trash=True,
            )
            deleted += 1
        except Exception as exc:
            print(f"  could not delete {doctype} {name}: {exc}")
    return deleted


def _delete_by_field(doctype: str, field: str,
                     projects: tuple[str, ...]) -> int:
    if not projects:
        return 0
    names = frappe.get_all(
        doctype,
        filters={field: ["in", list(projects)]},
        pluck="name",
    )
    deleted = 0
    for name in names:
        try:
            # Submittable docs must be cancelled before delete. Try a
            # cancel-then-delete cycle for any failure that mentions
            # "Submitted Record".
            frappe.delete_doc(
                doctype, name,
                ignore_permissions=True,
                force=True,
                ignore_on_trash=True,
            )
            deleted += 1
        except Exception as exc:
            msg = str(exc)
            if "Submitted Record" in msg or "docstatus" in msg.lower():
                try:
                    doc = frappe.get_doc(doctype, name)
                    doc.flags.ignore_permissions = True
                    if getattr(doc, "docstatus", 0) == 1:
                        doc.cancel()
                    frappe.delete_doc(
                        doctype, name,
                        ignore_permissions=True, force=True,
                        ignore_on_trash=True,
                    )
                    deleted += 1
                    continue
                except Exception as exc2:
                    # Fallback: nuke the row via SQL.
                    try:
                        frappe.db.delete(doctype, {"name": name})
                        deleted += 1
                        continue
                    except Exception:
                        print(f"  could not cancel+delete {doctype} {name}: {exc2}")
                        continue
            print(f"  could not delete {doctype} {name}: {exc}")
    return deleted


def _delete_project(name: str) -> int:
    if not frappe.db.exists("GRM Project", name):
        return 0
    try:
        frappe.delete_doc(
            "GRM Project", name,
            ignore_permissions=True,
            force=True,
            ignore_on_trash=True,
        )
        return 1
    except Exception as exc:
        print(f"  could not delete GRM Project {name}: {exc}")
        return 0


def _clear_user_permissions() -> int:
    """Drop User Permission rows pointing at any AQE project.

    Stale rows from prior runs cause 403s on project insert.
    """
    rows = frappe.get_all(
        "User Permission",
        filters={
            "allow": "GRM Project",
            "for_value": ["in", list(TARGET_PROJECTS)],
        },
        pluck="name",
    )
    deleted = 0
    for n in rows:
        try:
            frappe.delete_doc(
                "User Permission", n,
                ignore_permissions=True, force=True,
            )
            deleted += 1
        except Exception as exc:
            print(f"  could not delete User Permission {n}: {exc}")
    return deleted


def _delete_via_issue(doctype: str, projects: tuple[str, ...]) -> int:
    """Delete docs that hang off GRM Issue rows scoped to target projects."""
    if not projects:
        return 0
    issue_names = frappe.get_all(
        "GRM Issue",
        filters={"project": ["in", list(projects)]},
        pluck="name",
    )
    if not issue_names:
        return 0
    # The link from child → issue can vary by doctype. Most use `issue`.
    # Try common candidates.
    candidate_fields = ("issue", "parent_issue", "grm_issue", "issue_id")
    for field in candidate_fields:
        try:
            names = frappe.get_all(
                doctype,
                filters={field: ["in", issue_names]},
                pluck="name",
            )
        except Exception:
            continue
        if names:
            deleted = 0
            for n in names:
                try:
                    frappe.delete_doc(
                        doctype, n,
                        ignore_permissions=True, force=True,
                        ignore_on_trash=True,
                    )
                    deleted += 1
                except Exception as exc:
                    print(f"  could not delete {doctype} {n}: {exc}")
            return deleted
    return 0


def reset() -> None:
    print(f"--- reset_test_state: targets={list(TARGET_PROJECTS)} ---")

    total_deleted: dict[str, int] = {}
    for doctype, field in DEPENDENT_DOCTYPES:
        if doctype == "GRM Project":
            n = sum(_delete_project(p) for p in TARGET_PROJECTS)
        elif field == "_via_issue":
            n = _delete_via_issue(doctype, TARGET_PROJECTS)
        elif field is None:
            n = _delete_via_project_link(doctype, TARGET_PROJECTS)
        else:
            n = _delete_by_field(doctype, field, TARGET_PROJECTS)
        total_deleted[doctype] = n

    ups = _clear_user_permissions()

    frappe.db.commit()

    print("--- summary ---")
    for k, v in total_deleted.items():
        print(f"  {k}: {v}")
    print(f"  User Permission (project-scoped): {ups}")
    print("--- DONE reset_test_state ---")
