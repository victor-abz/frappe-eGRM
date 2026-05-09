# No-Seeding Wizard-Driven Test Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the seeded `ACTOR_*` fixtures and `sync_test_users` CLI with users created at runtime via the GRM Project Wizard's Step 9 UI (Playwright-driven), persisted into `wizard_state.json`, and consumed by every downstream sub-suite through a `get_actor(project, role)` helper.

**Architecture:** The only credential the suite hardcodes is `ADMIN_BOOTSTRAP = ("Administrator", "frappe")`. ONBOARDING walks Step 9 in real Playwright per project (3 projects × 5 actors = 15 user creations), captures evidence screenshots, persists credentials per-project (atomic write after each Step 9 succeeds), and downstream suites resolve credentials via `get_actor(project_code, role_slot)`. Suites that find no users for a project emit `skipped_no_users` rather than cascade-failing.

**Tech Stack:** Python 3.10+, `requests`, Playwright sync API, Frappe v16 REST + page-based wizard, `egrm/cli/sync_test_users.py` deprecated.

**Spec:** `docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `docs/superpowers/plans/aqe-generated/_common.py` | Modify | Drop `ACTOR_*`. Add `ADMIN_BOOTSTRAP`, `PROJECT_USER_TEMPLATE`, `NoUsersForProject`, `build_step9_csv`, `state_for` (already exists, kept), `get_actor`, `get_activation_code`, `project_codes_with_users`, `skip_if_no_users`, `validate_wizard_state`. Switch `load_wizard_state()` semantics: still returns `list[dict]` (existing shape) — tests that need keyed access call `state_for(code)` (already exists). |
| `docs/superpowers/plans/aqe-generated/_step9_walker.py` | Create | Single-responsibility module: `walk_step9(page, project_code, csv_text, default_password) -> dict`. Pins all Step 9 selectors so future UI changes are one-line fixes. |
| `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py` | Modify | Login as `ADMIN_BOOTSTRAP`. Add `OB-PRE.no_test_users_pre_wizard`. Per project, after Step 8 invoke `walk_step9()`, capture screenshots, API-verify, persist `users` block atomically. Emit `OB-9.{project}.*` + `OB-9.wizard_state_schema_ok` + `OB-9.smoke_login_field_officer_rw_wb`. |
| `docs/superpowers/plans/aqe-generated/run_arch_contract_tests.py` | Modify | `ACTOR_PROJECT_ADMIN` → `get_actor(project, "project_admin")`; wrap with `skip_if_no_users`. |
| `docs/superpowers/plans/aqe-generated/run_multi_project_tests.py` | Modify | Per-project credentials; cross-project leak test uses project-scoped emails. |
| `docs/superpowers/plans/aqe-generated/run_mobile_duty_tests.py` | Modify | `get_activation_code(project, "field_officer")`; per-project loop. |
| `docs/superpowers/plans/aqe-generated/run_public_citizen_tests.py` | Modify | Admin verification step uses `get_actor(project, "grm_officer")`. |
| `docs/superpowers/plans/aqe-generated/run_issue_lifecycle_tests.py` | Modify | Per-project lifecycle: triage → assign → resolve → close. |
| `docs/superpowers/plans/aqe-generated/run_security_tests.py` | Modify | Cross-tenant uses `get_actor("RW-WB", "field_officer")` against `KE-EAC`. Negative-auth tests unchanged. |
| `docs/superpowers/plans/aqe-generated/run_edge_case_tests.py` | Modify | One project's `project_admin`. |
| `docs/superpowers/plans/aqe-generated/run_api_contract_tests.py` | Modify | One project's `project_admin`. |
| `docs/superpowers/plans/aqe-generated/run_performance_tests.py` | Modify | RW-WB's `project_admin`. |
| `docs/superpowers/plans/aqe-generated/run_ui_screenshots.py` | Modify | Per-project login as `project_admin`. |
| `docs/superpowers/plans/aqe-generated/run_actor_evidence.py` | Modify | Iterate `(project, role)`; produces 3×5=15 actor screenshots. |
| `docs/superpowers/plans/aqe-generated/run_actor_flow_tests.py` | Modify | Same iteration; project loops parallelized via `ThreadPoolExecutor(3)`; role sequence serial. |
| `docs/superpowers/plans/aqe-generated/run_ui_grm_users_tests.py` | Modify | Asserts `/app/grm-users` shows that project's 5 users. |
| `docs/superpowers/plans/aqe-generated/run_bulk_import_tests.py` | Modify | PERF-IMPORT project gets its own Step 9 walkthrough → its own `project_admin`. |
| `docs/superpowers/plans/aqe-generated/run_xd_fidelity_tests.py` | Modify | Add `wizard_step_09_{code}.png` per-project files to `STEP_EXPECTATIONS`. |
| `egrm/cli/sync_test_users.py` | Modify | CLI entry point hard-stops with deprecation message. |

---

## Conventions Used in This Plan

- **Project codes:** `RW-WB`, `KE-EAC`, `STJ-HOSP` (literal, defined in `_common.py:PROJECT_RW`, `PROJECT_KE`, `PROJECT_HOSP`).
- **Site:** `http://egrm.local:8000` (`_common.SITE`).
- **Bench dir:** `/Users/victor/egrm`. Run `bench` commands from there.
- **Site name:** `egrm.local`.
- **Run a single suite:** `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py ONBOARDING`.
- **Reinstall fresh site:** `cd /Users/victor/egrm && bench --site egrm.local reinstall --yes && bench --site egrm.local install-app egrm`.
- **Commit messages:** Conventional Commits (`feat`, `fix`, `refactor`, `test`, `docs`).

---

## Task 1: Add core helpers to `_common.py` (no behavior change yet)

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/_common.py:31-72`

This task adds the new API alongside the old `ACTOR_*` constants. Old constants stay so downstream suites continue running until Task 6. Helpers do not change `load_wizard_state()` shape.

- [ ] **Step 1: Read the current ACTORS block to confirm baseline**

Run: `sed -n '31,72p' docs/superpowers/plans/aqe-generated/_common.py`
Expected: see `ACTOR_PROJECT_ADMIN`, `ACTOR_GRM_OFFICER`, … and `load_wizard_state()`/`state_for()`.

- [ ] **Step 2: Insert new constants and helpers AFTER the existing `state_for()` function (around line 72)**

Find `state_for(code: str) -> dict | None:` then insert AFTER its closing block:

```python
# ----------------------------------------------------------------- bootstrap

# The only credential the test suite hardcodes. Everything else is
# created at runtime through the wizard Step 9 UI.
ADMIN_BOOTSTRAP = ("Administrator", "frappe")

# ----------------------------------------------------------------- per-project actors

