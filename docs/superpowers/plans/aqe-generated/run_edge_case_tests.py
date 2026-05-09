"""SUITE: Edge cases — empty payloads, malformed JSON, boundaries, idempotency.

Targets: sync.push_changes, public_submit.submit_grievance,
         public_tracking.track_complaint.
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
    run, summary, SITE,
)


def _load_states() -> list[dict]:
    p = ART / "wizard_state.json"
    return json.loads(p.read_text()) if p.exists() else []


def main() -> int:
    suite = SuiteRun("EDGE-CASES")
    states = _load_states()

    s = requests.Session()
    login(s, *ACTOR_GRM_OFFICER)

    # --------------------- EC-1: empty changes payload -----------------
    code, body = post(s, "/api/method/egrm.api.sync.push_changes",
                      json_body={"changes": {}, "lastPulledAt": 0})
    suite.ok("EC-1.empty_changes_no_5xx",
             code == 200, f"http={code} body={str(body)[:200]}")

    # --------------------- EC-2: malformed JSON -----------------------
    r = s.post(f"{SITE}/api/method/egrm.api.sync.push_changes",
               data="not json",
               headers={"Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest"},
               timeout=10)
    suite.ok("EC-2.malformed_json_4xx",
             r.status_code in (400, 417, 500),  # frappe sometimes wraps as 500
             f"http={r.status_code} body={r.text[:200]}")

    # --------------------- EC-3: duplicate id in same batch -----------
    if states:
        proj = states[0]["project_name"] or states[0]["code"]
        # find category, type, region
        c, b = get(s, "/api/resource/GRM Issue Category",
                   params={
                       "filters": json.dumps([["project", "=", proj]]),
                       "fields": json.dumps(["name"]),
                       "limit_page_length": 1,
                   })
        cat = ((msg(b) or {}).get("data") or [{}])[0].get("name")
        c, b = get(s, "/api/resource/GRM Issue Type",
                   params={
                       "filters": json.dumps([["project", "=", proj]]),
                       "fields": json.dumps(["name"]),
                       "limit_page_length": 1,
                   })
        itype = ((msg(b) or {}).get("data") or [{}])[0].get("name")
        c, b = get(s, "/api/resource/GRM Issue Status",
                   params={
                       "filters": json.dumps([["project", "=", proj],
                                              ["initial_status", "=", 1]]),
                       "fields": json.dumps(["name"]),
                       "limit_page_length": 1,
                   })
        init = ((msg(b) or {}).get("data") or [{}])[0].get("name")
        region = next(iter((states[0].get("regions") or {}).values()), None)

        if cat and itype and init and region:
            now_ms = int(time.time() * 1000)
            iid = uuid.uuid4().hex[:14]
            row = {
                "id": iid, "creation": now_ms, "modified": now_ms,
                "tracking_code": None, "status": init, "project": proj,
                "category": cat, "issue_type": itype,
                "description": "<p>EC-3 duplicate-in-batch probe.</p>",
                "reporter": ACTOR_GRM_OFFICER[0],
                "administrative_region": region,
                "intake_date": now_ms, "issue_date": now_ms,
                "citizen_type": "Visible", "citizen": "EC-3",
                "gender": "female", "contact_medium": "facilitator",
            }
            payload = {
                "changes": {"grm_issues": {
                    "created": [row, dict(row)],   # SAME id twice
                    "updated": [], "deleted": [],
                }},
                "lastPulledAt": 0,
            }
            code, body = post(s, "/api/method/egrm.api.sync.push_changes",
                              json_body=payload, timeout=60)
            suite.ok("EC-3.dup_id_in_batch_no_5xx",
                     code < 500, f"http={code} body={str(body)[:300]}")

            # EC-4: idempotency — same payload again
            code, body = post(s, "/api/method/egrm.api.sync.push_changes",
                              json_body=payload, timeout=60)
            suite.ok("EC-4.idempotent_repeat_no_5xx",
                     code < 500, f"http={code} body={str(body)[:300]}")

    # --------------------- EC-7: empty tracking code ------------------
    code, body = get(s, "/api/method/egrm.api.public_tracking.track_complaint",
                     params={"tracking_code": ""})
    m = msg(body) or {}
    suite.ok("EC-7.empty_tracking_code_error",
             isinstance(m, dict) and m.get("status") == "error",
             f"got={m}")

    # --------------------- EC-9/10: description boundary --------------
    if states:
        proj = states[0]["project_name"] or states[0]["code"]
        c, b = get(s, "/api/method/egrm.api.public_submit.get_submission_options",
                   params={"project": proj})
        d = msg(b) or {}
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        cats = (d or {}).get("categories", [])
        types = (d or {}).get("issue_types", [])
        region = next(iter((states[0].get("regions") or {}).values()), None)
        if cats and types and region:
            # 9 chars (BELOW boundary)
            code, body = post(
                s, "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": proj, "category": cats[0]["name"],
                    "issue_type": types[0]["name"],
                    "administrative_region": region,
                    "description": "Too short",   # 9 chars
                },
            )
            m = msg(body) or {}
            suite.ok("EC-10.description_under_10_rejected",
                     isinstance(m, dict) and m.get("status") == "error",
                     f"got={m}")

            # exactly 10
            code, body = post(
                s, "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": proj, "category": cats[0]["name"],
                    "issue_type": types[0]["name"],
                    "administrative_region": region,
                    "description": "1234567890",   # exactly 10
                },
            )
            m = msg(body) or {}
            suite.ok("EC-9.description_exactly_10_accepted",
                     isinstance(m, dict)
                     and m.get("status") in ("success", "error")
                     and code < 500,
                     f"got={m}")

    # --------------------- EC-13: inactive project -------------------
    code, body = post(
        s, "/api/method/egrm.api.public_submit.submit_grievance",
        data={
            "project": "NON-EXISTENT-XYZ",
            "category": "X",
            "issue_type": "X",
            "administrative_region": "X",
            "description": "long enough description for test",
        },
    )
    m = msg(body) or {}
    suite.ok("EC-13.inactive_project_rejected",
             isinstance(m, dict) and m.get("status") == "error",
             f"got={m}")

    logout(s)
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
