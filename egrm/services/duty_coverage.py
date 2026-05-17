"""Duty coverage analysis for a project.

A project is operationally complete only when every active administrative
region has at least one user covering each of the three "operational"
duties: Intake (creates issues), Review (triages / accepts / closes),
Investigate & Resolve (works the issue to resolution).

Duties may be distributed across multiple users in the same region or
concentrated on a single user — both are accepted. The check is gated
at activation time and surfaced via a read-only preview helper so the
wizard UI can render gaps before the operator hits "Activate".

The check is intentionally region-scoped: a Review-duty user in region A
does not satisfy region B even within the same project. Issues raised in
region B need a triager who is in-scope for region B (or one of its
ancestors).
"""
from __future__ import annotations

from typing import TypedDict

import frappe


REQUIRED_DUTIES: tuple[str, ...] = (
    "Intake",
    "Review",
    "Investigate & Resolve",
)


class RegionDutyGap(TypedDict):
    region: str
    region_name: str
    region_path: str
    missing_duties: list[str]


class CoverageReport(TypedDict):
    project: str
    total_regions: int
    covered_regions: int
    gaps: list[RegionDutyGap]
    required_duties: list[str]


def _active_regions(project: str) -> list[dict]:
    return frappe.db.sql(
        """
        SELECT name, region_name, parent_region, COALESCE(path, name) AS path
        FROM `tabGRM Administrative Region`
        WHERE project = %s
        ORDER BY path
        """,
        (project,),
        as_dict=True,
    )


def _build_ancestor_index(regions: list[dict]) -> dict[str, set[str]]:
    """Return ``{region_id: {region_id, parent_id, grandparent_id, ...}}``.

    Region.path stores names (e.g. ``Rwanda:Eastern Province:Kayonza``)
    which can't be matched against the assignment's
    ``administrative_region`` foreign key (a doc ID). Instead, walk
    ``parent_region`` chains — these are real foreign keys and align
    directly with what assignments store.
    """
    by_id: dict[str, dict] = {r["name"]: r for r in regions}
    ancestors: dict[str, set[str]] = {}
    for r in regions:
        chain: set[str] = set()
        cur = r["name"]
        guard = 0
        while cur and guard < 32:
            if cur in chain:
                break
            chain.add(cur)
            cur = (by_id.get(cur) or {}).get("parent_region") or None
            guard += 1
        ancestors[r["name"]] = chain
    return ancestors


def _assignments_with_duties(project: str) -> list[dict]:
    """All configured assignments in the project, joined to their duty
    list. One row per (assignment, duty) so a role with N duties
    produces N rows.

    Coverage includes assignments in either ``Activated`` or
    ``Pending Activation`` state: the wizard creates government-worker
    assignments as Pending until the user enters their activation code,
    but the seat is *reserved* — coverage is a planning concept, not an
    operational one. Truly inactive rows (``is_active=0``) or terminal
    states (``Expired``, ``Suspended``, ``Revoked``) do not count.
    """
    return frappe.db.sql(
        """
        SELECT a.user, a.administrative_region, prd.duty
        FROM `tabGRM User Project Assignment` a
        JOIN `tabGRM Project Role` r ON r.name = a.role
        JOIN `tabGRM Project Role Duty` prd ON prd.parent = a.role
        WHERE a.project = %s
          AND a.is_active = 1
          AND a.activation_status IN ('Activated', 'Pending Activation', '')
          AND prd.duty IN %s
        """,
        (project, REQUIRED_DUTIES),
        as_dict=True,
    )


def compute_coverage(project: str) -> CoverageReport:
    """Return a per-region report of which required duties are uncovered.

    A region is "covered" for duty D when at least one active+activated
    user is assigned with role-duty D anywhere on the region's ancestor
    chain (the region itself or any of its parents).
    """
    regions = _active_regions(project)
    assignments = _assignments_with_duties(project)
    ancestor_index = _build_ancestor_index(regions)

    # Build duty -> set(regions covered directly) from assignments.
    by_region_duty: dict[str, set[str]] = {d: set() for d in REQUIRED_DUTIES}
    for row in assignments:
        if row["duty"] in by_region_duty and row["administrative_region"]:
            by_region_duty[row["duty"]].add(row["administrative_region"])

    gaps: list[RegionDutyGap] = []
    covered = 0
    for region in regions:
        ancestors = ancestor_index.get(region["name"], {region["name"]})
        missing = [
            d for d in REQUIRED_DUTIES
            if not (by_region_duty[d] & ancestors)
        ]
        if missing:
            gaps.append({
                "region": region["name"],
                "region_name": region["region_name"],
                "region_path": region["path"],
                "missing_duties": missing,
            })
        else:
            covered += 1

    return {
        "project": project,
        "total_regions": len(regions),
        "covered_regions": covered,
        "gaps": gaps,
        "required_duties": list(REQUIRED_DUTIES),
    }


def assert_full_coverage(project: str) -> None:
    """Raise frappe.ValidationError if any region is missing a duty.

    Called from the wizard's activate_project step.
    """
    report = compute_coverage(project)
    if not report["gaps"]:
        return
    lines = [
        frappe._(
            "Each region must have at least one user covering Intake,"
            " Review, and Investigate & Resolve duties. The following"
            " regions are missing coverage:"
        )
    ]
    for gap in report["gaps"][:20]:
        lines.append(
            "  - {name} ({path}): missing {duties}".format(
                name=gap["region_name"],
                path=gap["region_path"],
                duties=", ".join(gap["missing_duties"]),
            )
        )
    if len(report["gaps"]) > 20:
        lines.append(
            frappe._("  ... and {n} more").format(n=len(report["gaps"]) - 20)
        )
    frappe.throw("\n".join(lines))