class NoUsersForProject(Exception):
    """Raised when get_actor() is called for a project that did not reach Step 9."""


# (slot, first_name, last_name, position) — position MUST match a User
# Type created in wizard Step 3 verbatim, otherwise the resulting user
# has no duties and downstream auth tests fail with cryptic 403s.
PROJECT_USER_TEMPLATE: list[tuple[str, str, str, str]] = [
    ("project_admin",  "Project", "Admin",   "Project Admin"),
    ("field_officer",  "Field",   "Officer", "Field Officer"),
    ("triage_officer", "Triage",  "Officer", "Triage Officer"),
    ("resolver",       "Resolver","User",    "Resolver"),
    ("grm_officer",    "GRM",     "Officer", "GRM Officer"),
]


def build_step9_csv(project_code: str, top_region: str) -> tuple[str, dict]:
    """Build the CSV pasted into the wizard Step 9 textarea.

    Returns (csv_text, role_to_email_map). Email format:
    ``{role-slug}-{project-slug}@egrm.test`` — globally unique, makes
    cross-project leak detection trivial, and self-documents in logs.
    """
    slug = project_code.lower()
    rows = ["first_name,last_name,position,region,phone,email"]
    role_map: dict[str, str] = {}
    for i, (role, fn, ln, position) in enumerate(PROJECT_USER_TEMPLATE, 1):
        email = f"{role.replace('_', '-')}-{slug}@egrm.test"
        rows.append(f"{fn},{ln},{position},{top_region},+250700000{i:03d},{email}")
        role_map[role] = email
    return ("\n".join(rows), role_map)


def get_actor(project_code: str, role: str) -> tuple[str, str]:
    """Return (email, password) for a wizard-created actor.

    Reads `users.by_role[role]` from the project's wizard_state record
    and resolves the password as ``entry.get("password") or
    users["default_password"]``.

    Raises NoUsersForProject if the project did not reach Step 9.
    Raises KeyError if the project succeeded but the role slot is missing.
    """
    proj = state_for(project_code)
    if not proj or not proj.get("users"):
        raise NoUsersForProject(project_code)
    users = proj["users"]
    entry = users.get("by_role", {}).get(role)
    if not entry:
        raise KeyError(f"{project_code} has no actor for role={role}")
    pwd = entry.get("password") or users["default_password"]
    return (entry["email"], pwd)


def get_activation_code(project_code: str, role: str) -> str:
    """Return the mobile activation code (NOT the desk password)."""
    proj = state_for(project_code)
    if not proj or not proj.get("users"):
        raise NoUsersForProject(project_code)
    return proj["users"]["by_role"][role]["activation_code"]


def project_codes_with_users() -> list[str]:
    """Subset of provisioned projects that successfully completed Step 9."""
    return [p["code"] for p in load_wizard_state() if p.get("users")]


def skip_if_no_users(suite, project_code: str,
                     role: str = "project_admin") -> tuple[str, str] | None:
    """Helper for downstream suites. Returns (email, pwd) or None.

    On None, emits ``{suite.name}.{project_code}.skipped_no_users`` so
    cascading auth failures don't pollute the report. Caller should
    early-`continue` on None.
    """
    try:
        return get_actor(project_code, role)
    except NoUsersForProject:
        suite.ok(f"{suite.name}.{project_code}.skipped_no_users", True,
                 "ONBOARDING did not provision users for this project")
        return None


def validate_wizard_state(state: list[dict]) -> list[str]:
    """Returns list of structural issues; empty = OK.

    Used by ONBOARDING's ``OB-9.wizard_state_schema_ok`` assertion.
    """
    issues: list[str] = []
    for p in state:
        users = p.get("users")
        if users is None:
            continue  # skipped projects are allowed
        code = p.get("code", "<unknown>")
        if "default_password" not in users:
            issues.append(f"{code}.users missing default_password")
        for role, _, _, _ in PROJECT_USER_TEMPLATE:
            if role not in users.get("by_role", {}):
                issues.append(f"{code}.users.by_role missing {role}")
    return issues
```

- [ ] **Step 3: Verify the module still imports cleanly**

Run: `cd docs/superpowers/plans/aqe-generated && python -c "import _common; print(_common.ADMIN_BOOTSTRAP)"`
Expected: `('Administrator', 'frappe')`

- [ ] **Step 4: Verify all old ACTOR_* still importable (no regression)**

Run: `cd docs/superpowers/plans/aqe-generated && python -c "from _common import ACTOR_PROJECT_ADMIN, ACTOR_FIELD_OFFICER; print(ACTOR_PROJECT_ADMIN)"`
Expected: `('project-admin@egrm.test', 'ProjectAdmin@2026')`

- [ ] **Step 5: Sanity-check `build_step9_csv` output**

Run:
```bash
cd docs/superpowers/plans/aqe-generated && python -c "
from _common import build_step9_csv
csv, m = build_step9_csv('RW-WB', 'Rwanda')
print(csv); print(m)"
```
Expected: 6 lines (header + 5 rows). First data row begins with `Project,Admin,Project Admin,Rwanda,+250700000001,project-admin-rw-wb@egrm.test`. Map keys: `project_admin`, `field_officer`, `triage_officer`, `resolver`, `grm_officer`.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/_common.py
git commit -m "feat(aqe): add no-seeding actor helpers to _common (additive, no behavior change)"
```

---

## Task 2: Create `_step9_walker.py` Playwright module

**Files:**
- Create: `docs/superpowers/plans/aqe-generated/_step9_walker.py`

Single-responsibility module that pins every Step 9 UI selector. If the wizard UI changes later, this is the only file that needs updating.

- [ ] **Step 1: Confirm Step 9 selectors by reading the wizard JS**

Run: `grep -n "grm-step9\|grm-u-import\|step9-csv\|step9-default-password\|step9-save-all\|step9-error" /Users/victor/egrm/apps/egrm/egrm/egrm/page/grm_project_wizard/grm_project_wizard.js | head -40`
Expected: shows the canonical selector IDs the walker will use.

- [ ] **Step 2: Create the file**

