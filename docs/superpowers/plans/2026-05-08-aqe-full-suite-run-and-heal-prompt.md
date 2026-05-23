# AQE Queen Coordinator — Full Suite Run & Heal

**Audience:** AQE v3 Queen Coordinator (`qe-queen-coordinator`) operating with the
`mcp__agentic-qe__*` toolset against the eGRM Frappe app.

**Goal:** run the AQE-generated full suite end-to-end, observe failures, fix
**application code** (never the suite scaffolding) until every assertion is green,
and persist learnings.

---

## OBJECTIVE

Run the full AQE-generated suite at
`/Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated/` against the
local Frappe site (`http://egrm.local:8000`). Whenever an assertion fails:

1. Diagnose root cause in the **application** (`apps/egrm/egrm/...`).
2. Patch the application — NOT the test scaffolding.
3. Re-run the affected sub-suite, then the full suite.
4. Persist what you learned via `mcp__agentic-qe__memory_store` so future runs
   route around the same class of regression.

The structural design of the suite — number of sub-suites, run order, project
layouts (RW-WB / KE-EAC / STJ-HOSP / PERF-IMPORT), perf budgets, the BULK-IMPORT
UI-only scope, the XD body-only fidelity check, the canonical six-duty model —
**must not change**. If a test surfaces a structural disagreement with the app,
the app changes, not the test.

---

## CANONICAL ARTIFACTS

- Test plan (single source of truth):
  `/Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated/00-test-plan.md`
- Architecture plan (per-project DocType + duty model):
  `/Users/victor/egrm/apps/egrm/docs/superpowers/plans/2026-04-25-egrm-per-project-architecture-implementation.md`
- Suite root:
  `/Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated/`
  - Orchestrator: `run_full_suite.py`
  - Shared helpers + budgets: `_common.py`
  - Sub-suites: `run_<area>_tests.py`
- Reports / artifacts dir:
  `/Users/victor/egrm/aqe-screenshots/aqe-full-suite/`
  - `REPORT.json` — aggregated results
  - `<SUITE>.json` — per-sub-suite detail
  - `screenshots/` — Playwright captures
  - `screenshots/wizard_steps/wizard_step_NN.png` — body-only XD fidelity shots
  - `XD_FIDELITY_REPORT.md` — manual side-by-side table
  - `design_refs.json` — XD screen URLs + per-step notes
- App root:
  `/Users/victor/egrm/apps/egrm/egrm/`

---

## PRE-FLIGHT

Run these once at start. Each must succeed before the run begins.

1. Initialize the QE fleet:
   ```
   mcp__agentic-qe__fleet_init({
     topology: "hierarchical",
     maxAgents: 15,
     memoryBackend: "hybrid"
   })
   ```
2. Reinstall the egrm app on the site (so any pending DocType/migration is
   active):
   ```
   bench --site egrm.local install-app egrm   # idempotent
   bench --site egrm.local migrate
   bench --site egrm.local clear-cache
   ```
3. Sync canonical test users into the site (the suite assumes
   `ACTOR_PROJECT_ADMIN`, `ACTOR_FIELD_OFFICER`, etc. exist):
   - Use `apps/egrm/egrm/cli/` if present, otherwise call the Frappe REST
     endpoints with the credentials defined in `_common.py`.
4. Ensure Playwright Chromium is installed:
   ```
   pip install playwright requests
   playwright install chromium
   ```
5. Confirm site reachability:
   ```
   curl -sSf http://egrm.local:8000/api/method/ping
   ```

If any pre-flight step fails: stop, report the failure to the user, do not
proceed.

---

## RUN PROTOCOL

### Phase A — full pass, no fixes

```
cd /Users/victor/egrm/apps/egrm/docs/superpowers/plans/aqe-generated
python run_full_suite.py
```

After the run completes, read:
`/Users/victor/egrm/aqe-screenshots/aqe-full-suite/REPORT.json`

### Phase B — diagnose & fix

