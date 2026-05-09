"""SUITE: Mobile / duty-driven flows across all 3 wizard-created projects.

Re-asserts the ACT 13/14/15 mobile contract against the projects
created by run_onboarding_tests.py.

Targets: egrm/api/sync.py, egrm/api/lookup.py, egrm/api/issue.py.
"""
from __future__ import annotations

import base64
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


PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8Dw"
    "HwAFAAH/q842iQAAAABJRU5ErkJggg=="
)
OGG_TINY_BASE64 = base64.b64encode(b"OggS" + b"\x00" * 28).decode("ascii")


def _load_wizard_state() -> list[dict]:
    p = ART / "wizard_state.json"
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _pick_lookup_id(s, project: str, doctype: str, fields: list[str]) -> dict | None:
    """Pull the first record of `doctype` for `project` via REST list."""
    code, body = get(
        s, f"/api/resource/{doctype.replace(' ', '%20')}",
        params={
            "filters": json.dumps([["project", "=", project]]),
            "fields": json.dumps(["name"] + fields),
            "limit_page_length": 50,
        },
    )
    if code != 200:
        return None
    rows = (msg(body) or {}).get("data") if isinstance(body, dict) else []
    return rows[0] if rows else None


def main() -> int:
    suite = SuiteRun("MOBILE-DUTY")
    states = _load_wizard_state()
    if not states:
        suite.ok("MD-0.wizard_state_present", False,
                 "ONBOARDING suite must run first")
        return summary(suite)

    s = requests.Session()
    code, body = login(s, *ACTOR_GRM_OFFICER)
    suite.ok("MD-0.officer_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])

    # MD-1 lookup envelope ---------------------------------------------
    code, body = get(s, "/api/method/egrm.api.lookup.user_context")
    m = msg(body) or {}
    if isinstance(m, dict) and "data" in m:
        m = m["data"]
    suite.ok("MD-1.user_context_envelope",
             isinstance(m, dict)
             and {"user", "accessible_projects", "permissions"}.issubset(set(m.keys())),
             f"keys={list(m.keys()) if isinstance(m, dict) else m}")

    # MD-2 initial pull ------------------------------------------------
    code, body = get(
        s, "/api/method/egrm.api.sync.pull_changes",
        params={"lastPulledAt": "", "schemaVersion": "1", "migration": "null"},
        timeout=60,
    )
    suite.ok("MD-2.initial_pull_status", code == 200, str(body)[:200])
    pull = msg(body) or {}
    changes = (pull or {}).get("changes", {}) if isinstance(pull, dict) else {}
    expected_tables = {
        "grm_projects", "grm_administrative_regions",
        "grm_issue_categories", "grm_issue_types",
        "grm_issue_statuses", "grm_issue_age_groups",
        "grm_issue_citizen_groups", "grm_issue_departments",
        "grm_issues", "grm_issue_attachments",
    }
    suite.ok("MD-2.pull_has_all_required_tables",
             expected_tables.issubset(set(changes.keys())),
             f"missing={expected_tables - set(changes.keys())}")

    # Pick the first project we have categories+types+region+initial_status for.
    chosen = None
    for st in states:
        proj = st.get("project_name") or st.get("code")
        cat = _pick_lookup_id(s, proj, "GRM Issue Category", ["category_name"])
        itype = _pick_lookup_id(s, proj, "GRM Issue Type", ["type_name"])
        region = None
        for rname, rid in (st.get("regions") or {}).items():
            # prefer the deepest region (last in the layout list)
            region = {"name": rid, "region_name": rname}
        # pick initial status
        code, body = get(
            s, "/api/resource/GRM Issue Status",
            params={
                "filters": json.dumps([["project", "=", proj],
                                       ["initial_status", "=", 1]]),
                "fields": json.dumps(["name"]),
                "limit_page_length": 1,
            },
        )
        rows = (msg(body) or {}).get("data") if isinstance(body, dict) else []
        if cat and itype and region and rows:
            chosen = {
                "project": proj,
                "category": cat["name"],
                "issue_type": itype["name"],
                "region": region["name"],
                "initial_status": rows[0]["name"],
            }
            break
    suite.ok("MD-3.found_project_with_full_lookups",
             chosen is not None,
             f"checked {len(states)} projects")

    if not chosen:
        return summary(suite)

    # MD-3 sync push w/ image+audio (1 issue, 2 attachments) -----------
    issue_id = uuid.uuid4().hex[:14]
    img_id = uuid.uuid4().hex[:14]
    aud_id = uuid.uuid4().hex[:14]
    now_ms = int(time.time() * 1000)

    payload = {
        "changes": {
            "grm_issues": {
                "created": [{
                    "id": issue_id,
                    "creation": now_ms,
                    "modified": now_ms,
                    "tracking_code": None,
                    "status": chosen["initial_status"],
                    "project": chosen["project"],
                    "category": chosen["category"],
                    "issue_type": chosen["issue_type"],
                    "description": (
                        "<p>AQE MOBILE-DUTY automated push — image + audio "
                        "attachments. Project: " + chosen["project"] + ".</p>"
                    ),
                    "reporter": ACTOR_GRM_OFFICER[0],
                    "administrative_region": chosen["region"],
                    "intake_date": now_ms,
                    "issue_date": now_ms,
                    "citizen_type": "Visible",
                    "citizen": "AQE Mobile-Duty Citizen",
                    "gender": "female",
                    "contact_medium": "facilitator",
                }],
                "updated": [], "deleted": [],
            },
            "grm_issue_attachments": {
                "created": [
                    {
                        "id": img_id, "creation": now_ms, "modified": now_ms,
                        "grm_issue": issue_id, "attachment": "",
                        "file_name": "aqe-photo.png",
                        "local_url": "file:///mobile/cache/aqe-photo.png",
                        "uploaded": False,
                        "file_data": PNG_1X1_BASE64,
                        "needs_upload": True,
                    },
                    {
                        "id": aud_id, "creation": now_ms, "modified": now_ms,
                        "grm_issue": issue_id, "attachment": "",
                        "file_name": "aqe-voice.ogg",
                        "local_url": "file:///mobile/cache/aqe-voice.ogg",
                        "uploaded": False,
                        "file_data": OGG_TINY_BASE64,
                        "needs_upload": True,
                    },
                ],
                "updated": [], "deleted": [],
            },
        },
        "lastPulledAt": 0,
    }
    code, body = post(s, "/api/method/egrm.api.sync.push_changes",
                      json_body=payload, timeout=120)
    suite.ok("MD-3.push_status", code == 200, str(body)[:300])
    m = msg(body) or {}
    file_urls = (m or {}).get("file_urls", {}).get("grm_issue_attachments", {}) \
        if isinstance(m, dict) else {}
    suite.ok("MD-3.image_url_returned", img_id in file_urls,
             f"file_urls={file_urls}")
    suite.ok("MD-3.audio_url_returned", aud_id in file_urls,
             f"file_urls={file_urls}")

    # MD-10 readback via pull_changes ----------------------------------
    code, body = get(
        s, "/api/method/egrm.api.sync.pull_changes",
        params={"lastPulledAt": "", "schemaVersion": "1", "migration": "null"},
        timeout=60,
    )
    pull = msg(body) or {}
    changes = (pull or {}).get("changes", {}) if isinstance(pull, dict) else {}
    issues = changes.get("grm_issues", {}).get("created", [])
    suite.ok("MD-10.issue_in_pull",
             any(i.get("id") == issue_id for i in issues),
             f"count={len(issues)} my_id={issue_id}")

    logout(s)
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