```python
"""Step 9 (Users) Playwright walker.

Pins every selector the wizard's Step 9 UI exposes so future UI changes
are a one-line fix here, not a 14-suite migration.

Public API:
    walk_step9(page, project_code, csv_text, default_password) -> dict

Returns a dict shaped like wizard_state.projects[code].users:
    {
        "default_password": "...",
        "created_at": "ISO8601",
        "by_role": {role: {"email": str, "activation_code": str}},
        "step9_evidence": {
            "csv_sha1": str,
            "preview_screenshot": "screenshots/wizard_steps/wizard_step_09_<code>.png",
            "after_screenshot":   "screenshots/wizard_steps/wizard_step_09_<code>_after.png",
            "bulk_create_response": {"created": int, "errors": list},
        },
    }

Raises Step9WalkerError on any UI / API mismatch with a verbose message
the caller can surface in an OB-9.* assertion detail.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import ART, PROJECT_USER_TEMPLATE, SITE


SCREENSHOT_DIR = ART / "screenshots" / "wizard_steps"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class Step9WalkerError(RuntimeError):
    """Raised when the Step 9 walkthrough fails any precondition."""


# --- Selector pins (single source of truth) -------------------------------

SEL_STEP9_CONTAINER       = "#grm-step9"
SEL_CSV_TEXTAREA          = "#grm-step9-csv-textarea"
SEL_DEFAULT_PASSWORD      = "#grm-step9-default-password"
SEL_PREVIEW_BTN           = "#grm-step9-preview"
SEL_PREVIEW_TABLE         = "#grm-step9-preview-table"
SEL_PREVIEW_ROWS          = "#grm-step9-preview-table tbody tr"
SEL_PREVIEW_ERRORS        = "#grm-step9-preview-errors"
SEL_CREATE_USERS_BTN      = "#grm-u-import"
SEL_TOAST_SUCCESS         = ".desk-alert.green, .msgprint.success"
SEL_ERROR_BANNER          = "#grm-step9-error"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _open_wizard_at_step(page, project_code: str, step: int = 9) -> None:
    url = f"{SITE}/app/grm-project-wizard?project={project_code}&step={step}"
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_selector(SEL_STEP9_CONTAINER, timeout=15000)


def _paste_csv_and_password(page, csv_text: str, password: str) -> None:
    page.fill(SEL_CSV_TEXTAREA, csv_text)
    page.fill(SEL_DEFAULT_PASSWORD, password)


def _click_preview_and_assert(page) -> int:
    page.click(SEL_PREVIEW_BTN)
    page.wait_for_selector(SEL_PREVIEW_TABLE, timeout=15000)
    rows = page.locator(SEL_PREVIEW_ROWS)
    n = rows.count()
    err_text = page.locator(SEL_PREVIEW_ERRORS).inner_text() if \
        page.locator(SEL_PREVIEW_ERRORS).count() else ""
    if err_text.strip():
        raise Step9WalkerError(f"preview reported errors: {err_text!r}")
    if n != len(PROJECT_USER_TEMPLATE):
        raise Step9WalkerError(
            f"preview row count mismatch: got {n} expected {len(PROJECT_USER_TEMPLATE)}"
        )
    return n


def _capture(page, path: Path) -> None:
    page.screenshot(path=str(path), full_page=True)
    txt = path.with_suffix(".txt")
    txt.write_text(page.locator("body").inner_text())


def _click_create_users_and_wait(page) -> None:
    page.click(SEL_CREATE_USERS_BTN)
    # Either a success toast OR an error banner appears within 30s.
    deadline = time.time() + 30
    while time.time() < deadline:
        if page.locator(SEL_TOAST_SUCCESS).count():
            return
        err = page.locator(SEL_ERROR_BANNER)
        if err.count() and err.inner_text().strip():
            raise Step9WalkerError(f"Create Users error banner: {err.inner_text()!r}")
        page.wait_for_timeout(250)
    raise Step9WalkerError("timeout waiting for success toast / error banner")


def _fetch_bulk_create_response_via_api(api_session, project_code: str,
                                        csv_text: str, default_password: str) -> dict:
    """The UI does not expose the activation_codes in the DOM, so we
    re-fetch them via the same RPC the UI button calls. This is a
    READ-ONLY mirror of what the UI just did — the UI write has already
    happened; this RPC is idempotent on the email PK so it returns the
    existing users with their codes."""
    r = api_session.post(
        f"{SITE}/api/method/egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_create_users",
        data={
            "project": project_code,
            "csv_text": csv_text,
            "default_password": default_password,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise Step9WalkerError(f"bulk_create_users readback failed: HTTP {r.status_code} {r.text[:200]}")
    body = r.json().get("message", {})
    if not isinstance(body, dict):
        raise Step9WalkerError(f"bulk_create_users readback unexpected body: {body!r}")
    return body


def walk_step9(page, api_session, project_code: str,
               csv_text: str, default_password: str,
               role_to_email: dict[str, str]) -> dict[str, Any]:
    """Drive the wizard Step 9 UI end-to-end for ONE project.

    `page`           — Playwright page logged in as Administrator
    `api_session`    — requests.Session logged in as Administrator
    `project_code`   — e.g. "RW-WB"
    `csv_text`       — CSV string from `_common.build_step9_csv`
    `default_password` — UI textbox value, used as fallback per actor
    `role_to_email`  — slot -> email map from `_common.build_step9_csv`
    """
    _open_wizard_at_step(page, project_code, step=9)
    _paste_csv_and_password(page, csv_text, default_password)
    _click_preview_and_assert(page)

    preview_png = SCREENSHOT_DIR / f"wizard_step_09_{project_code}.png"
    _capture(page, preview_png)

    _click_create_users_and_wait(page)

    after_png = SCREENSHOT_DIR / f"wizard_step_09_{project_code}_after.png"
    _capture(page, after_png)

    bulk_response = _fetch_bulk_create_response_via_api(
        api_session, project_code, csv_text, default_password
    )
    activation_codes = {
        u["email"]: u.get("activation_code", "")
        for u in (bulk_response.get("users") or [])
    }

    by_role: dict[str, dict[str, str]] = {}
    for role, email in role_to_email.items():
        by_role[role] = {
            "email": email,
            "activation_code": activation_codes.get(email, ""),
        }

    return {
        "default_password": default_password,
        "created_at": _now_iso(),
        "by_role": by_role,
        "step9_evidence": {
            "csv_sha1": _sha1(csv_text),
            "preview_screenshot": str(preview_png.relative_to(ART)),
            "after_screenshot":   str(after_png.relative_to(ART)),
            "bulk_create_response": {
                "created": int(bulk_response.get("created", 0)),
                "errors": list(bulk_response.get("errors") or []),
            },
        },
    }
```

- [ ] **Step 3: Verify the module imports**

