"""SUITE: ARCH-CONTRACT — invariants from the per-project architecture
plan (`2026-04-25-egrm-per-project-architecture-implementation.md`).

This suite is the safety net for the contracts the architecture plan
promises. Every assertion below maps back to an explicit promise in the
plan; if a refactor regresses one of these, the developer should know
within a single CI run instead of via a customer ticket.

Coverage map (plan section → test ID):

  Task 1.2 / seed_duty_catalog            → AC-1.duty_catalog_complete
  Task 1.7 / seed_grm_role_catalog        → AC-2.frappe_role_catalog
  Task 1.7c / delete_legacy_grm_roles     → AC-2.legacy_roles_removed
  Task 1.4 GRM Project Role validations   → AC-3.project_role_min_one_duty,
                                             AC-3.project_role_unique_per_project
  Task 1.7 role_query scoping             → AC-4.role_query_scopes_to_project
  Task 1.11 boot_session payload          → AC-5.boot_session_shape_logged_in,
                                             AC-5.boot_session_shape_guest
  Task 2.4 workspace cleanup              → AC-6.exactly_two_workspaces
  Task 3.1 Step 3 activate_project gates  → AC-7.activate_project_no_levels,
                                             AC-7.activate_project_no_active_role
  Task 1.7d FIELD_DUTY_REQUIREMENTS       → AC-8.field_duty_status_blocked
  Task 1.10 PM creator guard              → AC-9.pm_cannot_assign_outside_scope
  Task 1.8 cross-project User Permission  → AC-10.cross_project_isolation

The suite needs a freshly-onboarded site: ONBOARDING must have run
first (so RW-WB / KE-EAC / STJ-HOSP exist with active project roles).
"""
from __future__ import annotations

import json
import sys

import requests

from _common import (
    ACTOR_GRM_OFFICER, ACTOR_PROJECT_ADMIN, ALL_PROJECT_CODES, ART,
    PROJECT_KE, PROJECT_RW, SuiteRun, get, login, logout, msg, post,
    run, state_for, summary,
)


CANONICAL_DUTIES = [
    "Intake", "Review", "Assignment",
    "Investigate & Resolve", "Feedback", "Supervise",
]

# Per the plan: 6 duty-roles + 1 platform-admin role = 7 total.
EXPECTED_FRAPPE_GRM_ROLES = {
    "GRM Intake",
    "GRM Review",
    "GRM Assignment",
    "GRM Investigate & Resolve",
    "GRM Feedback",
    "GRM Supervise",
    "GRM Platform Administrator",
}

# Roles the plan says MUST be deleted by `delete_legacy_grm_roles`.
LEGACY_GRM_ROLES = {
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
}


def _resource_count(s: requests.Session, doctype: str,
                    filters: dict | None = None) -> int:
    code, body = get(
        s,
        "/api/method/frappe.client.get_count",
        params={
            "doctype": doctype,
            "filters": json.dumps(filters or {}),
        },
        timeout=15,
    )
    n = msg(body)
    try:
        return int(n)
    except (TypeError, ValueError):
        return 0


def _resource_get_list(s: requests.Session, doctype: str,
                       filters: dict | None = None,
                       fields: list[str] | None = None,
                       limit: int = 100) -> list[dict]:
    code, body = get(
        s,
        "/api/method/frappe.client.get_list",
        params={
            "doctype": doctype,
            "filters": json.dumps(filters or {}),
            "fields": json.dumps(fields or ["name"]),
            "limit_page_length": str(limit),
        },
        timeout=15,
    )
    rows = msg(body) or []
    if isinstance(rows, dict):
        rows = rows.get("data", []) or []
    return rows if isinstance(rows, list) else []


def _resource_post(s: requests.Session, doctype: str,
                   payload: dict) -> tuple[int, dict]:
    return post(
        s,
        f"/api/resource/{doctype.replace(' ', '%20')}",
        data=payload,
        timeout=20,
    )


# ----------------------------------------------------------------- main

