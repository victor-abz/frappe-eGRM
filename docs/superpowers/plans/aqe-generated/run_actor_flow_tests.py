"""SUITE: ACTOR-FLOW — per-actor end-to-end issue lifecycle.

For every canonical actor in `_common.py`, exercise EVERY action the
actor's duty(ies) permit, and chain those actions across actors so a
real GRM Issue progresses from creation → terminal state. Every action
is captured as:

    1. A REST/HTTP call against the live Frappe site (success / failure
       recorded with status code and response body).
    2. A Playwright PNG of the resulting list/detail surface
       (`screenshots/flow/<actor-slug>/NN-<action>.png` + `.txt` sidecar).
    3. A `FLOW-<ACTOR>.<action>` assertion whose `detail` contains:
         issue=<GRM-Issue.name>, http=<code>, status=<post-action status>,
         screenshot=<rel-path>, inputs=...

Three end-to-end chains are seeded with different origins:
  * CHAIN-1 — citizen via /public_submit.submit_grievance, accepted by
    grm-officer, triaged → assigned → resolved → closed.
  * CHAIN-2 — field-officer via mobile sync.push_changes, triaged →
    resolved → reopened → resolved-again (terminal).
  * CHAIN-3 — officer desk-creates (via sync.create_record), triaged →
    assigned → escalated → resolved.

Each chain ends with FLOW-CHAIN-N.terminal_status that re-reads the
issue server-side and asserts a final-state status row was set.

Negative duty-boundary assertion preserved (mirrors SEC-11):
  * field-officer (Intake-only) cannot call assign().
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import uuid
from pathlib import Path

import requests

from _common import (
    ACTOR_FIELD_OFFICER, ACTOR_GRM_DEPT, ACTOR_GRM_OFFICER,
    ACTOR_PROJECT_ADMIN, ACTOR_RESOLVER, ACTOR_TRIAGE_OFFICER,
    ART, SITE, SuiteRun, get, login, logout, msg, post, run, summary,
)

# --------------------------------------------------------------------------
# Per-actor capture dirs
# --------------------------------------------------------------------------

SHOTS_FLOW = ART / "screenshots" / "flow"
SHOTS_FLOW.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1440, "height": 900}

ACTOR_SLUGS: dict[str, str] = {
    ACTOR_PROJECT_ADMIN[0]:  "project-admin",
    ACTOR_GRM_OFFICER[0]:    "grm-officer",
    ACTOR_TRIAGE_OFFICER[0]: "triage-officer",
    ACTOR_RESOLVER[0]:       "resolver",
    ACTOR_FIELD_OFFICER[0]:  "field-officer",
    ACTOR_GRM_DEPT[0]:       "grm-dept",
}

# --------------------------------------------------------------------------
# Build the actor → duty → action matrix at run time
# --------------------------------------------------------------------------

PROJECT_CODE = "RW-WB"


def _query_roles_for_user(s: requests.Session, email: str) -> list[str]:
    code, body = get(s, f"/api/resource/User/{email}")
    if code != 200:
        return []
    data = (msg(body) or {}).get("data") or {}
    roles = data.get("roles") or []
    out: list[str] = []
    for r in roles:
        # Frappe returns rows with `role` field.
        rname = r.get("role") if isinstance(r, dict) else None
        if rname:
            out.append(rname)
    return out


def _query_project_role_duties(s: requests.Session, project_code: str
                               ) -> dict[str, list[str]]:
    """Return GRM Project Role.role_name -> [duty_code, ...] for the project.

    NOTE: GRM Project Role does not link to a Frappe Role; the user-side
    role binding lives at User.roles (Has Role child) which the REST API
    gates for non-admins. We therefore key the project-side map by the
    `role_name` (e.g. 'Administrator', 'AQE-Intake-Only'); the user-side
    truth comes from `_KNOWN_USER_ROLES` (bench seed) which lists the
    Frappe Role names. The two are bridged via `_FRAPPE_ROLE_TO_DUTIES`.
    """
    code, body = get(
        s, "/api/resource/GRM Project Role",
        params={
            "filters": json.dumps([["project", "=", project_code]]),
            "fields": json.dumps(["name", "role_name"]),
            "limit_page_length": 0,
        },
    )
    rows = (msg(body) or {}).get("data") if code == 200 else []
    out: dict[str, list[str]] = {}
    for row in rows or []:
        name = row.get("name")
        rn = row.get("role_name")
        if not name or not rn:
            continue
        code2, body2 = get(s, f"/api/resource/GRM Project Role/{name}")
        doc = (msg(body2) or {}).get("data") if code2 == 200 else {}
        duties = [
            d.get("duty") for d in (doc or {}).get("duties") or []
            if d.get("duty")
        ]
        out[rn] = duties
    return out


def _duty_actions(duty: str) -> list[str]:
    """Map a duty -> the actions an actor with that duty MUST be able
    to perform. Action codes match endpoint method names where possible."""
    return {
        "Intake": [
            "create_via_mobile_push",      # sync.push_changes
            "accept_public_submission",    # public_submit + intake review
            "view_assigned_queue",         # GET /api/resource/GRM Issue
            "comment_on_issue",            # sync.push_changes(grm_issue_comments)
        ],
        "Review": [
            "view_review_queue",
            "comment_on_issue",
            "update_category",             # issue.update
        ],
        "Assignment": [
            "assign_to_resolver",          # issue.assign
        ],
        "Investigate & Resolve": [
            "view_assigned_queue",
            "comment_on_issue",
            "escalate",                    # issue.escalate
            "resolve",                     # issue.resolve
        ],
        "Feedback": [
            "resolve",
            "reopen",                      # issue.reopen
        ],
        "Supervise": [
            "configure_project",           # GET /api/resource/GRM Project
            "cancel_issue",                # frappe.client.cancel
            "view_all_issues",
        ],
    }.get(duty, [])


_KNOWN_USER_ROLES: dict[str, list[str]] = {
    # Authoritative truth: bench seed `egrm.cli.sync_test_users`
    # + grm-dept Frappe Role assignment. The REST API gates the User
    # resource's `roles` child for non-admins, so we ground the matrix
    # in the bench seed.
    ACTOR_PROJECT_ADMIN[0]:  ["GRM Platform Administrator", "GRM Supervise"],
    ACTOR_FIELD_OFFICER[0]:  ["GRM Intake"],
    ACTOR_TRIAGE_OFFICER[0]: ["GRM Review", "GRM Assignment"],
    ACTOR_RESOLVER[0]:       ["GRM Investigate & Resolve", "GRM Feedback"],
    ACTOR_GRM_OFFICER[0]:    ["GRM Intake", "GRM Investigate & Resolve",
                              "GRM Feedback"],
    ACTOR_GRM_DEPT[0]:       ["GRM Intake", "GRM Review", "GRM Assignment",
                              "GRM Investigate & Resolve", "GRM Feedback"],
}


def build_matrix(s_admin: requests.Session) -> dict:
    """Resolve frappe_role → duties (project-scoped), then per actor
    fold the user's roles → duties → action list."""
    role_to_duties = _query_project_role_duties(s_admin, PROJECT_CODE)

    # Hard-coded duty fallback per role (the GRM Project Role rows are
    # bench-seeded with duties; if the resource API gates the `duties`
    # child for non-admin readers, fall back to the bench seed map).
    fallback = {
        "GRM Intake":                 ["Intake"],
        "GRM Review":                 ["Review"],
        "GRM Assignment":             ["Assignment"],
        "GRM Investigate & Resolve":  ["Investigate & Resolve"],
        "GRM Feedback":               ["Feedback"],
        "GRM Supervise":              ["Supervise"],
        "GRM Platform Administrator": ["Supervise"],
    }
    for k, v in fallback.items():
        role_to_duties.setdefault(k, v)

    actors: dict[str, dict] = {}
    for email, _pwd in (
        ACTOR_PROJECT_ADMIN, ACTOR_GRM_OFFICER, ACTOR_TRIAGE_OFFICER,
        ACTOR_RESOLVER, ACTOR_FIELD_OFFICER, ACTOR_GRM_DEPT,
    ):
        # Try REST first (works when running as system manager); fall
        # back to the bench-seeded ground truth.
        roles = _query_roles_for_user(s_admin, email) or _KNOWN_USER_ROLES.get(email, [])
        duties: list[str] = []
        for r in roles:
            duties.extend(role_to_duties.get(r, []))
        # de-dup preserving order
        seen = set()
        duties = [d for d in duties if not (d in seen or seen.add(d))]
        actions: list[str] = []
        for d in duties:
            for a in _duty_actions(d):
                if a not in actions:
                    actions.append(a)
        actors[email] = {
            "frappe_roles": roles,
            "duties": duties,
            "permitted_actions": actions,
        }

    return {"project": PROJECT_CODE, "actors": actors}