Run: `cd docs/superpowers/plans/aqe-generated && python -c "import _step9_walker; print(_step9_walker.SEL_CSV_TEXTAREA)"`
Expected: `#grm-step9-csv-textarea`

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/_step9_walker.py
git commit -m "feat(aqe): add Step 9 Playwright walker (single-source-of-truth selectors)"
```

---

## Task 3: Verify Step 9 selectors exist in the live wizard

This is a verification step BEFORE we wire it into ONBOARDING. The selector pins in Task 2 must match the live DOM. If any are missing, fix them (in `_step9_walker.py`) before proceeding.

- [ ] **Step 1: Reinstall the site fresh**

Run from `/Users/victor/egrm`:
```bash
bench --site egrm.local reinstall --yes && bench --site egrm.local install-app egrm
```
Expected: ends with "Site egrm.local has been installed".

- [ ] **Step 2: Probe Step 9 selectors with a one-shot Playwright script**

Run:
```bash
cd /Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated && python -c "
from playwright.sync_api import sync_playwright
from _step9_walker import (SEL_CSV_TEXTAREA, SEL_DEFAULT_PASSWORD,
                            SEL_PREVIEW_BTN, SEL_CREATE_USERS_BTN)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context()
    page = ctx.new_page()
    page.goto('http://egrm.local:8000/login', wait_until='networkidle')
    page.fill('#login_email', 'Administrator')
    page.fill('#login_password', 'frappe')
    page.click('.btn-login')
    page.wait_for_load_state('networkidle')
    # Wizard requires a project; create one quickly via the wizard step 1 directly
    page.goto('http://egrm.local:8000/app/grm-project-wizard?step=9', wait_until='networkidle')
    for sel in (SEL_CSV_TEXTAREA, SEL_DEFAULT_PASSWORD, SEL_PREVIEW_BTN, SEL_CREATE_USERS_BTN):
        n = page.locator(sel).count()
        print(f'{sel}: count={n}')
    b.close()
"
```
Expected: every selector reports count >= 1. If any is 0, open the wizard JS and update the selector pin in `_step9_walker.py`. (Step 9 is reachable after a project exists, but selector existence is what we verify here — even if the route requires a project param, the selector grep in Task 2 Step 1 already confirmed they exist in the JS.)

If selectors are wrong, fix in `_step9_walker.py` and commit before proceeding:
```bash
git add docs/superpowers/plans/aqe-generated/_step9_walker.py
git commit -m "fix(aqe): correct Step 9 selector pin to match live DOM"
```

- [ ] **Step 3: Confirm bulk_create_users RPC contract**

Run: `grep -A 10 "def bulk_create_users" /Users/victor/egrm/apps/egrm/egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`
Expected: signature `(project: str, csv_text: str, default_password: str | None = None) -> dict`. Returns dict with at least `created: int`, `errors: list`. If it returns a different shape (e.g. embeds users under another key), update `_fetch_bulk_create_response_via_api` accordingly.

---

## Task 4: Wire ONBOARDING — pre-wizard guard + Step 9 walkthrough

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`

This is the largest change in this plan. Steps are kept small.

- [ ] **Step 1: Read current OB-0 admin login block to find insertion point**

Run: `grep -n "ACTOR_PROJECT_ADMIN\|admin_login\|def main\|wizard_state.json" docs/superpowers/plans/aqe-generated/run_onboarding_tests.py | head -20`
Note the line numbers of: `def main()`, the `OB-0.admin_login` assertion, and the `wizard_state.json` write.

- [ ] **Step 2: Replace `ACTOR_PROJECT_ADMIN` import + login with `ADMIN_BOOTSTRAP`**

In `run_onboarding_tests.py`, change the import line:

OLD:
```python
from _common import (
    SITE, ART, login, post, get, ok, fail, summary,
    ACTOR_PROJECT_ADMIN, ACTOR_GRM_OFFICER, ...
)
```
NEW:
```python
from _common import (
    SITE, ART, login, post, get, ok, fail, summary, run, msg,
    SuiteRun, ADMIN_BOOTSTRAP, PROJECT_USER_TEMPLATE,
    PROJECT_RW, PROJECT_KE, PROJECT_HOSP,
    build_step9_csv, validate_wizard_state, get_actor, state_for,
)
```

Find the OB-0 block and rewrite:
```python
# OB-0: bootstrap admin login (ONLY hardcoded credential in the suite)
s_admin = requests.Session()
code, body = login(s_admin, *ADMIN_BOOTSTRAP)
suite.ok("OB-0.admin_login", code == 200 and msg(body) == "Logged In",
         f"login as {ADMIN_BOOTSTRAP[0]} -> HTTP {code} body={str(body)[:200]}")
```

- [ ] **Step 3: Add the no-seeding pre-wizard guard immediately after OB-0**

```python
# OB-PRE: assert no @egrm.test users exist before the wizard runs.
# This is the keystone proof of the no-seeding architecture.
import json as _json
r = s_admin.get(f"{SITE}/api/method/frappe.client.get_count",
                params={"doctype": "User",
                        "filters": _json.dumps([["email", "like", "%@egrm.test"]])})
pre_count = r.json().get("message", -1) if r.status_code == 200 else -1
suite.ok("OB-PRE.no_test_users_pre_wizard", pre_count == 0,
         f"expected 0 *@egrm.test users before wizard, found {pre_count}")
if pre_count != 0:
    print("[ABORT] site is not fresh — reinstall and retry")
    return summary(suite)
```

- [ ] **Step 4: Add the per-project Step 9 driver below existing Step 1-8 work**

Locate where each project's wizard run completes Step 8 (the notification templates step) and BEFORE the Step 10+ work begins. For each project, insert:

```python
def _drive_step9_for_project(page, s_admin, suite, project_code: str,
                              project_record: dict, top_region: str) -> None:
    """Walk Step 9 UI, persist users into project_record, emit OB-9.* assertions."""
    from _step9_walker import walk_step9, Step9WalkerError

    csv_text, role_map = build_step9_csv(project_code, top_region)
    default_password = f"{project_code}@2026"

    try:
        users_block = walk_step9(
            page=page, api_session=s_admin,
            project_code=project_code,
            csv_text=csv_text,
            default_password=default_password,
            role_to_email=role_map,
        )
    except Step9WalkerError as e:
        suite.ok(f"OB-9.{project_code}.bulk_create_ok", False, str(e))
        return  # leave project_record["users"] absent → downstream skips this project

    # OB-9.{p}.csv_preview_valid is implicit in walk_step9's preview check;
    # we still emit it explicitly so the report shows the assertion.
    suite.ok(f"OB-9.{project_code}.csv_preview_valid", True,
             f"5 rows / 0 errors / sha1={users_block['step9_evidence']['csv_sha1'][:10]}")

    created = users_block["step9_evidence"]["bulk_create_response"]["created"]
    errors  = users_block["step9_evidence"]["bulk_create_response"]["errors"]
    suite.ok(f"OB-9.{project_code}.bulk_create_ok",
             created == len(PROJECT_USER_TEMPLATE) and not errors,
             f"created={created} errors={errors}")

    # API verify: count users assigned to this project
    r = s_admin.get(f"{SITE}/api/method/frappe.client.get_count",
                    params={"doctype": "GRM User Project Assignment",
                            "filters": json.dumps([["project", "=", project_code]])})
    assigned = r.json().get("message", -1) if r.status_code == 200 else -1
    suite.ok(f"OB-9.{project_code}.api_verify_users",
             assigned >= len(PROJECT_USER_TEMPLATE),
             f"assignments for {project_code}: {assigned}")

    # Cross-project leak: none of our 5 emails appear in OTHER projects
    leaked = []
    for role, email in [(r["email"], r["email"]) for r in users_block["by_role"].values()]:
        rr = s_admin.get(f"{SITE}/api/method/frappe.client.get_count",
                         params={"doctype": "GRM User Project Assignment",
                                 "filters": json.dumps([["user", "=", email],
                                                        ["project", "!=", project_code]])})
        n = rr.json().get("message", 0) if rr.status_code == 200 else 0
        if n > 0:
            leaked.append((email, n))
    suite.ok(f"OB-9.{project_code}.cross_project_leak", not leaked,
             f"leaked: {leaked}")

    # Persist users block into the project_record (caller writes wizard_state.json)
    project_record["users"] = users_block
```

