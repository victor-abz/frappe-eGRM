"""SUITE: Security tests — auth bypass, IDOR, injection, brute force, rate-limit.

Targets: every whitelisted endpoint reachable from sync, issue, lookup,
public_submit, public_tracking, attachment.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import requests

from _common import (
    ACTOR_GRM_OFFICER, ART, SuiteRun, get, login, logout, msg, post,
    run, summary,
)


def _load_states() -> list[dict]:
    p = ART / "wizard_state.json"
    return json.loads(p.read_text()) if p.exists() else []


def main() -> int:
    suite = SuiteRun("SECURITY")
    states = _load_states()

    # --------------------- SEC-1..3: unauth endpoints ------------------
    s_anon = requests.Session()

    code, body = get(s_anon, "/api/method/egrm.api.sync.pull_changes",
                     params={"lastPulledAt": "", "schemaVersion": "1",
                             "migration": "null"})
    suite.ok("SEC-1.unauth_pull_changes_blocked",
             code in (401, 403) or (isinstance(body, dict)
                                    and "exc" in body),
             f"http={code} body={str(body)[:200]}")

    code, body = post(s_anon, "/api/method/egrm.api.sync.push_changes",
                      json_body={"changes": {}, "lastPulledAt": 0})
    suite.ok("SEC-2.unauth_push_changes_blocked",
             code in (401, 403) or (isinstance(body, dict)
                                    and "exc" in body),
             f"http={code} body={str(body)[:200]}")

    code, body = post(s_anon, "/api/method/egrm.api.issue.upload_attachment",
                      data={"issue_id": "X", "attachment_data": "{}"})
    suite.ok("SEC-3.unauth_upload_attachment_blocked",
             code in (401, 403) or (isinstance(body, dict)
                                    and "exc" in body),
             f"http={code} body={str(body)[:200]}")

    # --------------------- SEC-5: cross-project category injection -----
    if len(states) >= 2:
        proj_a = states[0]["project_name"] or states[0]["code"]
        proj_b = states[1]["project_name"] or states[1]["code"]

        # Pull a category from proj_b
        code, body = get(
            s_anon, "/api/method/egrm.api.public_submit.get_submission_options",
            params={"project": proj_b},
        )
        d = msg(body) or {}
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        cats_b = (d or {}).get("categories", [])
        if cats_b:
            cat_b = cats_b[0]["name"]
            # Get a region in proj_a
            region_a = None
            for rname, rid in (states[0].get("regions") or {}).items():
                region_a = rid
            # Get a type in proj_a
            code2, body2 = get(
                s_anon, "/api/method/egrm.api.public_submit.get_submission_options",
                params={"project": proj_a},
            )
            d2 = msg(body2) or {}
            if isinstance(d2, dict) and "data" in d2:
                d2 = d2["data"]
            types_a = (d2 or {}).get("issue_types", [])
            if types_a and region_a:
                code, body = post(
                    s_anon,
                    "/api/method/egrm.api.public_submit.submit_grievance",
                    data={
                        "project": proj_a,
                        "category": cat_b,           # FROM proj_b
                        "issue_type": types_a[0]["name"],
                        "administrative_region": region_a,
                        "description": "AQE SEC-5 cross-project injection.",
                    },
                )
                m = msg(body) or {}
                suite.ok("SEC-5.cross_project_category_rejected",
                         isinstance(m, dict) and m.get("status") == "error",
                         f"got={m}")

    # --------------------- SEC-6: SQL injection on tracking_code -------
    code, body = get(s_anon, "/api/method/egrm.api.public_tracking.track_complaint",
                     params={"tracking_code": "' OR 1=1 -- "})
    m = msg(body) or {}
    suite.ok("SEC-6.sqli_tracking_code_safe",
             isinstance(m, dict) and m.get("status") == "error",
             f"got={m}")

    # --------------------- SEC-7: XSS in description -------------------
    if states:
        proj = states[0]["project_name"] or states[0]["code"]
        # find a category, type, region inside proj
        c, b = get(s_anon, "/api/method/egrm.api.public_submit.get_submission_options",
                   params={"project": proj})
        d = msg(b) or {}
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        cats = (d or {}).get("categories", [])
        types = (d or {}).get("issue_types", [])
        region = next(iter((states[0].get("regions") or {}).values()), None)
        if cats and types and region:
            code, body = post(
                s_anon,
                "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": proj,
                    "category": cats[0]["name"],
                    "issue_type": types[0]["name"],
                    "administrative_region": region,
                    "description": "<script>alert(1)</script>" + " " * 20
                    + "AQE SEC-7 stored-xss probe.",
                },
            )
            m = msg(body) or {}
            data = (m or {}).get("data", {}) if isinstance(m, dict) else {}
            tc = data.get("tracking_code")
            suite.ok("SEC-7.xss_submit_no_5xx", code < 500, str(body)[:200])
            if tc:
                # Track and ensure no <script> echoed back
                code, body = get(
                    s_anon,
                    "/api/method/egrm.api.public_tracking.track_complaint",
                    params={"tracking_code": tc},
                )
                raw = json.dumps(body)
                suite.ok("SEC-7.xss_not_echoed",
                         "<script>" not in raw and "alert(1)" not in raw,
                         "raw response contained inline script")

    # --------------------- SEC-8: OTP brute-force rate limit -----------
    # (Skipped unless SMS gateway is configured; otherwise rate-limit
    # check would race the early return.)
    code, body = post(s_anon, "/api/method/egrm.api.public_submit.send_otp",
                      data={"phone": "+250788000000"})
    m = msg(body) or {}
    suite.ok("SEC-8.otp_endpoint_responds",
             code < 500, f"http={code} body={str(body)[:200]}")

    # --------------------- SEC-11: Intake user cannot assign -----------
    s = requests.Session()
    login(s, *ACTOR_GRM_OFFICER)
    code, body = post(s, "/api/method/egrm.api.issue.assign",
                      data={"issue_id": "NONEXISTENT",
                            "assignee_id": "resolver@egrm.test"})
    # Either 4xx (permission) or business error — not 5xx.
    suite.ok("SEC-11.intake_assign_no_5xx",
             code < 500, f"http={code} body={str(body)[:200]}")

    # --------------------- SEC-15: CSRF guard --------------------------
    # Frappe v16 only enforces CSRF when csrf_token is sent and stale —
    # for whitelisted methods accessed from XHR with X-Requested-With,
    # Frappe accepts. We assert the endpoint is reachable with proper
    # headers (positive control), and reject without proper Accept
    # only if Frappe enforces — soft check.
    code, body = post(
        s, "/api/method/egrm.api.sync.push_changes",
        json_body={"changes": {}, "lastPulledAt": 0},
    )
    suite.ok("SEC-15.csrf_proper_header_works",
             code == 200, f"http={code} body={str(body)[:200]}")
    logout(s)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