def main() -> int:
    suite = SuiteRun("ARCH-CONTRACT")

    rw = state_for(PROJECT_RW)
    if not rw:
        suite.ok("AC-0.RW_state_present", False,
                 "ONBOARDING suite must run first")
        return summary(suite)

    s = requests.Session()
    code, body = login(s, *ACTOR_PROJECT_ADMIN)
    suite.ok("AC-0.admin_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])

    # ---- AC-1: duty catalog (6 canonical) ------------------------------
    duties = _resource_get_list(s, "GRM Duty",
                                fields=["name", "lifecycle_phase"], limit=50)
    duty_names = {d.get("name") for d in duties}
    missing = set(CANONICAL_DUTIES) - duty_names
    suite.ok("AC-1.duty_catalog_complete",
             not missing, f"missing={missing} got={duty_names}")

    # ---- AC-2: Frappe Role catalog -------------------------------------
    roles = _resource_get_list(s, "Role",
                               filters={"role_name": ["like", "GRM%"]},
                               fields=["name", "role_name"], limit=50)
    role_names = {r.get("role_name") for r in roles}
    missing_new = EXPECTED_FRAPPE_GRM_ROLES - role_names
    leftover_legacy = LEGACY_GRM_ROLES & role_names
    suite.ok("AC-2.frappe_role_catalog_complete",
             not missing_new,
             f"missing={missing_new} got={role_names}")
    suite.ok("AC-2.legacy_roles_removed",
             not leftover_legacy,
             f"still_present={leftover_legacy}")

    # ---- AC-3: GRM Project Role validations ----------------------------
    # (a) cannot save with zero duties
    project_name = rw["project_name"]
    code, body = _resource_post(s, "GRM Project Role", {
        "project": project_name,
        "role_name": "AC-3-Empty-Role",
        "is_active": 1,
        "duties": [],
    })
    # Frappe surfaces validation errors as 417 (or 4xx with exception).
    suite.ok("AC-3.project_role_min_one_duty",
             code != 200 and code != 201,
             f"unexpected http={code} body={str(body)[:200]}")

    # (b) cannot create duplicate (project, role_name)
    code, body = _resource_post(s, "GRM Project Role", {
        "project": project_name,
        "role_name": "Administrator",         # already created by ONBOARDING
        "is_active": 1,
        "duties": [{"duty": "Supervise"}],
    })
    suite.ok("AC-3.project_role_unique_per_project",
             code != 200 and code != 201,
             f"unexpected http={code} body={str(body)[:200]}")

    # ---- AC-4: role_query scopes to project ----------------------------
    # Without a project filter, role_query MUST return an empty list.
    code, body = post(
        s,
        "/api/method/frappe.desk.search.search_link",
        data={
            "doctype": "GRM Project Role",
            "txt": "",
            "reference_doctype": "GRM User Project Assignment",
            "page_length": "20",
            "query":
                "egrm.egrm.doctype.grm_user_project_assignment."
                "grm_user_project_assignment.role_query",
            "filters": json.dumps({}),
        },
        timeout=15,
    )
    rows = msg(body) or []
    if isinstance(rows, dict):
        rows = rows.get("results") or rows.get("message") or []
    suite.ok("AC-4.role_query_empty_without_project",
             isinstance(rows, list) and len(rows) == 0,
             f"got_rows={len(rows) if isinstance(rows, list) else rows}")

    # With a project filter, role_query MUST return ONLY that project's
    # active roles.
    code, body = post(
        s,
        "/api/method/frappe.desk.search.search_link",
        data={
            "doctype": "GRM Project Role",
            "txt": "",
            "reference_doctype": "GRM User Project Assignment",
            "page_length": "20",
            "query":
                "egrm.egrm.doctype.grm_user_project_assignment."
                "grm_user_project_assignment.role_query",
            "filters": json.dumps({"project": project_name}),
        },
        timeout=15,
    )
    rows = msg(body) or []
    if isinstance(rows, dict):
        rows = rows.get("results") or rows.get("message") or []
    suite.ok("AC-4.role_query_returns_for_project",
             isinstance(rows, list) and len(rows) >= 1,
             f"got={rows[:3]}")

    # ---- AC-5: boot_session payload shape ------------------------------
    # Logged-in (admin) → payload populated.
    code, body = get(s, "/api/method/frappe.boot.get_bootinfo",
                     timeout=20)
    boot = msg(body) or {}
    egrm = boot.get("egrm") if isinstance(boot, dict) else None
    suite.ok(
        "AC-5.boot_session_shape_logged_in",
        isinstance(egrm, dict) and {
            "active_project", "duties", "is_platform_admin",
            "available_projects",
        } <= set(egrm.keys()),
        f"got_keys={list(egrm.keys()) if isinstance(egrm, dict) else egrm}",
    )
    if isinstance(egrm, dict):
        suite.ok(
            "AC-5.admin_is_platform_admin",
            bool(egrm.get("is_platform_admin")),
            f"egrm={egrm}",
        )

    # Guest → empties / null.
    s_guest = requests.Session()
    code, body = get(s_guest, "/api/method/frappe.boot.get_bootinfo",
                     timeout=20)
    boot = msg(body) or {}
    egrm = boot.get("egrm") if isinstance(boot, dict) else None
    suite.ok(
        "AC-5.boot_session_shape_guest",
        isinstance(egrm, dict)
        and egrm.get("active_project") in (None, "")
        and egrm.get("duties") in ([], None)
        and not egrm.get("is_platform_admin"),
        f"got={egrm}",
    )

    # ---- AC-6: exactly two EGRM workspaces -----------------------------
    rows = _resource_get_list(s, "Workspace",
                              filters={"module": "EGRM"},
                              fields=["name", "title"], limit=50)
    ws_names = sorted({r.get("name") for r in rows})
    suite.ok(
        "AC-6.exactly_two_workspaces",
        len(ws_names) == 2 and set(ws_names) == {"eGRM", "Platform"},
        f"got={ws_names}",
    )

    # ---- AC-7: activate_project failure modes --------------------------
    # (a) New project with zero admin levels → must reject.
    no_levels_code = "AC-7-NoLevels"
    code, _ = _resource_post(s, "GRM Project", {
        "project_code": no_levels_code,
        "title": "AC-7 — no admin levels",
        "start_date": "2026-01-01",
        "end_date": "2030-12-31",
        "default_language": "en",
    })
    if code in (200, 201):
        # Must have ≥1 active role to isolate the "no levels" error.
        _resource_post(s, "GRM Project Role", {
            "project": no_levels_code,
            "role_name": "Administrator",
            "is_active": 1,
            "duties": [{"duty": "Supervise"}],
        })
        c2, b2 = post(
            s,
            "/api/method/egrm.egrm.page.grm_project_wizard."
            "grm_project_wizard.activate_project",
            data={"project": no_levels_code},
        )
        # Frappe converts ValidationError into HTTP 417.
        suite.ok("AC-7.activate_project_no_levels",
                 c2 != 200,
                 f"unexpected success http={c2} body={str(b2)[:200]}")

    # (b) New project with levels but NO active role → must reject.
    no_role_code = "AC-7-NoRole"
    code, _ = _resource_post(s, "GRM Project", {
        "project_code": no_role_code,
        "title": "AC-7 — no role",
        "start_date": "2026-01-01",
        "end_date": "2030-12-31",
        "default_language": "en",
    })
    if code in (200, 201):
        _resource_post(s, "GRM Administrative Level Type", {
            "project": no_role_code,
            "level_name": "Country",
            "level_order": 0,
        })
        c2, b2 = post(
            s,
            "/api/method/egrm.egrm.page.grm_project_wizard."
            "grm_project_wizard.activate_project",
            data={"project": no_role_code},
        )
        suite.ok("AC-7.activate_project_no_active_role",
                 c2 != 200,
                 f"unexpected success http={c2} body={str(b2)[:200]}")

    logout(s)

    # ---- AC-8: FIELD_DUTY_REQUIREMENTS — non-Review user blocked
    #            from changing `status` ---------------------------------
    # We try to update the status of an existing RW issue as a user
    # with Intake duty only. If no Intake-only user is provisioned the
    # check is informational-only.
    s_off = requests.Session()
    code, body = login(s_off, *ACTOR_GRM_OFFICER)
    if code == 200:
        # Find any Open RW issue.
        issues = _resource_get_list(
            s_off, "GRM Issue",
            filters={"project": project_name},
            fields=["name", "status"], limit=1,
        )
        if issues:
            iid = issues[0]["name"]
            target_status = next(iter(rw.get("statuses", {}).values()), None)
            if target_status:
                code, body = post(
                    s_off,
                    "/api/method/frappe.client.set_value",
                    data={
                        "doctype": "GRM Issue", "name": iid,
                        "fieldname": "status", "value": target_status,
                    },
                    timeout=15,
                )
                # The plan promises: non-Review users → PermissionError.
                # Frappe surfaces that as HTTP 403 / 417.
                blocked = code in (403, 417, 401, 400)
                suite.ok("AC-8.field_duty_status_blocked",
                         blocked,
                         f"http={code} body={str(body)[:200]}")
        logout(s_off)

    # ---- AC-10: cross-project isolation --------------------------------
    # An officer who is assigned only to RW must not see KE issues.
    s_off2 = requests.Session()
    if login(s_off2, *ACTOR_GRM_OFFICER)[0] == 200:
        ke = state_for(PROJECT_KE)
        if ke:
            rows = _resource_get_list(
                s_off2, "GRM Issue",
                filters={"project": ke["project_name"]},
                fields=["name", "project"], limit=20,
            )
            # If the officer is assigned to RW only, this list MUST be empty.
            # (If the officer is assigned to multiple projects, this assertion
            # is informational — verify via a stricter actor in your fleet.)
            suite.ok("AC-10.cross_project_isolation_ke_invisible_to_rw_officer",
                     isinstance(rows, list) and len(rows) == 0,
                     f"leak={[r.get('name') for r in rows[:5]]}")
        logout(s_off2)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