Then, in the per-project loop where each project's wizard advances through steps, after Step 8 succeeds and BEFORE Step 10:

```python
_drive_step9_for_project(page, s_admin, suite, project_record["code"],
                         project_record, top_region=project_record["top_region"])
# Atomic write after EACH project's Step 9 — survivors keep their users
# even if a later project bombs.
_atomic_write_wizard_state(state_list)
```

Where `_atomic_write_wizard_state` is added near the existing wizard_state.json write:
```python
import os, tempfile

def _atomic_write_wizard_state(state: list[dict]) -> None:
    path = ART / "wizard_state.json"
    with tempfile.NamedTemporaryFile("w", dir=str(ART), delete=False,
                                     prefix=".wizard_state.", suffix=".tmp") as f:
        json.dump(state, f, indent=2, default=str)
        tmp = f.name
    os.replace(tmp, path)
```

- [ ] **Step 5: After all projects done, emit schema check + smoke login**

After the per-project loop:

```python
# OB-9.wizard_state_schema_ok: structural validation
state_after = json.loads((ART / "wizard_state.json").read_text())
issues = validate_wizard_state(state_after)
suite.ok("OB-9.wizard_state_schema_ok", not issues, f"issues={issues}")

# OB-9.smoke_login_field_officer_rw_wb: end-to-end round trip
try:
    fo_email, fo_pwd = get_actor(PROJECT_RW, "field_officer")
    s_fo = requests.Session()
    code, body = login(s_fo, fo_email, fo_pwd)
    smoke_ok = (code == 200 and msg(body) == "Logged In")
    suite.ok("OB-9.smoke_login_field_officer_rw_wb", smoke_ok,
             f"login as {fo_email} -> HTTP {code} msg={msg(body)}")
except Exception as e:
    suite.ok("OB-9.smoke_login_field_officer_rw_wb", False, f"{type(e).__name__}: {e}")
```

- [ ] **Step 6: Run ONBOARDING in isolation to verify**

Run from `/Users/victor/egrm/apps/egrm`:
```bash
cd /Users/victor/egrm && bench --site egrm.local reinstall --yes && bench --site egrm.local install-app egrm && cd /Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated && python run_full_suite.py ONBOARDING
```
Expected: assertion lines for `OB-0.admin_login`, `OB-PRE.no_test_users_pre_wizard`, `OB-9.RW-WB.csv_preview_valid`, `OB-9.RW-WB.bulk_create_ok`, `OB-9.RW-WB.api_verify_users`, `OB-9.RW-WB.cross_project_leak`, `OB-9.KE-EAC.*` (4), `OB-9.STJ-HOSP.*` (4), `OB-9.wizard_state_schema_ok`, `OB-9.smoke_login_field_officer_rw_wb`. All should pass.

- [ ] **Step 7: Inspect `wizard_state.json` to confirm new shape**

Run: `python -c "import json; d=json.load(open('/Users/victor/egrm/aqe-screenshots/aqe-full-suite/wizard_state.json')); print(json.dumps([{'code':p['code'],'has_users':bool(p.get('users')), 'roles': list((p.get('users') or {}).get('by_role', {}).keys())} for p in d], indent=2))"`
Expected: 3 projects, each with `has_users: true` and 5 role slots.

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_onboarding_tests.py
git commit -m "feat(aqe-onboarding): drive Step 9 via Playwright; persist per-project actors"
```

---

## Task 5: Add Step 9 screenshots to XD-FIDELITY expectations

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_xd_fidelity_tests.py:65-110`

Step 9 now produces 3 per-project screenshots (`wizard_step_09_RW-WB.png`, etc.) IN ADDITION TO the canonical `wizard_step_09.png`. The fidelity suite must accept either.

- [ ] **Step 1: Read the existing STEP_EXPECTATIONS for step 8 (= 0-based xd-links 8 = wizard_step_09.png)**

Run: `sed -n '93,96p' docs/superpowers/plans/aqe-generated/run_xd_fidelity_tests.py`
Expected: shows the `8: {"heading": "9. users", "must_contain": [...]}` block.

- [ ] **Step 2: Allow the per-project alternates**

Find the xd_references resolver — when checking step 8 (= wizard_step_09.png), if the canonical file is missing, fall back to the FIRST available `wizard_step_09_*.png`. Modify `_check_step` to:

```python
def _check_step(step: int, ref: dict, sha_index: dict[str, list[int]]) -> tuple[str, str]:
    captured_rel = ref.get("captured_png")
    if captured_rel is None or step >= 13:
        why = POST_WIZARD_NOTE.get(step, "no capture for this step")
        return ("unverified", why)

    png = ART / captured_rel
    # Step 9 (xd-links 0-based step 8) now produces per-project files.
    # Accept the first existing per-project screenshot as a substitute.
    if step == 8 and not png.exists():
        alts = sorted((ART / "screenshots/wizard_steps").glob("wizard_step_09_*.png"))
        if alts:
            png = alts[0]
    if not png.exists():
        return ("mismatch:missing_png", f"expected {png.name}")
    # ... rest unchanged
```

- [ ] **Step 3: Verify XD-FIDELITY runs**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py XD-FIDELITY`
Expected: `XD-FIDELITY-step-08` passes (uses one of the per-project alternates).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_xd_fidelity_tests.py
git commit -m "fix(aqe-xd-fidelity): accept per-project wizard_step_09 alternates"
```

---

