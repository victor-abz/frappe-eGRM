"""Assign canonical AQE-suite test users to the AQE test projects.

This is the bridge between:

- The AQE full-suite projects ``RW-WB``, ``KE-EAC``, ``STJ-HOSP`` —
  freshly provisioned by ``run_onboarding_tests.py`` against a clean
  site. The wizard creates the project + admin levels + regions but
  does NOT auto-assign any of the duty-bearing users to it.
- The MULTI-PROJECT and MOBILE-DUTY suites which require:
    - ``project-admin@egrm.test`` to have the platform-level visibility
      already granted by their ``GRM Platform Administrator`` role
      (no per-project assignment needed).
    - ``grm-officer@egrm.test`` (mobile actor) to be assigned to *at
      least one* of the AQE projects so ``user_context.accessible_projects``
      is non-empty (required by MP-2 and the mobile pull/push surface
      via API-CONTRACT, MOBILE-DUTY, ISSUE-LIFECYCLE).

We deliberately do NOT touch ``RDAP`` (production-shaped seed handled
by ``seed_rdap.py``). The project codes here are the AQE-only codes.

Run::

    bench --site egrm.local execute egrm.cli.seed_aqe_projects.assign

This is idempotent — re-running creates no duplicates.
"""

from __future__ import annotations

import logging

import frappe

log = logging.getLogger(__name__)


# Canonical AQE-suite project codes (kept in sync with
# docs/superpowers/plans/aqe-generated/_common.py: ALL_PROJECT_CODES)
AQE_PROJECT_CODES: tuple[str, ...] = ("RW-WB", "KE-EAC", "STJ-HOSP")


# Test users who need at least one assignment row per AQE project so
# their pull/push, lookup, and mobile flows resolve a real region.
# Empty 'roles' means "don't touch" — we only manage assignments here.
_USERS_REQUIRING_ASSIGNMENTS: tuple[str, ...] = (
    "grm-officer@egrm.test",
    "field-officer@egrm.test",
    "triage-officer@egrm.test",
    "resolver@egrm.test",
)

# AQE arch-contract assertions AC-8 and AC-10 require
#   grm-officer@egrm.test  =  Intake-duty only, RW-WB-only
# (matches test-users-and-credentials.md §2 — "Cell Field Officer
# (mobile canonical), Intake-only, scoped to Nyamatete Village").
# Without this restriction, the same actor would have Review +
# multi-project visibility (because every project's Administrator role
# carries Review), and AC-8/AC-10 would (correctly) flag the leak as a
# regression. Map kept here so the wiring is testable in one place.
_INTAKE_ONLY_USERS: frozenset[str] = frozenset({"grm-officer@egrm.test"})
_INTAKE_ONLY_PROJECTS: frozenset[str] = frozenset({"RW-WB"})


def _pick_root_region(project_code: str) -> str | None:
    """Find the highest-level (root) region for the project.

    AQE seed users get the root assignment so their accessible-region
    hierarchy includes every descendant region. This is what the
    inner-workflow tests expect — the issue lifecycle suite picks
    arbitrary regions by creation order and the officer must be able to
    file/process issues anywhere in the project, not just one village.
    """
    levels = frappe.get_all(
        "GRM Administrative Level Type",
        filters={"project": project_code},
        fields=["name", "level_order"],
        order_by="level_order asc",
    )
    if not levels:
        return None

    # Try each level from root -> leaf, pick the first level with regions.
    for lvl in levels:
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": project_code, "administrative_level": lvl["name"]},
            fields=["name"],
            order_by="creation",
            limit=1,
        )
        if regions:
            return regions[0]["name"]

    # Fallback: any region under the project.
    any_region = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": project_code},
        fields=["name"],
        order_by="creation",
        limit=1,
    )
    return any_region[0]["name"] if any_region else None


def _pick_project_role(project_code: str) -> str | None:
    """Pick the canonical assignment role for a project.

    Convention: every project gets an 'Administrator' role at provisioning
    time; otherwise we fall back to whatever role exists. None means the
    project has no GRM Project Role at all (shouldn't happen for AQE
    projects but we return None defensively rather than raising).
    """
    # Prefer Administrator if available
    admin = frappe.get_all(
        "GRM Project Role",
        filters={"project": project_code, "role_name": "Administrator"},
        fields=["name"],
        limit=1,
    )
    if admin:
        return admin[0]["name"]
    any_role = frappe.get_all(
        "GRM Project Role",
        filters={"project": project_code},
        fields=["name"],
        order_by="creation",
        limit=1,
    )
    return any_role[0]["name"] if any_role else None


