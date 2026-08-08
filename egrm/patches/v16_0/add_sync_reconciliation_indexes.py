# Copyright (c) 2026, eGRM and contributors
# For license information, please see license.txt
"""Add the indexes the sync reconciliation path depends on.

``pull_changes`` now checks, on every incremental pull, whether a device is
missing records it is entitled to. Two queries carry that check and both are
unindexed on a stock install:

``GRM User Project Assignment (user, modified)``
    Reads the newest assignment row for one user to detect a widened scope.
    Without a leading ``user`` column the planner falls back to the ``modified``
    index and, for a stale watermark, scans nearly the whole table — the exact
    devices this feature exists to repair would be the ones triggering a full
    scan on every pull.

``GRM Project Link (parenttype, project, parent)``
    Backs ``count(distinct parent) ... group by parenttype``, which sizes the
    project-linked reference tables in one query. The three columns are the
    entire query, so this is an index-only scan with no table access.

    Column order is load-bearing. Leading with ``parenttype`` — the GROUP BY
    key — hands MariaDB rows already grouped, so the sort disappears and each
    group is one contiguous range per project. Leading with ``project``
    interleaves the parenttypes and forces a filesort. Measured on 1M link rows
    across 5000 projects (local MariaDB 10.6):

        projects   project-first   parenttype-first
               3         6.9 ms            1.8 ms
              10        23.1 ms            5.7 ms
              40       325.0 ms           22.4 ms

    EXPLAIN confirms the mechanism: project-first reports ``rows: 8000`` with
    ``Using filesort``; parenttype-first reports ``rows: 600`` with
    ``Using where; Using index`` and no sort.

``GRM Issue Attachment (creation)`` and ``(modified)``
    Attachments are pulled by time window — ``creation > watermark`` for the
    created stream, ``modified > watermark and creation <= watermark`` for the
    updated one. Frappe ships child tables with an index on ``parent`` only, so
    both queries had no usable index and fell back to a full scan of every
    attachment row on the site. Parent scoping cannot rescue them: it is a
    semi-join against the user's whole entitlement, which is the wide side of
    the query, not the selective one. The time window is the selective
    predicate, so it is the one that needs the index.

    Measured on 500k attachment rows spread over ~347 days, pulling a
    one-day-old watermark (1446 matching rows):

                       created stream   updated stream
        no index             461.6 ms         436.6 ms
        with indexes          11.6 ms          11.4 ms

    EXPLAIN: ``type=ALL key=NULL rows=390897`` before, ``type=range`` on the
    matching index with ``rows=1446`` after.

``Deleted Document (deleted_doctype, creation)``
    Every pull asks which records were tombstoned since the watermark. Frappe
    indexes this table on ``creation`` alone, and the planner will not use it:
    tombstones cluster in recent history, so ``creation > watermark`` is not
    selective and it full-scans instead. ``deleted_doctype`` — the column that
    *is* selective — has no index at all. This table is append-only and never
    pruned, so it is the one table in the pull whose cost grows forever.

Idempotent: ``frappe.db.add_index`` no-ops when the index already exists, so
repeated ``bench migrate`` runs are safe.
"""

import frappe

INDEXES = (
	("GRM User Project Assignment", ["user", "modified"], "idx_grm_upa_user_modified"),
	("GRM Project Link", ["parenttype", "project", "parent"], "idx_grm_project_link_scope"),
	("GRM Issue Attachment", ["creation"], "idx_grm_issue_attach_creation"),
	("GRM Issue Attachment", ["modified"], "idx_grm_issue_attach_modified"),
	("Deleted Document", ["deleted_doctype", "creation"], "idx_deleted_doctype_creation"),
)


def execute():  # type: ignore[no-untyped-def]
	for doctype, fields, index_name in INDEXES:
		try:
			frappe.db.add_index(doctype, fields, index_name=index_name)
		except Exception as exc:  # pragma: no cover - defensive
			frappe.logger().warning(f"add_sync_reconciliation_indexes: {doctype} skipped ({exc})")
			continue

	frappe.db.commit()