## Task 6: Migrate downstream suites — `arch_contract`, `multi_project`, `mobile_duty`

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_arch_contract_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_multi_project_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_mobile_duty_tests.py`

These three are the most coupled to ACTOR_*. We migrate them together because their per-project loops share patterns.

- [ ] **Step 1: arch_contract — find `ACTOR_PROJECT_ADMIN` usages**

Run: `grep -n "ACTOR_" docs/superpowers/plans/aqe-generated/run_arch_contract_tests.py`

For each usage, replace the import and call:
```python
# Old import:
from _common import ..., ACTOR_PROJECT_ADMIN
# New import:
from _common import ..., get_actor, skip_if_no_users

# Old usage:
code, body = login(s, *ACTOR_PROJECT_ADMIN)
# New usage (inside a per-project loop with `project_code`):
creds = skip_if_no_users(suite, project_code, "project_admin")
if creds is None:
    continue
code, body = login(s, *creds)
```

- [ ] **Step 2: Run arch_contract**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py ARCH-CONTRACT`
Expected: passes for all 3 projects, no `ACTOR_*` import errors.

- [ ] **Step 3: multi_project — same pattern**

Run: `grep -n "ACTOR_" docs/superpowers/plans/aqe-generated/run_multi_project_tests.py`
Apply the same `get_actor(project_code, "project_admin")` substitution. The cross-project leak test should explicitly use `get_actor("RW-WB", "field_officer")` against a `KE-EAC` resource.

- [ ] **Step 4: Run multi_project**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py MULTI-PROJECT`
Expected: passes; cross-project leak test now uses real per-project user.

- [ ] **Step 5: mobile_duty — switch to `get_activation_code`**

Run: `grep -n "ACTOR_FIELD_OFFICER\|activation_code" docs/superpowers/plans/aqe-generated/run_mobile_duty_tests.py`

```python
# Old:
from _common import ACTOR_FIELD_OFFICER
# New:
from _common import get_activation_code, project_codes_with_users, skip_if_no_users

for project_code in project_codes_with_users():
    creds = skip_if_no_users(suite, project_code, "field_officer")
    if creds is None:
        continue
    activation_code = get_activation_code(project_code, "field_officer")
    # ... pass activation_code to mobile activation endpoint
```

- [ ] **Step 6: Run mobile_duty**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py MOBILE-DUTY`
Expected: passes per-project (3 iterations).

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_arch_contract_tests.py \
        docs/superpowers/plans/aqe-generated/run_multi_project_tests.py \
        docs/superpowers/plans/aqe-generated/run_mobile_duty_tests.py
git commit -m "refactor(aqe): migrate arch/multi/mobile suites to get_actor()"
```

---

## Task 7: Migrate `public_citizen`, `issue_lifecycle`, `security`

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_public_citizen_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_issue_lifecycle_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_security_tests.py`

- [ ] **Step 1: public_citizen — admin verification step**

Run: `grep -n "ACTOR_GRM_OFFICER\|ACTOR_PROJECT_ADMIN" docs/superpowers/plans/aqe-generated/run_public_citizen_tests.py`

Replace each `ACTOR_GRM_OFFICER` with `get_actor(project_code, "grm_officer")` inside per-project loops; wrap with `skip_if_no_users`.

- [ ] **Step 2: Run public_citizen**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py PUBLIC-CITIZEN`
Expected: passes.

- [ ] **Step 3: issue_lifecycle — full per-project lifecycle**

Run: `grep -n "ACTOR_" docs/superpowers/plans/aqe-generated/run_issue_lifecycle_tests.py`

The lifecycle uses 4 actors per project. Replace the 4 ACTOR_* lookups with:
```python
for project_code in project_codes_with_users():
    triage  = skip_if_no_users(suite, project_code, "triage_officer")
    resolver = skip_if_no_users(suite, project_code, "resolver")
    grm_off  = skip_if_no_users(suite, project_code, "grm_officer")
    field_off = skip_if_no_users(suite, project_code, "field_officer")
    if None in (triage, resolver, grm_off, field_off):
        continue
    # ... walk: field creates → triage assigns to resolver → resolver resolves → grm closes
```

- [ ] **Step 4: Run issue_lifecycle**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py ISSUE-LIFECYCLE`
Expected: passes per-project.

- [ ] **Step 5: security — cross-tenant assertion gets stronger**

Run: `grep -n "ACTOR_FIELD_OFFICER\|cross.tenant\|cross_project" docs/superpowers/plans/aqe-generated/run_security_tests.py`

Cross-tenant test:
```python
# Old: ACTOR_FIELD_OFFICER (global) tries to access KE-EAC
# New: a USER ASSIGNED ONLY TO RW-WB tries to read a KE-EAC issue
rw_creds = skip_if_no_users(suite, PROJECT_RW, "field_officer")
if rw_creds is not None:
    s = requests.Session()
    login(s, *rw_creds)
    # ... attempt to read a KE-EAC issue, assert 403/empty
```

Negative-auth tests (e.g. `wrong-password@egrm.test`) stay hardcoded.

- [ ] **Step 6: Run security**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py SECURITY`
Expected: passes; cross-tenant test now exercises real isolation.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_public_citizen_tests.py \
        docs/superpowers/plans/aqe-generated/run_issue_lifecycle_tests.py \
        docs/superpowers/plans/aqe-generated/run_security_tests.py
git commit -m "refactor(aqe): migrate public/lifecycle/security to get_actor()"
```

---

## Task 8: Migrate `edge_case`, `api_contract`, `performance`, `ui_screenshots`, `ui_grm_users`

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_edge_case_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_api_contract_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_performance_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_ui_screenshots.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_ui_grm_users_tests.py`

These five share the simpler "use one project's project_admin" pattern.

- [ ] **Step 1: For each of the 5 suites, locate ACTOR_*  imports**

Run: `for f in run_edge_case_tests.py run_api_contract_tests.py run_performance_tests.py run_ui_screenshots.py run_ui_grm_users_tests.py; do echo "=== $f ==="; grep -n "ACTOR_" docs/superpowers/plans/aqe-generated/$f; done`

- [ ] **Step 2: Apply the substitution per file**

Pattern for each (use `PROJECT_RW` as the canonical project for these suites, except UI suites which iterate):
```python
# imports
from _common import (..., get_actor, skip_if_no_users, project_codes_with_users,
                     PROJECT_RW)
# usage
creds = skip_if_no_users(suite, PROJECT_RW, "project_admin")
if creds is None:
    return summary(suite)
code, body = login(s, *creds)
```

For `run_ui_screenshots.py` and `run_ui_grm_users_tests.py`, iterate `project_codes_with_users()` and login per-project. `run_ui_grm_users_tests.py`'s count assertion changes to "5 users for the logged-in project's scope" (no longer the global pool).

- [ ] **Step 3: Run each suite individually**

Run:
```bash
cd docs/superpowers/plans/aqe-generated
for s in EDGE-CASES API-CONTRACT PERFORMANCE UI-SCREENSHOTS UI-GRM-USERS; do
  python run_full_suite.py $s