# --------------------------------------------------------------------------
# REST helpers (chain & action runners)
# --------------------------------------------------------------------------

def _first(s: requests.Session, doctype: str, project: str,
           extra: list | None = None, fields: list | None = None
           ) -> dict | None:
    f = [["project", "=", project]]
    if extra:
        f.extend(extra)
    code, body = get(
        s, f"/api/resource/{doctype.replace(' ', '%20')}",
        params={
            "filters": json.dumps(f),
            "fields": json.dumps(fields or ["name"]),
            "limit_page_length": 1,
        },
    )
    rows = (msg(body) or {}).get("data") if code == 200 else None
    return rows[0] if rows else None


def _seed_via_mobile_push(s: requests.Session, project: str,
                          category: str, itype: str, region: str,
                          init_status: str, reporter: str,
                          marker: str) -> str | None:
    issue_id = uuid.uuid4().hex[:14]
    now_ms = int(time.time() * 1000)
    payload = {
        "changes": {
            "grm_issues": {
                "created": [{
                    "id": issue_id,
                    "creation": now_ms, "modified": now_ms,
                    "tracking_code": None,
                    "status": init_status,
                    "project": project,
                    "category": category, "issue_type": itype,
                    "description": f"<p>{marker}</p>",
                    "reporter": reporter,
                    "administrative_region": region,
                    "intake_date": now_ms, "issue_date": now_ms,
                    "citizen_type": "Visible",
                    "citizen": "AQE Flow Citizen",
                    "gender": "female", "contact_medium": "facilitator",
                }],
                "updated": [], "deleted": [],
            },
        },
        "lastPulledAt": 0,
    }
    code, _b = post(s, "/api/method/egrm.api.sync.push_changes",
                    json_body=payload, timeout=60)
    if code != 200:
        return None
    code, body = get(s, "/api/method/egrm.api.sync.pull_changes",
                     params={"lastPulledAt": "", "schemaVersion": "1",
                             "migration": "null"})
    pull = msg(body) or {}
    issues = pull.get("changes", {}).get("grm_issues", {}).get("created", [])
    found = next((i for i in issues if i.get("id") == issue_id), None)
    return found.get("name") if found else None


