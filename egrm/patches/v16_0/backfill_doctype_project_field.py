"""Backfill the new top-level `project` Link field on six project-scoped
DocTypes from their `grm_project_link` child table.

Why:
- These DocTypes historically stored project membership only in the
  `grm_project_link` child table (Table fieldtype). Mobile/Desk REST clients
  query them via `filters=[["project","=","<code>"]]` against the parent
  table, which silently returned nothing because there was no top-level
  `project` field.
- We added a `project` Link(GRM Project) at the top of each DocType. The
  per-document `validate()` now mirrors `grm_project_link[0].project` into
  the new field, but existing rows need a one-time backfill.

Affected DocTypes:
- GRM Issue Status
- GRM Issue Type
- GRM Issue Category
- GRM Issue Age Group
- GRM Issue Citizen Group
- GRM Issue Department
"""

from __future__ import annotations

import logging

import frappe

log = logging.getLogger(__name__)


TARGET_DOCTYPES: list[str] = [
    "GRM Issue Status",
    "GRM Issue Type",
    "GRM Issue Category",
    "GRM Issue Age Group",
    "GRM Issue Citizen Group",
    "GRM Issue Department",
]


def execute() -> None:
    """Backfill `project` from the first `grm_project_link` row for each
    affected document. Idempotent: skips rows that already have `project`
    set."""
    for doctype in TARGET_DOCTYPES:
        if not frappe.db.has_column(doctype, "project"):
            log.warning(
                "[backfill_doctype_project_field] %s.project column missing, skipping",
                doctype,
            )
            continue

        rows = frappe.db.sql(
            """
            SELECT parent.name AS parent_name, link.project AS project_code
            FROM `tab{doctype}` parent
            INNER JOIN `tabGRM Project Link` link
                ON link.parent = parent.name
                AND link.parenttype = %s
            WHERE (parent.project IS NULL OR parent.project = '')
              AND link.project IS NOT NULL
              AND link.project != ''
            GROUP BY parent.name
            """.format(doctype=doctype),
            (doctype,),
            as_dict=True,
        )

        for row in rows:
            frappe.db.set_value(
                doctype,
                row["parent_name"],
                "project",
                row["project_code"],
                update_modified=False,
            )

        log.info(
            "[backfill_doctype_project_field] %s: backfilled project field on %d rows",
            doctype,
            len(rows),
        )

    frappe.db.commit()