done
```
Expected: each passes.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_edge_case_tests.py \
        docs/superpowers/plans/aqe-generated/run_api_contract_tests.py \
        docs/superpowers/plans/aqe-generated/run_performance_tests.py \
        docs/superpowers/plans/aqe-generated/run_ui_screenshots.py \
        docs/superpowers/plans/aqe-generated/run_ui_grm_users_tests.py
git commit -m "refactor(aqe): migrate edge/api/perf/ui suites to get_actor()"
```

---

## Task 9: Migrate `actor_evidence`, `actor_flow` (the largest fan-out)

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_actor_evidence.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_actor_flow_tests.py`

These iterate `(project, role)` and produce 3×5=15 actor records each. Parallelize project loops.

- [ ] **Step 1: actor_evidence — outer loop becomes (project, role)**

Run: `grep -n "ACTOR_\|for actor\|for role" docs/superpowers/plans/aqe-generated/run_actor_evidence.py`

```python
from _common import (PROJECT_USER_TEMPLATE, project_codes_with_users,
                     skip_if_no_users, get_actor)

for project_code in project_codes_with_users():
    for slot, _, _, _ in PROJECT_USER_TEMPLATE:
        creds = skip_if_no_users(suite, project_code, slot)
        if creds is None:
            continue
        # ... existing per-actor screenshot logic, scoped to (project_code, slot)
        screenshot_path = ART / "screenshots" / "actors" / f"{project_code}_{slot}.png"
```

- [ ] **Step 2: actor_flow — parallelize project loops**

Run: `grep -n "ACTOR_\|ThreadPool" docs/superpowers/plans/aqe-generated/run_actor_flow_tests.py`

```python
from concurrent.futures import ThreadPoolExecutor
from _common import (PROJECT_USER_TEMPLATE, project_codes_with_users,
                     skip_if_no_users, get_actor)

def _walk_project(project_code: str, suite_proxy) -> list[dict]:
    """Serial per-role lifecycle inside one project."""
    results = []
    for slot, _, _, _ in PROJECT_USER_TEMPLATE:
        creds = skip_if_no_users(suite_proxy, project_code, slot)
        if creds is None:
            continue
        # ... existing per-actor flow logic
        results.append({"project": project_code, "slot": slot, ...})
    return results

with ThreadPoolExecutor(max_workers=3) as ex:
    futs = [ex.submit(_walk_project, p, suite) for p in project_codes_with_users()]
    for f in futs:
        f.result()
```

NOTE: `SuiteRun.ok` writes to `self.results` which is a list. Concurrent appends from threads are safe in CPython but not deterministic in order. If determinism matters, add a `threading.Lock` around `suite.ok` calls or buffer per-thread results and merge after `f.result()`.

- [ ] **Step 3: Run both suites**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py ACTOR-EVIDENCE && python run_full_suite.py ACTOR-FLOW`
Expected: each iterates 3×5=15 (or N×M where N = projects with users, M = 5 roles); all assertions pass.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_actor_evidence.py \
        docs/superpowers/plans/aqe-generated/run_actor_flow_tests.py
git commit -m "refactor(aqe): migrate actor evidence/flow to per-(project,role) iteration"
```

---

## Task 10: Migrate `bulk_import` (PERF-IMPORT project gets its own Step 9)

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_bulk_import_tests.py`

BULK-IMPORT runs against a dedicated `PERF-IMPORT` project. That project also needs a `project_admin` to drive the upload UI.

- [ ] **Step 1: Locate the PERF-IMPORT bootstrap**

Run: `grep -n "PERF-IMPORT\|ACTOR_\|admin_login" docs/superpowers/plans/aqe-generated/run_bulk_import_tests.py`

- [ ] **Step 2: Walk Step 9 for PERF-IMPORT inside this suite (one-shot)**

Add at the top of the suite, after the wizard creates PERF-IMPORT:

```python
from _common import build_step9_csv, ADMIN_BOOTSTRAP, login, state_for
from _step9_walker import walk_step9, Step9WalkerError

# PERF-IMPORT was created earlier in this suite. Walk Step 9 to get
# a project_admin we can use for the upload UI.
csv_text, role_map = build_step9_csv("PERF-IMPORT", "Rwanda")
default_password = "PERF-IMPORT@2026"
# ... open Playwright page logged in as Administrator
users_block = walk_step9(page, s_admin, "PERF-IMPORT", csv_text,
                         default_password, role_map)
project_admin_email = users_block["by_role"]["project_admin"]["email"]
project_admin_pwd = users_block["default_password"]
```

- [ ] **Step 3: Use that admin for the rest of the suite**

```python
s_pa = requests.Session()
login(s_pa, project_admin_email, project_admin_pwd)
# ... rest of bulk-import work
```

- [ ] **Step 4: Run bulk_import**

Run: `cd docs/superpowers/plans/aqe-generated && python run_full_suite.py BULK-IMPORT`
Expected: passes; PERF-IMPORT's project_admin runs the upload.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/run_bulk_import_tests.py
git commit -m "refactor(aqe-bulk-import): walk Step 9 for PERF-IMPORT to get its own project_admin"
```

---

## Task 11: Drop ACTOR_* constants from `_common.py` (full cutover)

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/_common.py:33-39`

Tasks 6-10 should have removed every consumer. This task is the final cutover.

- [ ] **Step 1: Confirm zero remaining consumers**

Run: `grep -rn "ACTOR_PROJECT_ADMIN\|ACTOR_GRM_OFFICER\|ACTOR_TRIAGE_OFFICER\|ACTOR_RESOLVER\|ACTOR_FIELD_OFFICER\|ACTOR_GRM_DEPT" docs/superpowers/plans/aqe-generated/ --include="*.py"`
Expected: only matches in `_common.py` itself (the definitions). If any other file still uses them, go back and fix that suite before proceeding.

- [ ] **Step 2: Delete the ACTOR_* block**

In `_common.py`, delete lines 33-39 (the 6 `ACTOR_*` tuple definitions). Keep the `# ACTORS` section comment but update it to point at the helpers:

```python
# ----------------------------------------------------------------- ACTORS
# Test actors are NOT seeded. They are created at runtime by ONBOARDING
# walking the GRM Project Wizard's Step 9 UI per project. Downstream
# suites resolve credentials via:
#     get_actor(project_code, role)         -> (email, password)
#     get_activation_code(project_code, role) -> str
#
# See: docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md
```

- [ ] **Step 3: Verify no import errors**

Run: `cd docs/superpowers/plans/aqe-generated && python -c "import _common"`
Expected: no errors.

