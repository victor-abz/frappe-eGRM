"""SUITE: Public citizen flows — anonymous submit, tracking, dashboard.

Verifies the unauthenticated citizen surface end-to-end:
  config -> options -> region cascade -> submit -> track -> resolve -> re-track

Targets: egrm/api/public_submit.py, public_tracking.py, public_metrics.py,
         public_reports.py, public_translations.py, portal_config.py.

The PC-13 test asserts the documented gap: there is currently no
public endpoint for a citizen to append a comment to an existing issue.

Prereq: ONBOARDING suite must have completed.
"""
from __future__ import annotations

import sys
import time

import requests

from _common import (
    ACTOR_RESOLVER, ALL_PROJECT_CODES, PROJECT_KE, PROJECT_RW, SuiteRun,
    get, load_wizard_state, login, logout, msg, post, run, state_for,
    summary,
)


def _options(s: requests.Session, project: str) -> dict:
    code, body = get(s, "/api/method/egrm.api.public_submit.get_submission_options",
                     params={"project": project})
    d = msg(body) or {}
    if isinstance(d, dict) and "data" in d:
        d = d["data"]
    return d or {}


def main() -> int:
    suite = SuiteRun("PUBLIC-CITIZEN")

    states = load_wizard_state()
    if not states:
        suite.ok("PC-0.wizard_state_present", False,
                 "ONBOARDING suite must run first")
        return summary(suite)
    rw = state_for(PROJECT_RW)
    ke = state_for(PROJECT_KE)
    if not rw:
        suite.ok("PC-0.RW_state", False, "RW-WB project missing")
        return summary(suite)
    rw_proj = rw["project_name"]

    # ----- PC-1 submission config (no auth) ---------------------------
    s = requests.Session()
    code, body = get(s, "/api/method/egrm.api.public_submit.get_submission_config")
    suite.ok("PC-1.config_no_auth", code == 200, str(body)[:200])
    data = msg(body) or {}
    if isinstance(data, dict):
        data = data.get("data", data)
    suite.ok("PC-1.config_has_otp_flag",
             isinstance(data, dict) and "otp_enabled" in data,
             str(data)[:200])

    # ----- PC-2 submission options w/o project ------------------------
    code, body = get(s, "/api/method/egrm.api.public_submit.get_submission_options")
    data = msg(body) or {}
    if isinstance(data, dict):
        data = data.get("data", data)
    projects = (data or {}).get("projects", [])
    project_codes = {p.get("project_code") for p in (projects or [])}
    suite.ok("PC-2.options_lists_active_projects",
             any(c in project_codes for c in ALL_PROJECT_CODES),
             f"projects={project_codes}")

    # ----- PC-3 options for RW ----------------------------------------
    rw_opts = _options(s, rw_proj)
    cats = rw_opts.get("categories", [])
    types = rw_opts.get("issue_types", [])
    suite.ok("PC-3.RW_categories_present",
             isinstance(cats, list) and len(cats) >= 1, f"cats={cats}")
    suite.ok("PC-3.RW_types_present",
             isinstance(types, list) and len(types) >= 1, f"types={types}")

    # ----- PC-4 region cascade (root) ---------------------------------
    code, body = get(s, "/api/method/egrm.api.public_submit.get_region_children",
                     params={"project": rw_proj})
    regions = msg(body) or {}
    if isinstance(regions, dict):
        regions = regions.get("data", regions)
    suite.ok("PC-4.region_cascade_root_returns_list",
             isinstance(regions, list), f"got={type(regions).__name__}")

    # Find a leaf region in RW from wizard state for submit.
    leaf_region = next(
        (rw["regions"][n] for n in
         ("Nyamatete Village", "Murama Cell", "Mukarange Sector",
          "Kayonza District", "Eastern Province", "Rwanda")
         if n in (rw.get("regions") or {})),
        None,
    )

    # ----- PC-5 anonymous submit RW -----------------------------------
    submitted_data = {}
    if cats and types and leaf_region:
        code, body = post(
            s,
            "/api/method/egrm.api.public_submit.submit_grievance",
            data={
                "project": rw_proj,
                "category": cats[0]["name"],
                "issue_type": types[0]["name"],
                "administrative_region": leaf_region,
                "description": (
                    "Public citizen submission via AQE PC-5 test — "
                    "tracking_code returned should be unique and queryable."
                ),
                "contact_medium": "anonymous",
                "citizen_name": "AQE PC-5 Citizen",
                "issue_date": "2026-05-08",
            },
        )
        m = msg(body) or {}
        suite.ok("PC-5.submit_status_success",
                 isinstance(m, dict) and m.get("status") == "success",
                 f"got={m}")
        submitted_data = (m or {}).get("data", {})
    tracking_code = submitted_data.get("tracking_code")
    issue_name = submitted_data.get("name")
    suite.ok("PC-5.tracking_code_returned", bool(tracking_code),
             f"data={submitted_data}")
    suite.ok("PC-5.issue_name_returned", bool(issue_name),
             f"data={submitted_data}")

    # ----- PC-6 submit grievance to KE (different project) -----------
    if ke:
        ke_opts = _options(s, ke["project_name"])
        ke_cats = ke_opts.get("categories", [])
        ke_types = ke_opts.get("issue_types", [])
        ke_leaf = next(iter(ke.get("regions", {}).values()), None)
        if ke_cats and ke_types and ke_leaf:
            code, body = post(
                s,
                "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": ke["project_name"],
                    "category": ke_cats[0]["name"],
                    "issue_type": ke_types[0]["name"],
                    "administrative_region": ke_leaf,
                    "description": "AQE PC-6 — KE project public submission.",
                    "contact_medium": "anonymous",
                    "citizen_name": "AQE PC-6 Citizen",
                    "issue_date": "2026-05-08",
                },
            )
            m = msg(body) or {}
            suite.ok("PC-6.KE_submit_success",
                     isinstance(m, dict) and m.get("status") == "success",
                     f"got={m}")

    # ----- PC-7 track returned tracking_code --------------------------
    if tracking_code:
        code, body = get(s, "/api/method/egrm.api.public_tracking.track_complaint",
                         params={"tracking_code": tracking_code})
        m = msg(body) or {}
        suite.ok("PC-7.track_returns_success",
                 isinstance(m, dict) and m.get("status") == "success",
                 f"got={m}")
        td = (m or {}).get("data", {}) if isinstance(m, dict) else {}
        suite.ok("PC-7.track_no_pii_phone",
                 isinstance(td, dict) and "phone" not in td and "citizen_name" not in td,
                 f"td_keys={list(td.keys()) if isinstance(td, dict) else td}")
        suite.ok("PC-7.track_status_present",
                 isinstance(td, dict) and bool(td.get("status")), f"td={td}")

    # ----- PC-8 bogus tracking code -----------------------------------
    code, body = get(s, "/api/method/egrm.api.public_tracking.track_complaint",
                     params={"tracking_code": "DOES-NOT-EXIST-XYZ"})
    m = msg(body) or {}
    suite.ok("PC-8.bogus_tracking_returns_error",
             isinstance(m, dict) and m.get("status") == "error",
             f"got={m}")

    # ----- PC-9 public dashboard --------------------------------------
    code, body = get(s, "/api/method/egrm.api.public_metrics.get_public_dashboard",
                     params={"project_id": rw_proj})
    suite.ok("PC-9.dashboard_status", code == 200, str(body)[:200])
    m = msg(body) or {}
    if isinstance(m, dict):
        m = m.get("data", m)
    suite.ok("PC-9.dashboard_has_overview",
             isinstance(m, dict) and ("overview" in m or "totals" in m
                                      or "status_breakdown" in m),
             str(m)[:200])

    # ----- PC-10 public reports list ----------------------------------
    code, body = get(s, "/api/method/egrm.api.public_reports.get_public_reports")
    suite.ok("PC-10.public_reports_status", code == 200, str(body)[:200])

    # ----- PC-11 translations -----------------------------------------
    code, body = get(s, "/api/method/egrm.api.public_translations.get_translations",
                     params={"lang": "en"})
    suite.ok("PC-11.translations_status", code == 200, str(body)[:200])

    # ----- PC-12 portal config ----------------------------------------
    code, body = get(s, "/api/method/egrm.api.portal_config.get_portal_config")
    suite.ok("PC-12.portal_config_status", code == 200, str(body)[:200])
    m = msg(body) or {}
    if isinstance(m, dict):
        m = m.get("data", m)
    suite.ok("PC-12.portal_config_has_visibility_flags",
             isinstance(m, dict) and any(
                 k in m for k in
                 ("show_dashboard", "show_reports", "enable_public_dashboard")
             ),
             str(m)[:200])

    # ----- PC-13 GAP — no public citizen-comment endpoint -------------
    # We assert by attempting a few likely paths; all should 404/405.
    gap_paths = [
        "/api/method/egrm.api.public_submit.append_citizen_comment",
        "/api/method/egrm.api.public_tracking.add_comment",
        "/api/method/egrm.api.public_submit.add_citizen_comment",
    ]
    not_found = 0
    for p in gap_paths:
        code, _ = post(s, p, data={"tracking_code": tracking_code or "X"})
        if code in (404, 405):
            not_found += 1
    suite.ok("PC-13.documented_gap_no_public_comment_endpoint",
             not_found == len(gap_paths),
             f"unexpectedly resolved {len(gap_paths) - not_found} of these paths")

    # ----- PC-14 staff resolves the issue, then re-track --------------
    if issue_name and tracking_code:
        s2 = requests.Session()
        code, body = login(s2, *ACTOR_RESOLVER)
        if code == 200:
            code, body = post(
                s2,
                "/api/method/egrm.api.issue.resolve",
                data={
                    "issue_id": issue_name,
                    "resolution_text": "AQE PC-14 — automated resolution.",
                },
            )
            suite.ok("PC-14.resolve_endpoint_no_5xx",
                     code < 500, f"got={code} body={str(body)[:200]}")

            time.sleep(0.5)

            code, body = get(s, "/api/method/egrm.api.public_tracking.track_complaint",
                             params={"tracking_code": tracking_code})
            m = msg(body) or {}
            td = (m or {}).get("data", {}) if isinstance(m, dict) else {}
            suite.ok("PC-14.retrack_after_resolve_status_present",
                     isinstance(td, dict) and bool(td.get("status")),
                     f"td={td}")
            logout(s2)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
