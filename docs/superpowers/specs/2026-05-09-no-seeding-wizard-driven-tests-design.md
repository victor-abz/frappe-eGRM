# No-Seeding Wizard-Driven Test Suite — Design

**Date:** 2026-05-09
**Status:** Approved (sections 1–7)
**Branch:** `feat/duty-driven-workspace`
**Supersedes:** `egrm/cli/sync_test_users.py` and the hardcoded `ACTOR_*` constants in `docs/superpowers/plans/aqe-generated/_common.py`

## Problem

The current AQE full suite assumes 5 globally-shared test users (`project-admin@egrm.test`, `field-officer@egrm.test`, …) exist before any sub-suite runs. They are provisioned out-of-band by `egrm/cli/sync_test_users.py`. This pattern has three failure modes that motivated three full-suite reruns:

1. **Cascade-fail on auth lockout.** Frappe locks accounts after consecutive failed logins. Once `OB-0.admin_login` fails, every downstream suite fails too because it tries the same locked credentials.
2. **Doesn't reflect human reality.** A real PM never runs a CLI to seed users — they walk through the wizard. The test suite must exercise what humans actually do, not a parallel "test-only" path that masks UI bugs.
3. **No per-project user isolation.** A single global `field-officer@egrm.test` cannot prove "user assigned to RW-WB cannot read KE-EAC issues" — they trivially can't because they're assigned to nothing.

## Decision

Replace seeded test users with users created at runtime through the GRM Project Wizard's Step 9 UI (Playwright-driven, paste CSV → click Create Users → assert success toast). Each project gets its own dedicated 5-actor set with project-scoped emails. Credentials are persisted to `wizard_state.json` and read by downstream suites via a `get_actor(project, role)` helper.

## Scope

**In scope:** ONBOARDING and every downstream sub-suite that authenticates as a non-Administrator user.

