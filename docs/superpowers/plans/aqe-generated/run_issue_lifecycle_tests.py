"""SUITE: Issue lifecycle — create / assign / escalate / resolve / reopen / appeal / comments.

Targets: egrm/api/issue.py + GRMIssue controller hooks +
egrm.server_scripts.issue_actions (which append GRM Issue Comment +
GRM Issue Log rows on every transition).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import requests

from _common import (
    ACTOR_GRM_OFFICER, ACTOR_PROJECT_ADMIN, ACTOR_RESOLVER,
    ACTOR_TRIAGE_OFFICER, ART, SuiteRun, get, login, logout, msg, post,
    run, summary,
)


def _load_first_state() -> dict | None:
    p = ART / "wizard_state.json"
    if not p.exists():
        return None
    states = json.loads(p.read_text())
    return states[0] if states else None


def _seed_one_issue(s: requests.Session, suite: SuiteRun, project: str,
                    category: str, issue_type: str, region: str,
                    initial_status: str) -> str | None:
    """Use mobile push path to create + auto-submit a real issue."""
    issue_id = uuid.uuid4().hex[:14]
    now_ms = int(time.time() * 1000)
    payload = {
        "changes": {
            "grm_issues": {
                "created": [{
                    "id": issue_id,
                    "creation": now_ms, "modified": now_ms,
                    "tracking_code": None,
                    "status": initial_status,
                    "project": project,
                    "category": category, "issue_type": issue_type,
                    "description": "<p>AQE IL — lifecycle seed.</p>",
                    "reporter": ACTOR_GRM_OFFICER[0],
                    "administrative_region": region,
                    "intake_date": now_ms, "issue_date": now_ms,
                    "citizen_type": "Visible",
                    "citizen": "AQE IL Citizen",
                    "gender": "female", "contact_medium": "facilitator",
                }],
                "updated": [], "deleted": [],
            },
        },
        "lastPulledAt": 0,
    }
    code, body = post(s, "/api/method/egrm.api.sync.push_changes",
                      json_body=payload, timeout=60)
    if code != 200:
        suite.ok("IL.seed_push", False, f"http={code} body={str(body)[:200]}")
        return None

    # Resolve the server-side name from the next pull_changes
    code, body = get(s, "/api/method/egrm.api.sync.pull_changes",
                     params={"lastPulledAt": "", "schemaVersion": "1",
                             "migration": "null"})
    pull = msg(body) or {}
    issues = pull.get("changes", {}).get("grm_issues", {}).get("created", [])
    found = next((i for i in issues if i.get("id") == issue_id), None)
    suite.ok("IL.seed_readback", found is not None,
             f"could not find seeded issue id={issue_id}")
    return found.get("name") if found else None


def main() -> int:
    suite = SuiteRun("ISSUE-LIFECYCLE")

    state = _load_first_state()
    if not state:
        suite.ok("IL-0.wizard_state_present", False,
                 "ONBOARDING suite must run first")
        return summary(suite)

    project = state.get("project_name") or state.get("code")

    # Officer login (Intake duty) — seed the issue
    s = requests.Session()
    code, body = login(s, *ACTOR_GRM_OFFICER)
    suite.ok("IL-0.officer_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])

    # Pick category, type, region, initial status from REST list
    def _first(doctype, extra_filters=None, fields=None):
        f = [["project", "=", project]]
        if extra_filters:
            f.extend(extra_filters)
        c, b = get(
            s, f"/api/resource/{doctype.replace(' ', '%20')}",
            params={
                "filters": json.dumps(f),
                "fields": json.dumps(fields or ["name"]),
                "limit_page_length": 1,
            },
        )
        rows = (msg(b) or {}).get("data") if isinstance(b, dict) else []
        return rows[0] if rows else None

    cat = _first("GRM Issue Category")
    itype = _first("GRM Issue Type")
    region = _first("GRM Administrative Region")
    init = _first("GRM Issue Status", [["initial_status", "=", 1]])

    if not (cat and itype and region and init):
        suite.ok("IL-0.lookups_present", False,
                 f"cat={cat} itype={itype} region={region} init={init}")
        return summary(suite)

    issue_name = _seed_one_issue(
        s, suite, project, cat["name"], itype["name"],
        region["name"], init["name"],
    )
    if not issue_name:
        return summary(suite)
    suite.ok("IL-1.issue_created", bool(issue_name), f"name={issue_name}")

    logout(s)

    # IL-2 — staff comment via sync push (triage/dept user) -----------
    s2 = requests.Session()
    login(s2, *ACTOR_TRIAGE_OFFICER)

    comment_id = uuid.uuid4().hex[:14]
    now_ms = int(time.time() * 1000)
    payload = {
        "changes": {
            "grm_issue_comments": {
                "created": [{
                    "id": comment_id,
                    "creation": now_ms, "modified": now_ms,
                    "grm_issue": issue_name,
                    "comment_text": "AQE IL-2 staff comment from triage.",
                    "comment_by": ACTOR_TRIAGE_OFFICER[0],
                    "comment_date": now_ms,
                }],
                "updated": [], "deleted": [],
            },
        },
        "lastPulledAt": 0,
    }
    code, body = post(s2, "/api/method/egrm.api.sync.push_changes",
                      json_body=payload, timeout=60)
    suite.ok("IL-2.staff_comment_push_status",
             code == 200, f"http={code} body={str(body)[:200]}")

    # IL-4 — assign via REST endpoint -----------------------------------
    code, body = post(
        s2, "/api/method/egrm.api.issue.assign",
        data={"issue_id": issue_name, "assignee_id": ACTOR_RESOLVER[0]},
    )
    suite.ok("IL-4.assign_no_5xx", code < 500,
             f"http={code} body={str(body)[:200]}")
    logout(s2)

    # IL-5 — escalate (resolver) ---------------------------------------
    s3 = requests.Session()
    login(s3, *ACTOR_RESOLVER)
    code, body = post(
        s3, "/api/method/egrm.api.issue.escalate",
        data={"issue_id": issue_name, "reason": "AQE IL-5 escalation."},
    )
    suite.ok("IL-5.escalate_no_5xx", code < 500,
             f"http={code} body={str(body)[:200]}")

    # IL-6 — resolve ----------------------------------------------------
    code, body = post(
        s3, "/api/method/egrm.api.issue.resolve",
        data={"issue_id": issue_name,
              "resolution_text": "AQE IL-6 — automated resolution."},
    )
    suite.ok("IL-6.resolve_no_5xx", code < 500,
             f"http={code} body={str(body)[:200]}")

    # IL-7 — reopen -----------------------------------------------------
    code, body = post(
        s3, "/api/method/egrm.api.issue.reopen",
        data={"issue_id": issue_name,
              "reason": "AQE IL-7 — automated reopen."},
    )
    suite.ok("IL-7.reopen_no_5xx", code < 500,
             f"http={code} body={str(body)[:200]}")
    logout(s3)

    # IL-11 — cancel by Supervise admin --------------------------------
    s4 = requests.Session()
    login(s4, *ACTOR_PROJECT_ADMIN)
    # cancel via Frappe REST cancel endpoint
    code, body = post(
        s4, "/api/method/frappe.client.cancel",
        data={"doctype": "GRM Issue", "name": issue_name},
    )
    suite.ok("IL-11.cancel_no_5xx", code < 500,
             f"http={code} body={str(body)[:200]}")
    logout(s4)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
