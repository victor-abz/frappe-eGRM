"""SUITE: API contract — envelope shape, idempotency, method discipline.

Asserts on every endpoint:
  - Frappe wraps responses under `message`
  - public_* endpoints return `{"status":..., "data":..., "message":...}`
  - GETs are idempotent
  - POST endpoints reject GET (405)
  - sync.pull_changes returns the expected `changes` table set
  - sync.push_changes returns `file_urls` shape
  - error responses use the documented envelope (no bare 500 strings)

Prereq: ONBOARDING + at least one PUBLIC-CITIZEN submit.
"""
from __future__ import annotations

import json
import sys

import requests

from _common import (
    ACTOR_GRM_OFFICER, PROJECT_RW, SuiteRun, SITE, get, load_wizard_state,
    login, logout, msg, post, run, state_for, summary,
)


EXPECTED_PULL_TABLES = {
    "grm_issues",
    "grm_issue_comments",
    "grm_issue_logs",
    "grm_issue_attachments",
    "grm_administrative_regions",
    "grm_administrative_level_types",
    "grm_issue_statuses",
    "grm_issue_categories",
    "grm_issue_types",
    "grm_issue_age_groups",
    "grm_issue_citizen_groups",
}


def main() -> int:
    suite = SuiteRun("API-CONTRACT")

    rw = state_for(PROJECT_RW)
    if not rw:
        suite.ok("API-0.RW_state_present", False,
                 "ONBOARDING suite must run first")
        return summary(suite)

    # ---- API-1 Frappe envelope on a public GET -------------------------
    s = requests.Session()
    code, body = get(s, "/api/method/egrm.api.public_submit.get_submission_config")
    suite.ok("API-1.envelope_message_key",
             isinstance(body, dict) and "message" in body,
             f"keys={list(body.keys()) if isinstance(body, dict) else body}")

    # ---- API-2 status + data envelope on public_* ----------------------
    m = msg(body) or {}
    if isinstance(m, dict):
        m_data = m.get("data", m)
        suite.ok("API-2.public_endpoint_has_status_or_data",
                 isinstance(m_data, dict),
                 f"m={str(m)[:200]}")

    # ---- API-6 idempotent GETs ----------------------------------------
    c1, b1 = get(s, "/api/method/egrm.api.public_submit.get_submission_options",
                 params={"project": rw["project_name"]})
    c2, b2 = get(s, "/api/method/egrm.api.public_submit.get_submission_options",
                 params={"project": rw["project_name"]})
    raw1 = json.dumps(b1, sort_keys=True, default=str)
    raw2 = json.dumps(b2, sort_keys=True, default=str)
    suite.ok("API-6.options_get_is_idempotent",
             c1 == 200 and c2 == 200 and raw1 == raw2,
             f"len1={len(raw1)} len2={len(raw2)} eq={raw1 == raw2}")

    # ---- API-7 POST endpoint rejects GET --------------------------------
    code, body = get(s, "/api/method/egrm.api.public_submit.submit_grievance",
                     params={"project": rw["project_name"]})
    # Frappe may answer 405 (Method Not Allowed) or wrap in a 417/error
    # envelope; assert the call did NOT silently succeed.
    m = msg(body) or {}
    suite.ok("API-7.submit_via_get_not_success",
             not (isinstance(m, dict) and m.get("status") == "success"),
             f"http={code} body={str(body)[:200]}")

    # ---- API-9 error envelope shape -------------------------------------
    code, body = get(s, "/api/method/egrm.api.public_tracking.track_complaint",
                     params={"tracking_code": "DOES-NOT-EXIST-XYZ"})
    m = msg(body) or {}
    suite.ok("API-9.error_response_has_documented_shape",
             isinstance(m, dict) and m.get("status") == "error"
             and isinstance(m.get("message", ""), str),
             f"got={m}")

    # ---- Authenticated checks for sync ----------------------------------
    s2 = requests.Session()
    code, body = login(s2, *ACTOR_GRM_OFFICER)
    suite.ok("API-0.officer_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])

    # ---- API-3 lookup.user_context envelope -----------------------------
    code, body = get(s2, "/api/method/egrm.api.lookup.user_context")
    m = msg(body) or {}
    if isinstance(m, dict):
        m = m.get("data", m)
    suite.ok("API-3.user_context_has_accessible_projects",
             isinstance(m, dict) and "accessible_projects" in m,
             f"keys={list(m.keys()) if isinstance(m, dict) else m}")

    # ---- API-4 sync.pull_changes envelope -------------------------------
    code, body = get(s2, "/api/method/egrm.api.sync.pull_changes",
                     params={"lastPulledAt": "", "schemaVersion": "1",
                             "migration": "null"})
    m = msg(body) or {}
    if isinstance(m, dict):
        changes = m.get("changes", {})
    else:
        changes = {}
    actual_tables = set(changes.keys()) if isinstance(changes, dict) else set()
    missing = EXPECTED_PULL_TABLES - actual_tables
    suite.ok("API-4.pull_changes_envelope_has_expected_tables",
             not missing,
             f"missing={missing} got={actual_tables}")

    # ---- API-5 sync.push_changes returns file_urls ---------------------
    code, body = post(
        s2, "/api/method/egrm.api.sync.push_changes",
        json_body={"changes": {}, "lastPulledAt": 0},
    )
    m = msg(body) or {}
    if isinstance(m, dict):
        file_urls = m.get("file_urls", None)
    else:
        file_urls = None
    suite.ok("API-5.push_changes_response_has_file_urls",
             isinstance(file_urls, dict),
             f"got_type={type(file_urls).__name__} body={str(body)[:200]}")

    # ---- API-10 attachment URLs prefix --------------------------------
    # Uploaded attachments must surface under /files/. We don't necessarily
    # have an attachment in the seed yet; just assert URLs that DO appear
    # follow the convention.
    bad_urls = []
    pull_attach = (m or {}).get("changes", {}) if isinstance(m, dict) else {}
    if not isinstance(pull_attach, dict):
        pull_attach = {}
    # try a fresh pull
    code, body = get(s2, "/api/method/egrm.api.sync.pull_changes",
                     params={"lastPulledAt": "", "schemaVersion": "1",
                             "migration": "null"})
    pm = msg(body) or {}
    attachs = (pm.get("changes", {}) if isinstance(pm, dict) else {}) \
        .get("grm_issue_attachments", {})
    for row in (attachs or {}).get("created", []) + (attachs or {}).get("updated", []):
        url = (row or {}).get("file_url") or ""
        if url and not url.startswith("/files/") and not url.startswith("/private/files/"):
            bad_urls.append(url)
    suite.ok("API-10.attachment_urls_under_files_prefix",
             not bad_urls,
             f"non-conforming={bad_urls}")

    logout(s2)
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