**Out of scope:** Negative-auth tests in SECURITY (those still hardcode bad creds — those users intentionally don't exist). The Frappe lockout cache bug itself (the new design sidesteps it by using fresh per-project users with known passwords).

## Architecture

### Bootstrap

The only credential the test suite hardcodes is `ADMIN_BOOTSTRAP = ("Administrator", "frappe")`. Every other login resolves through `get_actor(project_code, role)`.

### File-level changes

| File | Change |
|---|---|
| `_common.py` | Drop `ACTOR_*` constants. Add `ADMIN_BOOTSTRAP`, `get_actor`, `get_activation_code`, `project_codes_with_users`, `skip_if_no_users`, `load_wizard_state`, `validate_wizard_state`, `build_step9_csv`, `PROJECT_USER_TEMPLATE`, `NoUsersForProject`. |
| `run_onboarding_tests.py` | Login as Administrator. After Step 8, drive Step 9 UI via Playwright per project (textarea paste → Preview → Create Users). Persist created users into `wizard_state.json` per project. Emit pre-wizard no-seeding guard + per-project Step 9 verification + post-write schema check + smoke login. |
| Every downstream suite | Replace `ACTOR_PROJECT_ADMIN` etc. with `get_actor(project, "project_admin")`. Wrap project loops in `skip_if_no_users` so a partially-skipped ONBOARDING does not cascade-fail downstream. |
| `egrm/cli/sync_test_users.py` | CLI entry point hard-stops with deprecation message. Function bodies retained transiently for any in-flight imports. |

### No-seeding guard

`OB-PRE.no_test_users_pre_wizard` runs first. It logs in as Administrator, queries `frappe.client.get_count` for `User` filtered by `email LIKE %@egrm.test`, and asserts the count is 0. Failure aborts the suite with "site is not fresh — reinstall and retry". This protects against silent regression.

## The 5 canonical actors per project

Slot names are stable; emails contain the project slug.

| Slot | First | Last | Position (must match Step 3 User Type) | Frappe Role |
|---|---|---|---|---|
| `project_admin` | Project | Admin | `Project Admin` | GRM Project Admin |
| `field_officer` | Field | Officer | `Field Officer` | GRM Field Officer |
| `triage_officer` | Triage | Officer | `Triage Officer` | GRM Triage Officer |
| `resolver` | Resolver | User | `Resolver` | GRM Resolver |
| `grm_officer` | GRM | Officer | `GRM Officer` | GRM Officer |

**Email format:** `{role-slug}-{project-slug}@egrm.test`
**Region column:** project's top-level region (root assignment, duties cascade)
**Default password:** `{ProjectCode}@2026` (e.g. `RW-WB@2026`), set via Step 9 UI textbox

**Position is load-bearing.** `bulk_create_from_csv` looks up `position` against the GRM User Types created in Step 3; mismatched positions create users with no duties. ONBOARDING emits `OB-3.user_types_match_csv_positions` to lock this in.

## Step 9 walkthrough (per project)

```
for project in [RW-WB, KE-EAC, BJ-WCS]:
    1. Run wizard Steps 1-8 (existing flow, unchanged)
    2. Navigate to Step 9 via Playwright
    3. Build CSV from PROJECT_USER_TEMPLATE (5 rows, project-scoped emails)
    4. Paste CSV into #grm-step9-csv-textarea
    5. Set #grm-step9-default-password to "{ProjectCode}@2026"
    6. Click Preview → assert preview table shows 5 rows, 0 errors
    7. Click Create Users (#grm-u-import) → wait for success toast
    8. Capture wizard_step_09_{project_code}.png + .txt sidecar
    9. API verify: 5 users exist with this project's assignment
   10. Persist credentials to wizard_state.json (atomic write)
   11. Continue Steps 10-13 (routing, SLAs, statuses, activate)
```

**Failure containment:** If Step 9 fails for any project, that project's downstream suites are skipped (not failed) — emit `SUITE.{name}.{project}.skipped_no_users` rather than cascading auth failures.

**Per-project assertions:**
- `OB-9.{project}.csv_preview_valid` — preview returned 5 rows / 0 errors
- `OB-9.{project}.bulk_create_ok` — 5 users + 5 activation codes + 5 assignments
- `OB-9.{project}.api_verify_users` — `get_count` confirms 5 users assigned
- `OB-9.{project}.cross_project_leak` — none of these emails assigned elsewhere

**Post-write assertions:**
- `OB-9.wizard_state_schema_ok` — `validate_wizard_state(state) == []`
- `OB-9.smoke_login_field_officer_rw_wb` — round-trip end-to-end smoke

## `wizard_state.json` schema (additions)

Additive only; existing keys untouched.

```json
{
  "projects": {
    "RW-WB": {
      "...existing fields...": "...",
      "users": {
        "default_password": "RW-WB@2026",
        "created_at": "2026-05-09T14:32:11Z",
        "by_role": {
          "project_admin":  {"email": "project-admin-rw-wb@egrm.test",  "activation_code": "A1B2C3D4"},
          "field_officer":  {"email": "field-officer-rw-wb@egrm.test",  "activation_code": "E5F6G7H8"},
          "triage_officer": {"email": "triage-officer-rw-wb@egrm.test", "activation_code": "I9J0K1L2"},
          "resolver":       {"email": "resolver-rw-wb@egrm.test",       "activation_code": "M3N4O5P6"},
          "grm_officer":    {"email": "grm-officer-rw-wb@egrm.test",    "activation_code": "Q7R8S9T0"}
        },
        "step9_evidence": {
          "csv_sha1": "ab12cd34...",
          "preview_screenshot": "screenshots/wizard_steps/wizard_step_09_RW-WB.png",
          "after_screenshot":   "screenshots/wizard_steps/wizard_step_09_RW-WB_after.png",
          "bulk_create_response": {"created": 5, "errors": []}
        }
      }
    }
  }
}
```

**Atomicity:** Write happens once per project after Step 9 succeeds (`tmp + os.replace`), so a Step 11 failure on project 3 does not invalidate projects 1 and 2 for downstream suites.

## `_common.py` core API

```python
ADMIN_BOOTSTRAP = ("Administrator", "frappe")

class NoUsersForProject(Exception): ...

PROJECT_USER_TEMPLATE = [
    ("project_admin",  "Project", "Admin",   "Project Admin"),
    ("field_officer",  "Field",   "Officer", "Field Officer"),
    ("triage_officer", "Triage",  "Officer", "Triage Officer"),
    ("resolver",       "Resolver","User",    "Resolver"),
    ("grm_officer",    "GRM",     "Officer", "GRM Officer"),
]

def build_step9_csv(project_code: str, top_region: str) -> tuple[str, dict]: ...
def load_wizard_state() -> dict: ...
def get_actor(project_code: str, role: str) -> tuple[str, str]: ...
def get_activation_code(project_code: str, role: str) -> str: ...
def project_codes_with_users() -> list[str]: ...
def skip_if_no_users(suite, project_code: str, role: str = "project_admin") -> tuple[str, str] | None: ...
def validate_wizard_state(state: dict) -> list[str]: ...
```

`login(s, email, pwd)` is unchanged — only the source of `(email, pwd)` changes.

## Downstream suite refactor matrix

| Suite | Change |
|---|---|
| `run_arch_contract_tests.py` | `ACTOR_PROJECT_ADMIN` → `get_actor(project, "project_admin")`; wrap with `skip_if_no_users`. |
| `run_multi_project_tests.py` | Per-project credentials; cross-project leak test uses `field-officer-rw-wb@egrm.test` against KE-EAC (stronger than today). |
| `run_mobile_duty_tests.py` | `get_activation_code(project, "field_officer")` + mobile activation endpoint, per-project. |
| `run_public_citizen_tests.py` | Admin-side verification step uses `get_actor(project, "grm_officer")`. |
| `run_issue_lifecycle_tests.py` | Per-project full lifecycle: triage → assign → resolve → close, each step uses its role. |
| `run_security_tests.py` | Negative-auth tests unchanged. Cross-tenant test uses `get_actor("RW-WB", "field_officer")` against KE-EAC. |
| `run_edge_case_tests.py` | One project's `project_admin`. |
| `run_api_contract_tests.py` | One project's `project_admin`. |
| `run_performance_tests.py` | RW-WB's `project_admin`. |
| `run_ui_screenshots.py` | Per-project login as `project_admin`. |
| `run_actor_evidence.py` | Iterates `(project, role)` — produces 3×5=15 actor screenshots. |
| `run_actor_flow_tests.py` | Same iteration; project loops parallelized (3 workers), role sequence serial within a project. |
| `run_ui_grm_users_tests.py` | Asserts `/app/grm-users` shows that project's 5 users (not the global pool). |
| `run_bulk_import_tests.py` | PERF-IMPORT project gets its own Step 9 walkthrough → its own `project_admin`. |
| `run_xd_fidelity_tests.py` | Add `wizard_step_09_{code}.png` per-project files to `STEP_EXPECTATIONS` table. |

## Verification approach

1. **Pre-wizard guard:** `OB-PRE.no_test_users_pre_wizard` aborts the suite if any `*@egrm.test` user exists before the wizard runs.
2. **Per-project Step 9:** 4 named assertions per project (preview valid, bulk create ok, API verify, cross-project leak).
3. **Post-write structural:** `OB-9.wizard_state_schema_ok`.
4. **End-to-end smoke:** `OB-9.smoke_login_field_officer_rw_wb` round-trip.
5. **Deprecation marker:** `egrm/cli/sync_test_users.py` CLI entry point hard-stops with a pointer to this spec.

## Non-goals

- Fixing the Frappe lockout cache (sidestepped, not solved).
- Replacing the negative-auth fixtures in SECURITY.
- Migrating any non-test seeding (production seed data is untouched).
- Backwards compatibility with the old `ACTOR_*` constants (full cutover).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Step 9 UI selectors change and break the walkthrough | Pin selectors in one helper (`_step9_walkthrough(page, csv, password)`) so a future UI change is one-line fix. |
| Wizard Step 3 user types drift from `PROJECT_USER_TEMPLATE` positions | `OB-3.user_types_match_csv_positions` assertion catches drift at onboarding time, not at downstream auth time. |
| ONBOARDING runtime grows due to Playwright per-project | Step 9 walkthrough budgeted at ~15s per project = +45s. Acceptable vs current ~12-min suite. |
| `actor_flow` runtime triples (5 → 15 actor-runs) | Parallelize project loops (3 workers); within a project, lifecycle stages remain serial. |
| Partial ONBOARDING leaves some projects without users | `skip_if_no_users` per suite emits `skipped_no_users` rather than failing — diagnoses cleanly. |

## Success criteria

- `OB-PRE.no_test_users_pre_wizard` passes on a fresh reinstall.
- All 4 per-project Step 9 assertions pass for all 3 projects (12 assertions).
- `OB-9.wizard_state_schema_ok` and `OB-9.smoke_login_field_officer_rw_wb` pass.
- Every downstream suite either passes with `get_actor(...)` or emits a clean `skipped_no_users` for projects that didn't reach Step 9.
- `egrm/cli/sync_test_users.py` CLI invocation prints the deprecation message and exits non-zero.