For each `suite` in `REPORT.json` with `failed > 0`, walk the `results` array.
For each failing assertion ID (e.g. `PF-13.region_cascade_under_100ms`,
`BI-UI-1.upload_admin_regions_registered`, `AC-2.platform_admin_role_canary`):

1. Quote the assertion ID and its failure detail verbatim in your scratch
   memory.
2. Spawn the appropriate specialist via `Task` (background OK):
   - `qe-root-cause-analyzer` — for ambiguous or multi-system failures
   - `qe-tdd-green` — when the fix is a one-file targeted change in
     `apps/egrm/egrm/...`
   - `qe-coverage-specialist` — when the failure exposes an untested branch in
     application logic
   - `qe-security-scanner` — for any `SEC-*` assertion failure
   - `qe-performance-tester` — for any `PF-*` assertion failure
3. Apply the patch in the app source.
4. Re-run **only the affected sub-suite** to confirm green:
   ```
   python run_full_suite.py <SUITE_NAME>     # e.g. PERFORMANCE
   ```
5. Iterate until that sub-suite is green.

### Phase C — full re-run

Once every sub-suite passes individually, run the orchestrator end-to-end one
more time. The DoD requires `REPORT.json.totals.failed == 0` from a single
contiguous run — not a stitched run.

### Phase D — write HEALING_LOG.md

Emit
`/Users/victor/egrm/aqe-screenshots/aqe-full-suite/HEALING_LOG.md` with one
section per fix:

```
## <ASSERTION_ID>
- Root cause:
- App file(s) changed:
- Diff summary:
- Re-run evidence: <SUITE_NAME> went from N/M -> M/M
```

---

## FIX SCOPE — ALLOWED

You **MAY** change anything under:

- `apps/egrm/egrm/` (Python, JS, JSON, fixtures, hooks)
- Missing `egrm.api.bulk_import.*` whitelisted RPCs (this is the most likely
  first-run gap — see callout below)
- Patches under `apps/egrm/egrm/patches/`
- DocType JSON / Python controllers (validate, on_update, on_submit)
- `hooks.py` (boot_session, scheduler events, jinja filters)
- Workspace JSONs under `apps/egrm/egrm/egrm/workspace/`
- Public-side templates / web forms under `apps/egrm/egrm/templates/` and
  `apps/egrm/egrm/www/`
- Wizard CSS at
  `apps/egrm/egrm/page/grm_project_wizard/grm_project_wizard.css`
- Targeted Frappe-QB rewrites and caching where a `PF-*` budget is breached

You **MAY** add new whitelisted methods, fixtures, patches, or migrations
when the suite reveals a missing surface — but only when the suite explicitly
asserts that surface (e.g. `BI-UI-1.MISSING_UI_RPCS`).

---

## FIX SCOPE — FORBIDDEN

You **MUST NOT** change:

- The number of sub-suites or their run order in
  `run_full_suite.py:SUITES`
- `LAYOUTS` (RW-WB / KE-EAC / STJ-HOSP / PERF-IMPORT) in `_common.py`
- `DEFAULT_ROLE_DUTIES`, `CANONICAL_DUTIES`,
  `EXPECTED_FRAPPE_GRM_ROLES`, `LEGACY_GRM_ROLES`
- `PERF_BUDGETS` — these are the negotiated SLOs; the app must meet them
- `BULK_SCALE` — these are the documented scale targets
- `XD_PROJECT_ROOT`, `XD_SCREEN_URLS`, `XD_STEP_NOTES`
- `EXPECTED_UI_RPCS` — these are the contract; if missing, ADD the module
- The MacBook 13" viewport pin (1440×900 @ DPR=2)
- `00-test-plan.md` — this is the contract document
- The body-only XD fidelity scope (Frappe sidebar/header are stock chrome and
  out of scope; never reintroduce sidebar/header diffing)
- `EXPECTED_FRAPPE_BENCH_COMMANDS` removal: the bench CLI is **explicitly
  out of scope** for BULK-IMPORT; do not re-add CLI assertions

