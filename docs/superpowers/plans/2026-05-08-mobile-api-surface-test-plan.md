# Mobile-App API Surface Test Plan

**Date**: 2026-05-08
**Purpose**: Validate every backend endpoint the eGRM mobile app
(`/Users/victor/Documents/dev/grm-mobile-app`) actually calls, end-to-end,
without modifying any mobile-app code. The contract is fixed by the
mobile app; the backend must conform.
**Test site**: `http://egrm.local:8000`
**Mobile actor**: `grm-officer@egrm.test` / `GrmOfficer@2026` (Cell Field
Officer, Intake-only on RDAP) — this is the canonical mobile intake
user.

---

## How the inventory was built

Grepped every API call site reachable from `src/screens/`:

```
grep -rn "egrm\.api\.\|frappe\.auth\.\|frappe\.client\.\|frappe\.db\.\
  |/api/method/\|callAPI\|call\.get\|call\.post" \
  src/screens src/services src/providers
```

Every screen consumes either WatermelonDB local data
(`watermelonManager.getDatabase().get(...)`) — populated by
`egrm.api.sync.pull_changes` — or routes through `DataManager` /
`AuthProvider` / `WatermelonSyncManager`. There are NO direct API calls
from screen components except `Profile.js → db.getDoc('User', ...)`
(which maps to Frappe's built-in `frappe.client.get_doc`).

So the full mobile-side API surface is 17 distinct endpoints/
operations, listed below. Each is tested.

---

## API inventory (17 operations)

### A. Auth + bootstrap (3)

| # | Endpoint | Caller | Purpose |
|---|---|---|---|
| A1 | `POST /api/method/login` (`auth.loginWithUsernamePassword`) | `AuthProvider.login` | Log user in, set Frappe session cookie. Body must equal `"Logged In"`. |
| A2 | `GET /api/method/frappe.auth.get_logged_user` | `AuthProvider.fetchUserInfo`, `DataManager.initializeUserContext` | Return the email of the logged-in user. |
| A3 | `POST /api/method/logout` (`auth.logout`) | `AuthProvider.logout` | Destroy session. |

### B. User context (1)

| # | Endpoint | Caller | Purpose |
|---|---|---|---|
| B1 | `GET /api/method/egrm.api.lookup.get_user_context` | `DataManager.getUserContext` | Returns `{ user, accessible_projects, accessible_regions, assignments, permissions }`. Drives the assignment-determination logic in `CitizenReportStep3`. |

### C. Lookups (8 — populate WatermelonDB on first run)

| # | Endpoint | Filter | Mobile-side fields consumed |
|---|---|---|---|
| C1 | `GET /api/method/egrm.api.lookup.projects` | (none) | `name`, `project_name`, `description`, `active` |
| C2 | `GET /api/method/egrm.api.lookup.categories` | `?project=<id>` | `name`, `category_name`, `assigned_department_id`, `administrative_level_id`, `confidentiality_level` |
| C3 | `GET /api/method/egrm.api.lookup.types` | `?project=<id>` | `name`, `type_name` (or similar `typeName` after WMDB mapping) |
| C4 | `GET /api/method/egrm.api.lookup.statuses` | (none) | `name`, `status_name`, `initial_status` (boolean) |
| C5 | `GET /api/method/egrm.api.lookup.age_groups` | (none) | `name`, `label` |
| C6 | `GET /api/method/egrm.api.lookup.citizen_groups` | (none) | nested `{ citizen_group_1: [...], citizen_group_2: [...] }` |
| C7 | `GET /api/method/egrm.api.lookup.departments` | (none) | `name`, `department_name` |
| C8 | `GET /api/method/egrm.api.lookup.regions` | optional filters | `name`, `region_name`, `parent_id`, `administrative_level` |

All return `{status, data}` envelope (per `extractApiResponse` in DataManager.js:20).

### D. Sync (2 — the main hot path; populates everything in WMDB)

| # | Endpoint | Caller | Notes |
|---|---|---|---|
| D1 | `GET /api/method/egrm.api.sync.pull_changes` | `WatermelonSyncManager.pullChanges` | Params: `lastPulledAt` (ms-epoch or empty for full sync), `schemaVersion`, `migration`. Response: `{ changes: { table: { created, updated, deleted } }, timestamp }`. |
| D2 | `POST /api/method/egrm.api.sync.push_changes` | `WatermelonSyncManager.pushChanges` | Body: `{ changes, lastPulledAt }`. Returns acknowledgement / new server state. |

### E. Mutations / file ops (1)

| # | Endpoint | Caller | Notes |
|---|---|---|---|
| E1 | `POST /api/method/egrm.api.issue.upload_attachment` | `DataManager.uploadAttachment` | Body: `{ issue, attachment_url, attachment_name }`. Returns the saved attachment. |

### F. Frappe built-ins (2)

| # | Endpoint | Caller | Notes |
|---|---|---|---|
| F1 | `GET /api/method/frappe.client.get_doc?doctype=User&name=<email>` (via `db.getDoc('User', username)`) | `Profile.js` line 57 | Reads `full_name`, `phone`, `user_image`. Always works in Frappe; no custom backend; only verifies the test user has these populated. |

---

## Test methodology

Pure HTTP via Python `requests` — exactly what the mobile app sees over
the wire. We log in as `grm-officer@egrm.test`, then exercise A1 → F1
in order, asserting on response shapes the mobile-app code actually
reads. We also issue admin-actor calls where the grm-officer scope
returns nothing relevant (e.g., E1 needs an existing issue id).

For each test we record:
- HTTP code
- Body envelope
- Specific shape assertions (key names, types, non-emptiness)
- Whether the response satisfies the contract the mobile app expects

Test harness: `/tmp/aqe-e2e/run_act13_mobile_full_api.py`
Artifacts: `/Users/victor/egrm/aqe-screenshots/e2e-flow/mobile-api/` —
one JSON file per endpoint.

## Acceptance criteria

For each of the 17 operations:
- HTTP 200
- Response shape matches `mobile-side fields consumed` column above
- Where shape mismatches are found, fix backend (Python only, NEVER
  the mobile app).

## What constitutes a failure

A failure is **any** of:
- Non-200 status for valid actor
- Missing field name the mobile screen reads
- Wrong field type (e.g., string where mobile parses boolean)
- Empty/null where the mobile UI requires non-empty (e.g., statuses
  missing the `initial_status=true` row → CitizenReportStep3 throws
  `"No initial status available. Please contact support."`)

## Sequence

1. A1 login → cookies retained for the rest of the run.
2. A2 get_logged_user → assert message == grm-officer email.
3. B1 get_user_context → assert RDAP appears in accessible_projects.
4. C1–C8 lookups → assert each returns the WMDB-friendly shape.
5. D1 pull_changes (full sync, lastPulledAt="") → assert `changes.grm_*`
   keys, RDAP issues present.
6. C2/C3 with `project=RDAP` filter → categories/types scoped correctly.
7. D2 push_changes (idempotent empty payload) → assert 200 + ack.
8. E1 upload_attachment using one of the 3 RDAP issues created in
   ACT 6 → assert created.
9. F1 frappe.client.get_doc on the actor → assert User doc present.
10. A3 logout → assert 200.

If anything fails: fix backend Python only, re-run the same script
until 17/17 PASS.