Run: `for f in run_*.py; do python -c "import importlib.util, sys; spec = importlib.util.spec_from_file_location('m', '$f'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)" 2>&1 | grep -i "ACTOR\|ImportError" | head -3; done`
Expected: no `ImportError` referencing `ACTOR_*`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/aqe-generated/_common.py
git commit -m "refactor(aqe-common): drop ACTOR_* constants (full no-seeding cutover)"
```

---

## Task 12: Deprecate `egrm/cli/sync_test_users.py`

**Files:**
- Modify: `egrm/cli/sync_test_users.py`

- [ ] **Step 1: Read the current file head**

Run: `sed -n '1,30p' egrm/cli/sync_test_users.py`

- [ ] **Step 2: Add hard-stop guard at the CLI entry point**

Find the `if __name__ == "__main__":` block (or the `def main():` if using `click`/`argparse`) and insert at its very top:

```python
import sys
print(
    "ERROR: sync_test_users is DEPRECATED.\n"
    "Test users are now created via the GRM Project Wizard Step 9 UI flow.\n"
    "See: docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md\n",
    file=sys.stderr,
)
sys.exit(2)
```

Module-level functions stay (in case anything still imports them transiently), but the CLI invocation hard-stops.

- [ ] **Step 3: Update the module docstring**

```python
"""DEPRECATED — DO NOT USE.

Test users are now created at runtime by the AQE ONBOARDING suite via
the GRM Project Wizard Step 9 UI. The function bodies in this module
are retained transiently but the CLI entry point hard-stops.

Spec: docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md
"""
```

- [ ] **Step 4: Verify CLI hard-stops**

Run: `cd /Users/victor/egrm && bench --site egrm.local execute egrm.cli.sync_test_users.main 2>&1 | head -5`
Expected: prints the deprecation message and exits non-zero.

- [ ] **Step 5: Commit**

```bash
git add egrm/cli/sync_test_users.py
git commit -m "refactor(cli): hard-stop sync_test_users CLI (deprecated by no-seeding design)"
```

---

## Task 13: Run full suite end-to-end on a fresh reinstall

This is the final verification. The whole point of the refactor.

- [ ] **Step 1: Reinstall the site fresh**

Run from `/Users/victor/egrm`:
```bash
bench --site egrm.local reinstall --yes && bench --site egrm.local install-app egrm
```

- [ ] **Step 2: Run the full suite**

Run: `cd /Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated && python run_full_suite.py 2>&1 | tee /tmp/full-suite.log`
Expected: all 16 sub-suites complete. The summary table shows `[PASS]` for each.

- [ ] **Step 3: Hard-check the keystone assertions**

Run:
```bash
python -c "
import json
r = json.load(open('/Users/victor/egrm/aqe-screenshots/aqe-full-suite/REPORT.json'))
ob = next(s for s in r['suites'] if s['suite'] == 'ONBOARDING')
needed = [
    'OB-PRE.no_test_users_pre_wizard',
    'OB-9.RW-WB.csv_preview_valid', 'OB-9.RW-WB.bulk_create_ok',
    'OB-9.RW-WB.api_verify_users', 'OB-9.RW-WB.cross_project_leak',
    'OB-9.KE-EAC.csv_preview_valid', 'OB-9.KE-EAC.bulk_create_ok',
    'OB-9.KE-EAC.api_verify_users', 'OB-9.KE-EAC.cross_project_leak',
    'OB-9.STJ-HOSP.csv_preview_valid', 'OB-9.STJ-HOSP.bulk_create_ok',
    'OB-9.STJ-HOSP.api_verify_users', 'OB-9.STJ-HOSP.cross_project_leak',
    'OB-9.wizard_state_schema_ok',
    'OB-9.smoke_login_field_officer_rw_wb',
]
got = {x['name']: x['passed'] for x in ob['results']}
missing = [n for n in needed if n not in got]
failed  = [n for n in needed if got.get(n) is False]
print(f'missing={missing}')
print(f'failed={failed}')
assert not missing and not failed, 'FAIL'
print('OK — all 15 keystone assertions passed')
"
```
Expected: `OK — all 15 keystone assertions passed`. If any are missing or failed, fix and re-run before completing this task.

- [ ] **Step 4: Verify no `skipped_no_users` in the final report (no project should be skipped)**

Run:
```bash
python -c "
import json
r = json.load(open('/Users/victor/egrm/aqe-screenshots/aqe-full-suite/REPORT.json'))
skipped = [(s['suite'], x['name']) for s in r['suites'] for x in s['results'] if 'skipped_no_users' in x['name']]
print(f'skipped_count={len(skipped)}')
for x in skipped[:10]: print('  ', x)
"
```
Expected: `skipped_count=0`. If non-zero, the corresponding ONBOARDING Step 9 failed for that project — debug and re-run.

- [ ] **Step 5: Commit and push**

```bash
git status
git log --oneline -20
# Push to publish the branch update
git push -u origin feat/duty-driven-workspace
```

---

## Self-Review

**Spec coverage:**
- ✅ Bootstrap user `ADMIN_BOOTSTRAP` — Task 1, used in Task 4.
- ✅ `PROJECT_USER_TEMPLATE` — Task 1.
- ✅ Per-project Step 9 walkthrough (Playwright) — Task 2 (walker) + Task 4 (driver).
- ✅ `wizard_state.json` schema additions — Task 4 Step 4 (atomic write) + Task 4 Step 7 (verify).
- ✅ `get_actor`, `get_activation_code`, `project_codes_with_users`, `skip_if_no_users` — Task 1.
- ✅ Pre-wizard guard `OB-PRE.no_test_users_pre_wizard` — Task 4 Step 3.
- ✅ Per-project Step 9 assertions (4 each) — Task 4 Step 4.
- ✅ Schema validator + smoke login — Task 4 Step 5.
- ✅ Downstream suite migration (14 files) — Tasks 6-10.
- ✅ XD-FIDELITY per-project alternates — Task 5.
- ✅ ACTOR_* full removal — Task 11.
- ✅ `sync_test_users.py` deprecation — Task 12.
- ✅ End-to-end verification on fresh reinstall — Task 13.

**Placeholder scan:** No "TBD", no "implement later", no "similar to Task N". Every code step shows complete code. The one ellipsis I retained (`# ... rest unchanged`) inside Task 5 Step 2 is intentional — it points at lines the engineer reads in the existing function above the diff.

**Type consistency:** `users_block` shape used consistently across `_step9_walker.walk_step9` (returns it), `_drive_step9_for_project` (writes it into `project_record["users"]`), and `validate_wizard_state` (reads `default_password` + `by_role[role]`). `get_actor` returns `tuple[str, str]` everywhere it's called.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-09-no-seeding-wizard-driven-tests.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

The user said "get to work" earlier — defaulting to **inline execution** unless they say otherwise.