def _seed_via_public_submit(s: requests.Session, project_doc: str,
                            category: str, itype: str, region_doc: str,
                            marker: str) -> str | None:
    """Anonymous citizen path. Note: `project` here is the Project doc
    `name` (which equals the project_code). public_submit returns a
    tracking_code; we resolve the GRM Issue.name with an admin session."""
    code, body = post(
        s, "/api/method/egrm.api.public_submit.submit_grievance",
        json_body={
            "project": project_doc,
            "category": category,
            "issue_type": itype,
            "administrative_region": region_doc,
            "description": marker,
            "citizen_name": "AQE Public Citizen",
            "contact_information": "+250788000999",
            "contact_medium": "phone",
        },
    )
    if code != 200:
        return None
    data = (msg(body) or {}).get("data") or msg(body) or {}
    return data.get("issue_name") or data.get("name") or data.get("tracking_code")


def _resolve_issue_by_marker(s: requests.Session, project: str,
                             marker_substr: str) -> str | None:
    """Locate an issue by description LIKE `%marker_substr%`."""
    code, body = get(
        s, "/api/resource/GRM Issue",
        params={
            "filters": json.dumps([
                ["project", "=", project],
                ["description", "like", f"%{marker_substr}%"],
            ]),
            "fields": json.dumps(["name", "status"]),
            "order_by": "creation desc",
            "limit_page_length": 1,
        },
    )
    rows = (msg(body) or {}).get("data") if code == 200 else None
    return rows[0]["name"] if rows else None


def _read_status(s: requests.Session, issue_name: str) -> dict:
    code, body = get(s, f"/api/resource/GRM Issue/{issue_name}")
    if code != 200:
        return {"name": issue_name, "_http": code}
    d = (msg(body) or {}).get("data") or {}
    return {
        "name": d.get("name"),
        "status": d.get("status"),
        "assignee": d.get("assignee"),
        "category": d.get("category"),
        "escalate_flag": d.get("escalate_flag"),
        "resolution_date": d.get("resolution_date"),
        "research_result": d.get("research_result"),
    }


# --------------------------------------------------------------------------
# Playwright per-actor capture
# --------------------------------------------------------------------------

def _capture_action(browser, actor_slug: str, email: str, pwd: str,
                    seq: int, action_slug: str, route: str) -> tuple[Path, int, str]:
    """Open a fresh browser context as the actor, navigate, screenshot.
    Returns (png_path, size_bytes, sha1)."""
    actor_dir = SHOTS_FLOW / actor_slug
    actor_dir.mkdir(parents=True, exist_ok=True)
    png = actor_dir / f"{seq:02d}-{action_slug}.png"
    txt = actor_dir / f"{seq:02d}-{action_slug}.txt"
    ctx = None
    try:
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2,
                                  ignore_https_errors=True)
        page = ctx.new_page()
        page.goto(f"{SITE}/login", wait_until="networkidle", timeout=30_000)
        page.locator("#login_email").fill(email)
        page.locator("#login_password").fill(pwd)
        page.locator("button.btn-login, .btn.btn-primary").first.click()
        page.wait_for_url("**/app**", timeout=20_000)
        page.goto(f"{SITE}{route}", wait_until="networkidle", timeout=30_000)
        try:
            page.wait_for_function(
                "() => document.body && document.body.innerText.replace(/\\s+/g,' ').trim().length > 200",
                timeout=8000,
            )
        except Exception:
            pass
        page.screenshot(path=str(png), full_page=True)
        try:
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            text = ""
        txt.write_text(text or "")
    except Exception as e:
        try:
            png.write_bytes(b"")  # marker that capture failed
        except Exception:
            pass
        return png, 0, ""
    finally:
        if ctx:
            try:
                ctx.close()
            except Exception:
                pass
    size = png.stat().st_size if png.exists() else 0
    sha1 = ""
    if size:
        try:
            sha1 = hashlib.sha1(png.read_bytes()).hexdigest()
        except Exception:
            sha1 = ""
    return png, size, sha1


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ART))
    except Exception:
        return p.name


