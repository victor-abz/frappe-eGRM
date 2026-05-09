"""SUITE: Multi-project parallel layouts.

Verifies the three projects provisioned by `run_onboarding_tests.py`
coexist without cross-leakage:

  RW-WB     Rwanda 6-level   (Country/Province/District/Sector/Cell/Village)
  KE-EAC    Kenya 5-level    (Country/County/Sub-County/Ward/Village)
  STJ-HOSP  Hospital 4-level (Hospital/Department/Unit/Ward — non-geographic)

The depth and label set vary deliberately to catch hardcoded
"Province"/"District"/"Region" assumptions and any geographic-only logic.

Prereq: ONBOARDING suite must have completed and written wizard_state.json.
"""
from __future__ import annotations

import sys

import requests

from _common import (
    ACTOR_GRM_OFFICER, ACTOR_PROJECT_ADMIN, ALL_PROJECT_CODES,
    PROJECT_HOSP, PROJECT_KE, PROJECT_RW, SuiteRun, get, load_wizard_state,
    login, logout, msg, post, run, state_for, summary,
)


def _project_codes_from_user_context(s: requests.Session) -> set[str]:
    code, body = get(s, "/api/method/egrm.api.lookup.user_context")
    data = msg(body) or {}
    if isinstance(data, dict):
        data = data.get("data", data)
    out = set()
    for p in (data or {}).get("accessible_projects", []) or []:
        out.add(p.get("project_code") or p.get("name"))
    return out


def _options_for(s: requests.Session, project_name: str) -> dict:
    code, body = get(s, "/api/method/egrm.api.public_submit.get_submission_options",
                     params={"project": project_name})
    d = msg(body) or {}
    if isinstance(d, dict) and "data" in d:
        d = d["data"]
    return d or {}


def main() -> int:
    suite = SuiteRun("MULTI-PROJECT")

    states = load_wizard_state()
    if len(states) < 3:
        suite.ok("MP-0.wizard_state_present", False,
                 f"need 3 onboarded projects, got {len(states)}")
        return summary(suite)
    suite.ok("MP-0.wizard_state_present", True, f"{len(states)} projects")

    by_code = {st["code"]: st for st in states}
    rw   = by_code.get(PROJECT_RW)
    ke   = by_code.get(PROJECT_KE)
    hosp = by_code.get(PROJECT_HOSP)
    suite.ok("MP-0.three_layouts_present",
             all([rw, ke, hosp]),
             f"have={[s['code'] for s in states]}")
    if not (rw and ke and hosp):
        return summary(suite)

    # ------- MP-1: admin sees all 3 projects ----------------------------
    s = requests.Session()
    code, body = login(s, *ACTOR_PROJECT_ADMIN)
    suite.ok("MP-1.admin_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])

    admin_codes = _project_codes_from_user_context(s)
    for c in ALL_PROJECT_CODES:
        suite.ok(f"MP-1.admin_sees_{c}",
                 c in admin_codes, f"got={admin_codes}")
    logout(s)

    # ------- MP-2: officer sees only assigned projects ------------------
    s = requests.Session()
    login(s, *ACTOR_GRM_OFFICER)
    officer_codes = _project_codes_from_user_context(s)
    suite.ok("MP-2.officer_sees_at_least_one",
             len(officer_codes & set(ALL_PROJECT_CODES)) >= 1,
             f"got={officer_codes}")
    logout(s)

    # ------- MP-3..5: depth scoping per project (anonymous) -------------
    s_anon = requests.Session()

    rw_opts = _options_for(s_anon, rw["project_name"])
    rw_levels = rw_opts.get("admin_levels") or []
    suite.ok("MP-3.RW_has_6_levels",
             len(rw_levels) == 6,
             f"levels={[l.get('level_name') for l in rw_levels]}")

    ke_opts = _options_for(s_anon, ke["project_name"])
    ke_levels = ke_opts.get("admin_levels") or []
    suite.ok("MP-4.KE_has_5_levels",
             len(ke_levels) == 5,
             f"levels={[l.get('level_name') for l in ke_levels]}")

    hosp_opts = _options_for(s_anon, hosp["project_name"])
    hosp_levels = hosp_opts.get("admin_levels") or []
    hosp_label_set = {l.get("level_name") for l in hosp_levels}
    suite.ok("MP-5.HOSP_has_4_levels",
             len(hosp_levels) == 4,
             f"levels={hosp_label_set}")
    suite.ok("MP-5.HOSP_uses_org_labels_not_geo",
             "Hospital" in hosp_label_set
             and "District" not in hosp_label_set
             and "Province" not in hosp_label_set,
             f"labels={hosp_label_set}")

    # ------- MP-6: KE label set differs from RW (no hardcoded "District") -----
    rw_label_set = {l.get("level_name") for l in rw_levels}
    ke_label_set = {l.get("level_name") for l in ke_levels}
    suite.ok("MP-6.KE_has_distinct_labels_from_RW",
             "County" in ke_label_set and "District" in rw_label_set
             and "Sub-County" in ke_label_set,
             f"rw={rw_label_set} ke={ke_label_set}")

    # ------- MP-7: cross-project category leak negative -----------------
    rw_cats = (rw_opts or {}).get("categories") or []
    ke_cats_d = _options_for(s_anon, ke["project_name"]).get("categories") or []
    if rw_cats and ke_cats_d:
        rw_region = next(iter(rw["regions"].values()), None)
        ke_type = (ke_opts.get("issue_types") or [{}])[0].get("name")
        # Submit RW-project issue with KE-project category
        if rw_region and ke_type:
            code, body = post(
                s_anon,
                "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": rw["project_name"],
                    "category": ke_cats_d[0]["name"],   # FROM ke
                    "issue_type": (rw_opts.get("issue_types")
                                   or [{}])[0].get("name"),
                    "administrative_region": rw_region,
                    "description": "AQE MP-7 cross-project category leak probe.",
                },
            )
            m = msg(body) or {}
            suite.ok("MP-7.cross_project_category_rejected",
                     isinstance(m, dict) and m.get("status") == "error",
                     f"got={m}")

    # ------- MP-8: each project has its own initial_status --------------
    s = requests.Session()
    login(s, *ACTOR_PROJECT_ADMIN)
    initial_statuses = set()
    for st in (rw, ke, hosp):
        code, body = get(
            s, "/api/resource/GRM Issue Status",
            params={
                "filters": '[["project","=","' + st["project_name"]
                           + '"],["initial_status","=",1]]',
                "fields": '["name","status_name","project"]',
                "limit_page_length": 5,
            },
        )
        rows = (msg(body) or {}).get("data") if isinstance(body, dict) else []
        names = {r.get("name") for r in (rows or [])}
        initial_statuses |= names
        suite.ok(f"MP-8.{st['code']}_has_own_initial_status",
                 len(names) >= 1,
                 f"rows={rows}")
    suite.ok("MP-8.initial_statuses_distinct_across_projects",
             len(initial_statuses) >= 3,
             f"statuses={initial_statuses}")
    logout(s)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