def _ensure_intake_only_role(project_code: str) -> str | None:
    """Idempotently provision an Intake-only project role.

    Used so the canonical mobile field actor (`grm-officer@egrm.test`)
    can hold a project assignment that grants ONLY the Intake duty —
    matching the live RDAP role assignment documented in
    `test-users-and-credentials.md`. Without this, AC-8
    (FIELD_DUTY_REQUIREMENTS — non-Review user must not change status)
    and AC-10 (cross-project isolation when officer is RW-only) cannot
    pass under the AQE seed.
    """
    role_name = "AQE-Intake-Only"
    existing = frappe.get_all(
        "GRM Project Role",
        filters={"project": project_code, "role_name": role_name},
        fields=["name"],
        limit=1,
    )
    if existing:
        return existing[0]["name"]
    if not frappe.db.exists("GRM Duty", "Intake"):
        # Defensive: the duty catalog must exist; if it doesn't there's
        # no point provisioning the role.
        return None
    doc = frappe.new_doc("GRM Project Role")
    doc.project = project_code
    doc.role_name = role_name
    doc.is_active = 1
    doc.description = "AQE — Intake duty only (mobile field officer)"
    doc.append("duties", {"duty": "Intake"})
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_assignment(user: str, project_code: str, region: str, role: str) -> str:
    """Idempotently create a GRM User Project Assignment row.

    Returns 'created' / 'exists' / 'reactivated' / 'role_updated'.
    """
    existing = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user,
            "project": project_code,
            "administrative_region": region,
        },
        fields=["name", "is_active", "activation_status", "role"],
        limit=1,
    )
    if existing:
        # Make sure it's active so user_context picks it up
        row = existing[0]
        updates: dict = {}
        if not row["is_active"]:
            updates["is_active"] = 1
        if row.get("activation_status") != "Activated":
            updates["activation_status"] = "Activated"
        if row.get("role") != role:
            updates["role"] = role
        if updates:
            frappe.db.set_value(
                "GRM User Project Assignment", row["name"], updates
            )
            return "reactivated" if "role" not in updates else "role_updated"
        return "exists"

    doc = frappe.new_doc("GRM User Project Assignment")
    doc.user = user
    doc.project = project_code
    doc.administrative_region = region
    doc.role = role
    doc.is_active = 1
    # The doctype's `before_insert` hook unconditionally flips
    # government-worker assignments to 'Pending Activation' because the
    # project role here grants Intake / Investigate & Resolve duties.
    # That blocks `user_context.accessible_projects` from listing the
    # project until an SMS-style activation flow runs. For test seed
    # purposes we want the assignment to be live immediately, so we
    # post-update the row via a direct DB write after insert.
    doc.insert(ignore_permissions=True)
    frappe.db.set_value(
        "GRM User Project Assignment",
        doc.name,
        {"activation_status": "Activated", "is_active": 1},
        update_modified=False,
    )
    return "created"


def assign_for_project(project_code: str, *, verbose: bool = False) -> dict[str, str]:
    """Assign every canonical AQE test user to a single project's root region.

    Idempotent. Returns a dict ``{user_email: action}`` where action is one of
    ``created`` / ``exists`` / ``reactivated`` / ``SKIP: <reason>``.

    This is the per-project building block used by both the bench CLI
    ``assign()`` and the post-activation auto-bridge in
    ``grm_project_wizard.activate_project``.
    """
    actions: dict[str, str] = {}

    if not frappe.db.exists("GRM Project", project_code):
        if verbose:
            print(f"SKIP project {project_code}: not provisioned")
        return {"_project": "SKIP: not provisioned"}

    region = _pick_root_region(project_code)
    if not region:
        if verbose:
            print(f"SKIP project {project_code}: no leaf region")
        return {"_project": "SKIP: no leaf region"}

    default_role = _pick_project_role(project_code)
    if not default_role:
        if verbose:
            print(f"SKIP project {project_code}: no project role")
        return {"_project": "SKIP: no project role"}

    intake_role = _ensure_intake_only_role(project_code)

    for user in _USERS_REQUIRING_ASSIGNMENTS:
        if not frappe.db.exists("User", user):
            actions[user] = "SKIP: user not provisioned"
            if verbose:
                print(f"SKIP user {user}: not provisioned")
            continue

        # AC-8 / AC-10: keep grm-officer Intake-only and RW-WB-only.
        if user in _INTAKE_ONLY_USERS:
            if project_code not in _INTAKE_ONLY_PROJECTS:
                _deactivate_assignments(user, project_code)
                actions[user] = "SKIP: user is intake-only, project out of scope"
                if verbose:
                    print(
                        f"  {user} -> {project_code}: "
                        f"intake-only, deactivating any prior rows"
                    )
                continue
            chosen_role = intake_role or default_role
        else:
            chosen_role = default_role

        try:
            action = _ensure_assignment(user, project_code, region, chosen_role)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception(
                "[seed_aqe_projects] failed to assign %s to %s/%s: %s",
                user, project_code, region, exc,
            )
            action = f"ERROR: {exc}"

        actions[user] = f"{action} ({region})"
        if verbose:
            print(
                f"  {user} -> {project_code} via {region} "
                f"(role={chosen_role}): {action}"
            )

    return actions


def _deactivate_assignments(user: str, project_code: str) -> int:
    """Deactivate any active assignment rows linking ``user`` to ``project_code``.

    Used when an Intake-only user (e.g. ``grm-officer``) was previously
    seeded onto a project that AC-8/AC-10 require them to be absent
    from. Idempotent — returns the number of rows deactivated.
    """
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "project": project_code, "is_active": 1},
        fields=["name"],
    )
    for row in rows:
        frappe.db.set_value(
            "GRM User Project Assignment", row["name"],
            {"is_active": 0, "activation_status": "Suspended"},
            update_modified=False,
        )
    if rows:
        log.info(
            "[seed_aqe_projects] deactivated %d existing %s assignments to %s",
            len(rows), user, project_code,
        )
    return len(rows)


def assign() -> None:
    """Assign every canonical AQE test user to every AQE project's leaf region."""
    summary: dict[str, dict[str, str]] = {}
    for project_code in AQE_PROJECT_CODES:
        actions = assign_for_project(project_code, verbose=True)
        for user, action in actions.items():
            summary.setdefault(user, {})[project_code] = action

    frappe.db.commit()
    print("--- AQE project assignments complete ---")
    for user, projects in summary.items():
        for code, action in projects.items():
            print(f"{user} | {code}: {action}")