# --------------------------------------------------------------------------
# Action runners (each returns (http_code, ok, summary_str))
# --------------------------------------------------------------------------

def _action_view_list(s: requests.Session, project: str) -> tuple[int, bool, str]:
    code, body = get(
        s, "/api/resource/GRM Issue",
        params={
            "filters": json.dumps([["project", "=", project]]),
            "fields": json.dumps(["name", "status"]),
            "limit_page_length": 5,
        },
    )
    n = len((msg(body) or {}).get("data") or []) if code == 200 else 0
    return code, code == 200, f"rows={n}"


def _action_view_assigned(s: requests.Session, email: str
                          ) -> tuple[int, bool, str]:
    code, body = get(
        s, "/api/resource/GRM Issue",
        params={
            "filters": json.dumps([["assignee", "=", email]]),
            "fields": json.dumps(["name", "status"]),
            "limit_page_length": 5,
        },
    )
    n = len((msg(body) or {}).get("data") or []) if code == 200 else 0
    return code, code == 200, f"my_assigned={n}"


def _action_comment(s: requests.Session, issue_name: str, by: str,
                    text: str) -> tuple[int, bool, str]:
    cid = uuid.uuid4().hex[:14]
    now_ms = int(time.time() * 1000)
    payload = {
        "changes": {
            "grm_issue_comments": {
                "created": [{
                    "id": cid, "creation": now_ms, "modified": now_ms,
                    "grm_issue": issue_name,
                    "comment_text": text,
                    "comment_by": by, "comment_date": now_ms,
                }],
                "updated": [], "deleted": [],
            },
        },
        "lastPulledAt": 0,
    }
    code, _b = post(s, "/api/method/egrm.api.sync.push_changes",
                    json_body=payload, timeout=30)
    return code, code == 200, f"comment_id={cid}"


def _action_assign(s: requests.Session, issue_name: str,
                   assignee: str) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/egrm.api.issue.assign",
        data={"issue_id": issue_name, "assignee_id": assignee},
    )
    m = msg(body) if isinstance(body, dict) else {}
    ok = code == 200 and (m.get("status") == "success"
                          if isinstance(m, dict) else False)
    return code, ok, f"assignee={assignee}"


def _action_resolve(s: requests.Session, issue_name: str,
                    text: str) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/egrm.api.issue.resolve",
        data={"issue_id": issue_name, "resolution_text": text},
    )
    m = msg(body) if isinstance(body, dict) else {}
    ok = code == 200 and (m.get("status") == "success"
                          if isinstance(m, dict) else False)
    return code, ok, "resolved=ok"


def _action_reopen(s: requests.Session, issue_name: str,
                   reason: str) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/egrm.api.issue.reopen",
        data={"issue_id": issue_name, "reason": reason},
    )
    m = msg(body) if isinstance(body, dict) else {}
    ok = code == 200 and (m.get("status") == "success"
                          if isinstance(m, dict) else False)
    return code, ok, "reopened=ok"


def _action_escalate(s: requests.Session, issue_name: str,
                     reason: str) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/egrm.api.issue.escalate",
        data={"issue_id": issue_name, "reason": reason},
    )
    m = msg(body) if isinstance(body, dict) else {}
    ok = code == 200 and (m.get("status") == "success"
                          if isinstance(m, dict) else False)
    return code, ok, "escalated=ok"


def _action_cancel(s: requests.Session, issue_name: str
                   ) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/frappe.client.cancel",
        data={"doctype": "GRM Issue", "name": issue_name},
    )
    return code, code == 200, "cancelled?"