If a test seems "wrong", treat that as a signal that the app is wrong. Bring
it up in `HEALING_LOG.md` under "Open Questions" — do not silently mutate the
suite.

---

## GUARDRAILS

- Honor the project Integrity Rule: no shortcuts, no fake passes, no
  commenting-out of failing assertions to make CI green.
- Never run `git commit` / `git push` without explicit user approval.
- Never run `--no-verify`, `--no-gpg-sign`, or skip pre-commit hooks.
- Never `rm -rf` `.agentic-qe/` or any `*.db`.
- For UI changes: verify in headless Chromium at the pinned viewport before
  declaring a UI fix done. Type-check / unit-test green is **not** UI-verified.
- Run sub-agents in parallel where independent (root-cause-analyzer for one
  failure can run alongside coverage-specialist for another).

---

## LEARNING — persist after each green fix

```
mcp__agentic-qe__memory_store({
  key: "patterns/aqe-heal/<assertion-id>/<timestamp>",
  namespace: "learning",
  value: {
    type: "aqe-heal",
    suite: "<SUITE_NAME>",
    assertion: "<ASSERTION_ID>",
    root_cause: "<one-sentence>",
    app_file: "<relative path>",
    fix_summary: "<one-sentence>",
    confidence: 0.9
  },
  persist: true
})
```

At the end of the run, also store one rolled-up `patterns/aqe-heal/run/<ts>`
with the full list of resolved assertions and the elapsed wall time.

---

## DEFINITION OF DONE

All of the following must hold from a single, contiguous full-suite run:

- `REPORT.json.totals.failed == 0`
- Every `PF-*` assertion is within its `PERF_BUDGETS` budget — no soft
  exceptions
- Every `BI-UI-*` assertion is green; the round-trip
  download_admin_regions_template → upload_admin_regions completes against
  the dedicated `PERF-IMPORT` project
- `XD_FIDELITY_REPORT.md` exists with all 16 rows populated and links to the
  body-only `wizard_steps/wizard_step_NN.png` for each step
- `HEALING_LOG.md` exists with one entry per fix applied during the heal phase
- `screenshots/` contains the 12 page captures plus 16 wizard step body-only
  captures

---

## OPERATOR CALLOUTS

### Callout 1 — `PF-13.region_cascade_under_100ms`

This is the headline performance budget for the wizard's region cascade. The
PERFORMANCE suite bulk-seeds extra regions on RW-WB to stress this path. If it
fails, the fix is almost certainly server-side: an N+1 in the cascade fetch,
a missing index on `parent_administrative_region`, or an unbatched
`frappe.get_all` inside a loop. **Profile before patching.**

### Callout 2 — `BI-UI-1.MISSING_UI_RPCS` (expected on first run)

The XD design promises a Download-template / Upload page for project admins,
but the whitelisted module `egrm.api.bulk_import` may not exist yet on the
current branch. The expected fix is to **add** that module exposing
`download_admin_regions_template`, `upload_admin_regions`,
`download_workers_template`, `upload_workers` — wrapped behind a
project-admin permission gate. Internally these MAY reuse the parsing logic
from the bench commands; that is an implementation detail. The bench CLI
itself remains out of scope for the test surface.

### Callout 3 — `AC-2.platform_admin_role_canary`

This is the canary for the duty-driven role refactor. If it fails, the most
likely cause is a stale role in `hooks.py` `boot_session` or a leftover
`Has Role` doc for one of the four legacy roles
(`LEGACY_GRM_ROLES` in `_common.py`). Run the role-cleanup patch before
deeper diagnosis.

---

## START

1. Run the PRE-FLIGHT block.
2. Run Phase A.
3. Iterate Phases B/C until DoD is met.
4. Emit `HEALING_LOG.md` per Phase D.
5. Persist learning entries per the LEARNING section.
6. Report back to the user with: total wall time, fixes applied
   (assertion IDs only), final `REPORT.json.totals`.