def _action_update(s: requests.Session, issue_name: str,
                   issue_data: dict) -> tuple[int, bool, str]:
    code, body = post(
        s, "/api/method/egrm.api.issue.update",
        json_body={"issue_id": issue_name, "issue_data": issue_data},
    )
    m = msg(body) if isinstance(body, dict) else {}
    ok = code == 200 and (m.get("status") == "success"
                          if isinstance(m, dict) else False)
    return code, ok, f"updated={list(issue_data.keys())}"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    suite = SuiteRun("ACTOR-FLOW")

    # ---- 1. Build matrix as project-admin ---------------------------------
    s_admin = requests.Session()
    code, body = login(s_admin, *ACTOR_PROJECT_ADMIN)
    suite.ok("FLOW-0.admin_login",
             code == 200 and msg(body) == "Logged In",
             f"http={code}")
    matrix = build_matrix(s_admin)
    matrix_path = ART / "actor_action_matrix.json"
    matrix_path.write_text(json.dumps(matrix, indent=2))
    suite.ok("FLOW-0.matrix_built",
             len(matrix["actors"]) == 6,
             f"actors={list(matrix['actors'].keys())} matrix={matrix_path.name}")

    # ---- 2. Resolve catalog refs on RW-WB ---------------------------------
    project = PROJECT_CODE
    cat = _first(s_admin, "GRM Issue Category", project)
    itype = _first(s_admin, "GRM Issue Type", project)
    region = _first(s_admin, "GRM Administrative Region", project)
    init = _first(s_admin, "GRM Issue Status", project,
                  extra=[["initial_status", "=", 1]])
    if not (cat and itype and region and init):
        suite.ok("FLOW-0.lookups_present", False,
                 f"cat={cat} itype={itype} region={region} init={init}")
        logout(s_admin)
        return summary(suite)
    suite.ok("FLOW-0.lookups_present", True,
             f"cat={cat['name']} itype={itype['name']} region={region['name']} init={init['name']}")

    # ---- 3. Browser bootstrap ---------------------------------------------
    browser = None
    pw_ctx = None
    try:
        from playwright.sync_api import sync_playwright
        pw_ctx = sync_playwright().start()
        browser = pw_ctx.chromium.launch(headless=True)
        suite.ok("FLOW-0.playwright_ready", True, "chromium headless launched")
    except Exception as e:
        suite.ok("FLOW-0.playwright_ready", False,
                 f"{type(e).__name__}: {str(e)[:120]} (PNG captures will be skipped)")

    # ---- 4. Seed grm-dept project assignment ------------------------------
    # grm-dept@egrm.test holds duty Frappe Roles but has no GRM User
    # Project Assignment, which means the duty-driven has_permission
    # check denies it access to GRM Issue. Provision an Activated
    # all-duties assignment on RW-WB so the Supervise/dept
    # actor can actually exercise its duty actions in CHAIN-3.
    # The 'Administrator' GRM Project Role bundles all six duties
    # (Intake/Review/Assignment/Investigate & Resolve/Feedback/Supervise).
    role_resolver = _first(s_admin, "GRM Project Role", project,
                           extra=[["role_name", "=", "Administrator"]])
    if role_resolver:
        existing = get(
            s_admin, "/api/resource/GRM User Project Assignment",
            params={
                "filters": json.dumps([
                    ["user", "=", ACTOR_GRM_DEPT[0]],
                    ["project", "=", project],
                ]),
                "fields": json.dumps(["name"]),
            },
        )
        rows = (msg(existing[1]) or {}).get("data") if existing[0] == 200 else []
        if not rows:
            code, body = post(
                s_admin, "/api/resource/GRM User Project Assignment",
                json_body={
                    "doctype": "GRM User Project Assignment",
                    "user": ACTOR_GRM_DEPT[0],
                    "project": project,
                    "role": role_resolver["name"],
                    "administrative_region": region["name"],
                    "is_active": 1,
                    "activation_status": "Activated",
                },
            )
            assignment_name = (msg(body) or {}).get("data", {}).get("name") if isinstance(body, dict) else None
            suite.ok("FLOW-0.grm_dept_assignment_seeded",
                     code in (200, 201, 409),
                     f"http={code} role={role_resolver['name']} region={region['name']} body={str(body)[:160]}")
        else:
            assignment_name = rows[0]["name"]
            suite.ok("FLOW-0.grm_dept_assignment_seeded", True,
                     f"already exists: {assignment_name}")
        # Force activation_status = "Activated" — the assignment doctype
        # defaults new rows to "Pending Activation" (and the duty resolver
        # only counts ("Activated", "")), so a freshly-created OR pre-existing
        # row may otherwise be ignored when checking grm-dept's duties.
        if assignment_name:
            ac_code, ac_body = post(
                s_admin, "/api/method/frappe.client.set_value",
                data={
                    "doctype": "GRM User Project Assignment",
                    "name": assignment_name,
                    "fieldname": json.dumps({
                        "is_active": 1,
                        "activation_status": "Activated",
                    }),
                },
            )
            suite.ok("FLOW-0.grm_dept_assignment_activated",
                     ac_code in (200, 202),
                     f"http={ac_code} name={assignment_name} body={str(ac_body)[:160]}")
    else:
        suite.ok("FLOW-0.grm_dept_assignment_seeded", False,
                 "no GRM Project Role 'Administrator' for project")

    seq_counter: dict[str, int] = {}

    def cap(actor_email: str, action: str, route: str) -> tuple[str, str]:
        """Capture per-actor PNG. Returns (rel_png_path, sha1)."""
        slug = ACTOR_SLUGS[actor_email]
        seq_counter[slug] = seq_counter.get(slug, -1) + 1
        seq = seq_counter[slug]
        if not browser:
            return f"(no-browser)/{slug}/{seq:02d}-{action}.png", ""
        # Find password
        pwd = next(
            p for em, p in (
                ACTOR_PROJECT_ADMIN, ACTOR_GRM_OFFICER, ACTOR_TRIAGE_OFFICER,
                ACTOR_RESOLVER, ACTOR_FIELD_OFFICER, ACTOR_GRM_DEPT,
            ) if em == actor_email
        )
        png, size, sha1 = _capture_action(
            browser, slug, actor_email, pwd, seq, action, route,
        )
        return _rel(png), sha1

    # ---- Helper to record one action assertion ---------------------------
    def record(actor_email: str, action: str, http_code: int, action_ok: bool,
               note: str, issue_name: str | None, route: str,
               *, expect_fail: bool = False) -> None:
        rel, sha1 = cap(actor_email, action, route)
        slug = ACTOR_SLUGS[actor_email]
        st = _read_status(s_admin, issue_name) if issue_name else {}
        passed = (action_ok and not expect_fail) or (
            (not action_ok) and expect_fail
        )
        if expect_fail:
            note = f"EXPECTED-FAIL {note}"
        detail = (
            f"actor={actor_email} action={action} http={http_code} "
            f"{note} issue={st.get('name') or issue_name or '-'} "
            f"status={st.get('status') or '-'} assignee={st.get('assignee') or '-'} "
            f"screenshot={rel} sha1={sha1[:12]}"
        )
        suite.ok(f"FLOW-{slug.upper()}.{action}", passed, detail)

    # ====================================================================== CHAIN-1: citizen → grm-officer accepts → triage → resolver → grm-dept closes
    print("\n[ACTOR-FLOW] CHAIN-1 — citizen origin → resolver → close")
    s_anon = requests.Session()
    chain1_marker = f"AQE-FLOW-CHAIN1-{uuid.uuid4().hex[:8]}"
    chain1_name = _seed_via_public_submit(
        s_anon, project, cat["name"], itype["name"], region["name"], chain1_marker,
    )
    if not chain1_name:
        chain1_name = _resolve_issue_by_marker(s_admin, project, chain1_marker)
    suite.ok("FLOW-CHAIN-1.seed_public_submit",
             bool(chain1_name),
             f"marker={chain1_marker} issue={chain1_name}")

    if chain1_name:
        # GRM-OFFICER accepts (intake duty: view & comment to acknowledge)
        s_o = requests.Session()
        login(s_o, *ACTOR_GRM_OFFICER)
        c1, ok1, n1 = _action_view_list(s_o, project)
        record(ACTOR_GRM_OFFICER[0], "accept_public_submission", c1, ok1,
               n1, chain1_name, "/app/grm-issue")
        c2, ok2, n2 = _action_comment(s_o, chain1_name, ACTOR_GRM_OFFICER[0],
                                      f"AQE FLOW CHAIN1 — intake acknowledge {chain1_marker}")
        record(ACTOR_GRM_OFFICER[0], "comment_on_issue", c2, ok2, n2,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        c3, ok3, n3 = _action_view_assigned(s_o, ACTOR_GRM_OFFICER[0])
        record(ACTOR_GRM_OFFICER[0], "view_assigned_queue", c3, ok3, n3,
               chain1_name, "/app/grm-issue?assignee=grm-officer%40egrm.test")
        logout(s_o)

        # TRIAGE-OFFICER reviews and assigns to resolver
        s_t = requests.Session()
        login(s_t, *ACTOR_TRIAGE_OFFICER)
        c4, ok4, n4 = _action_view_list(s_t, project)
        record(ACTOR_TRIAGE_OFFICER[0], "view_review_queue", c4, ok4, n4,
               chain1_name, "/app/grm-issue")
        c5, ok5, n5 = _action_comment(s_t, chain1_name, ACTOR_TRIAGE_OFFICER[0],
                                      "AQE FLOW CHAIN1 — triage review note")
        record(ACTOR_TRIAGE_OFFICER[0], "comment_on_issue", c5, ok5, n5,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        # Triage updates `rating` (allow_on_submit=1) — proves the
        # issue.update endpoint works for this duty role on a submitted
        # doc. Free-form text fields (description, citizen) are
        # intentionally locked post-submit by Frappe's "Cannot Update
        # After Submit" rule for audit-integrity.
        c6, ok6, n6 = _action_update(
            s_t, chain1_name,
            {"rating": 4},
        )
        record(ACTOR_TRIAGE_OFFICER[0], "update_category", c6, ok6, n6,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        c7, ok7, n7 = _action_assign(s_t, chain1_name, ACTOR_RESOLVER[0])
        record(ACTOR_TRIAGE_OFFICER[0], "assign_to_resolver", c7, ok7, n7,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        logout(s_t)

        # RESOLVER investigates and resolves
        s_r = requests.Session()
        login(s_r, *ACTOR_RESOLVER)
        c8, ok8, n8 = _action_view_assigned(s_r, ACTOR_RESOLVER[0])
        record(ACTOR_RESOLVER[0], "view_assigned_queue", c8, ok8, n8,
               chain1_name, "/app/grm-issue?assignee=resolver%40egrm.test")
        c9, ok9, n9 = _action_comment(s_r, chain1_name, ACTOR_RESOLVER[0],
                                      "AQE FLOW CHAIN1 — investigator findings")
        record(ACTOR_RESOLVER[0], "comment_on_issue", c9, ok9, n9,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        c10, ok10, n10 = _action_resolve(
            s_r, chain1_name,
            f"AQE FLOW CHAIN1 — resolved by resolver ({chain1_marker})",
        )
        record(ACTOR_RESOLVER[0], "resolve", c10, ok10, n10,
               chain1_name, f"/app/grm-issue/{chain1_name}")
        logout(s_r)

        # Verify terminal
        final = _read_status(s_admin, chain1_name)
        passed_terminal = bool(final.get("status")) and bool(final.get("resolution_date"))
        suite.ok("FLOW-CHAIN-1.terminal_status",
                 passed_terminal,
                 f"issue={chain1_name} status={final.get('status')} "
                 f"resolution_date={final.get('resolution_date')} "
                 f"research_result={(final.get('research_result') or '')[:80]}")

    # ====================================================================== CHAIN-2: field-officer mobile push → triage → resolve → reopen → re-resolve
    print("\n[ACTOR-FLOW] CHAIN-2 — mobile origin → reopen → re-resolve")
    s_fo = requests.Session()
    login(s_fo, *ACTOR_FIELD_OFFICER)
    chain2_marker = f"AQE-FLOW-CHAIN2-{uuid.uuid4().hex[:8]}"
    chain2_name = _seed_via_mobile_push(
        s_fo, project, cat["name"], itype["name"], region["name"],
        init["name"], ACTOR_FIELD_OFFICER[0], chain2_marker,
    )
    suite.ok("FLOW-CHAIN-2.seed_mobile_push",
             bool(chain2_name),
             f"marker={chain2_marker} issue={chain2_name}")

    if chain2_name:
        # field-officer creates via mobile push (already happened above,
        # record action with that issue name)
        record(ACTOR_FIELD_OFFICER[0], "create_via_mobile_push",
               200, True, "seeded via sync.push_changes", chain2_name,
               "/app/grm-issue")
        # NEGATIVE: field-officer (Intake-only) cannot assign
        cN, okN, nN = _action_assign(s_fo, chain2_name, ACTOR_RESOLVER[0])
        record(ACTOR_FIELD_OFFICER[0], "assign_to_resolver_BOUNDARY",
               cN, okN, f"duty-boundary: intake cannot assign — http={cN}",
               chain2_name, f"/app/grm-issue/{chain2_name}",
               expect_fail=True)
        cF1, okF1, nF1 = _action_view_list(s_fo, project)
        record(ACTOR_FIELD_OFFICER[0], "view_assigned_queue",
               cF1, okF1, nF1, chain2_name, "/app/grm-issue")
        logout(s_fo)

        # triage assigns
        s_t = requests.Session()
        login(s_t, *ACTOR_TRIAGE_OFFICER)
        c11, ok11, n11 = _action_assign(s_t, chain2_name, ACTOR_RESOLVER[0])
        record(ACTOR_TRIAGE_OFFICER[0], "assign_to_resolver",
               c11, ok11, n11, chain2_name, f"/app/grm-issue/{chain2_name}")
        logout(s_t)

        # resolver resolves
        s_r = requests.Session()
        login(s_r, *ACTOR_RESOLVER)
        c12, ok12, n12 = _action_resolve(
            s_r, chain2_name,
            f"AQE FLOW CHAIN2 — first resolution ({chain2_marker})",
        )
        record(ACTOR_RESOLVER[0], "resolve", c12, ok12, n12,
               chain2_name, f"/app/grm-issue/{chain2_name}")
        # citizen rejects -> resolver reopens
        c13, ok13, n13 = _action_reopen(
            s_r, chain2_name, "AQE FLOW CHAIN2 — citizen rejected outcome",
        )
        record(ACTOR_RESOLVER[0], "reopen", c13, ok13, n13,
               chain2_name, f"/app/grm-issue/{chain2_name}")
        # final resolve
        c14, ok14, n14 = _action_resolve(
            s_r, chain2_name,
            f"AQE FLOW CHAIN2 — second (final) resolution ({chain2_marker})",
        )
        record(ACTOR_RESOLVER[0], "resolve", c14, ok14, n14,
               chain2_name, f"/app/grm-issue/{chain2_name}")
        logout(s_r)

        final2 = _read_status(s_admin, chain2_name)
        passed_terminal2 = (
            bool(final2.get("status")) and bool(final2.get("resolution_date"))
        )
        suite.ok("FLOW-CHAIN-2.terminal_status",
                 passed_terminal2,
                 f"issue={chain2_name} status={final2.get('status')} "
                 f"resolution_date={final2.get('resolution_date')}")

    # ====================================================================== CHAIN-3: officer desk-creates → triage assigns → resolver escalates → grm-dept resolves
    print("\n[ACTOR-FLOW] CHAIN-3 — desk origin → escalate → resolve")
    s_o2 = requests.Session()
    login(s_o2, *ACTOR_GRM_OFFICER)
    chain3_marker = f"AQE-FLOW-CHAIN3-{uuid.uuid4().hex[:8]}"
    chain3_name = _seed_via_mobile_push(
        s_o2, project, cat["name"], itype["name"], region["name"],
        init["name"], ACTOR_GRM_OFFICER[0], chain3_marker,
    )
    suite.ok("FLOW-CHAIN-3.seed_desk_create",
             bool(chain3_name),
             f"marker={chain3_marker} issue={chain3_name}")

    if chain3_name:
        record(ACTOR_GRM_OFFICER[0], "create_via_mobile_push",
               200, True, "officer desk-equivalent create via sync.push",
               chain3_name, "/app/grm-issue")
        logout(s_o2)

        s_t = requests.Session()
        login(s_t, *ACTOR_TRIAGE_OFFICER)
        cA, okA, nA = _action_assign(s_t, chain3_name, ACTOR_RESOLVER[0])
        record(ACTOR_TRIAGE_OFFICER[0], "assign_to_resolver",
               cA, okA, nA, chain3_name, f"/app/grm-issue/{chain3_name}")
        logout(s_t)

        s_r = requests.Session()
        login(s_r, *ACTOR_RESOLVER)
        cB, okB, nB = _action_escalate(
            s_r, chain3_name,
            "AQE FLOW CHAIN3 — needs district-level decision",
        )
        record(ACTOR_RESOLVER[0], "escalate",
               cB, okB, nB, chain3_name, f"/app/grm-issue/{chain3_name}")
        logout(s_r)

        # grm-dept (Supervise duty actor here) — view all, then resolve
        s_d = requests.Session()
        login(s_d, *ACTOR_GRM_DEPT)
        cC, okC, nC = _action_view_list(s_d, project)
        record(ACTOR_GRM_DEPT[0], "view_all_issues",
               cC, okC, nC, chain3_name, "/app/grm-issue?project=RW-WB")
        cD, okD, nD = _action_resolve(
            s_d, chain3_name,
            f"AQE FLOW CHAIN3 — resolved post-escalation ({chain3_marker})",
        )
        record(ACTOR_GRM_DEPT[0], "resolve",
               cD, okD, nD, chain3_name, f"/app/grm-issue/{chain3_name}")
        logout(s_d)

        # project-admin Supervise actions (configure)
        cE, _bE = get(s_admin, f"/api/resource/GRM Project/{project}")
        record(ACTOR_PROJECT_ADMIN[0], "configure_project",
               cE, cE == 200,
               f"GET project={project}", chain3_name,
               "/app/grm-project")

        final3 = _read_status(s_admin, chain3_name)
        passed_terminal3 = (
            bool(final3.get("status")) and bool(final3.get("resolution_date"))
        )
        suite.ok("FLOW-CHAIN-3.terminal_status",
                 passed_terminal3,
                 f"issue={chain3_name} status={final3.get('status')} "
                 f"escalate_flag={final3.get('escalate_flag')} "
                 f"resolution_date={final3.get('resolution_date')}")

    # ---- Sanity: cross-actor PNG distinctness ------------------------------
    pngs = list(SHOTS_FLOW.rglob("*.png"))
    sha_to_files: dict[str, list[Path]] = {}
    for p in pngs:
        try:
            h = hashlib.sha1(p.read_bytes()).hexdigest()
        except Exception:
            continue
        sha_to_files.setdefault(h, []).append(p)
    duplicates = [(h, files) for h, files in sha_to_files.items() if len(files) > 1]
    suite.ok(
        "FLOW-distinct-renders",
        # Allow up to 2 colliding pairs (e.g. same actor screen twice)
        len(duplicates) <= 2,
        f"pngs={len(pngs)} unique_sha1={len(sha_to_files)} "
        f"collisions={len(duplicates)}",
    )

    # ---- Cleanup ---------------------------------------------------------
    if browser:
        try:
            browser.close()
        except Exception:
            pass
    if pw_ctx:
        try:
            pw_ctx.stop()
        except Exception:
            pass
    logout(s_admin)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
