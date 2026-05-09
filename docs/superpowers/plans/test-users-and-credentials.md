# eGRM Test Users — Credentials & Capability Matrix

> **Source of truth.** Generated from
> `egrm/cli/sync_test_users.py`, `egrm/cli/set_worker_passwords.py`,
> `egrm/cli/seed_rdap.py`, and live verification against
> `http://egrm.local:8000` on 2026-05-08. Use these accounts to
> manually exercise admin desk pages, GRM-officer duty flows, and the
> React Native mobile app.

> **Site**: `http://egrm.local:8000`
> **Project**: `RDAP` (Rwanda Digital Acceleration Project) — `is_active=1`
> **Login URL**: `http://egrm.local:8000/login`
> **Mobile API base**: `http://egrm.local:8000/api/method/...`

---

## 1. Credentials (canonical)

| # | Email | Password | First / Last | Status |
|---|-------|----------|--------------|--------|
| 1 | `project-admin@egrm.test` | `ProjectAdmin@2026` | Pria Admin | ✅ enabled |
| 2 | `field-officer@egrm.test` | `FieldOfficer@2026` | Frida Officer | ✅ enabled |
| 3 | `triage-officer@egrm.test` | `TriageOfficer@2026` | Tomo Triage | ✅ enabled |
| 4 | `resolver@egrm.test` | `Resolver@2026` | Reno Resolver | ✅ enabled |
| 5 | `grm-officer@egrm.test` | `GrmOfficer@2026` | GRM Test Officer | ✅ enabled (mobile actor) |
| 6 | `grm-dept@egrm.test` | `GrmDept@2026` | GRM Test Dept Head | ✅ enabled |
| 7 | `grm-pm@egrm.test` | *(unset — set via desk)* | GRM Test PM | ✅ enabled |
| 8 | `grm-admin@egrm.test` | *(unset — set via desk)* | GRM Test Admin | ✅ enabled |
| 9 | `sector-officer@egrm.test` | *(unset — set via desk)* | Sector Officer | ✅ enabled |

> Users 7–9 were created inline by the wizard (Scenario B path) and
> never had a deterministic password assigned. To enable them for
> manual testing, run:
> `bench --site egrm.local execute egrm.cli.set_worker_passwords.run`
> after appending tuples for those emails (or use Frappe's "Reset
> Password" link in the desk).

---

## 2. Role & duty matrix (live, verified)

| User | Roles | Duty | DocPerm matrix highlights |
|------|-------|------|---------------------------|
| `project-admin@egrm.test` | GRM Platform Administrator, GRM Supervise | **Platform / Supervise** (BYPASS) | Full read across project DocTypes; cancel/audit on GRM Issue. Cannot submit (reserved for Investigate & Resolve / System Manager). |
| `field-officer@egrm.test` | GRM Intake | **Intake** | `create=Intake` on GRM Issue. No write/submit. |
| `triage-officer@egrm.test` | GRM Review, GRM Assignment, GRM Intake, GRM Investigate & Resolve, GRM Feedback | **Triage (Review + Assignment + …)** | `write` for review/assignment/feedback; `submit` via Investigate & Resolve. (Granted broader duties on the live site than the seed script implies.) |
| `resolver@egrm.test` | GRM Investigate & Resolve, GRM Feedback | **Investigate & Resolve + Feedback** | `submit=1`; resolution_days, escalation_reasons, citizen_feedback fields. |
| `grm-officer@egrm.test` | GRM Intake | **Cell Field Officer (mobile canonical)** | `create=Intake`, scoped to Nyamatete Village. |
| `grm-dept@egrm.test` | GRM Review, GRM Assignment, GRM Intake, GRM Investigate & Resolve, GRM Feedback | **District Department Head (full inner-workflow)** | All non-platform duties. |
| `grm-pm@egrm.test` | (TBD per ACT 4 inline) | **Project Manager** | Read-heavy; configure roles via wizard. |
| `grm-admin@egrm.test` | (TBD per ACT 4 inline) | **Project Admin (per-project)** | Mirrors Platform Admin scoped to RDAP. |
| `sector-officer@egrm.test` | GRM Review, GRM Assignment, GRM Intake | **Sector GRM Officer** | Multi-duty, scoped to Mukarange Sector. |

> **BYPASS_ROLES** (skip duty checks): `System Manager`,
> `GRM Platform Administrator`, `GRM Administrator`, `GRM Supervise`.

---

## 3. RDAP project assignments (live)

| User | Project | Region (id → name) | Department | Position |
|------|---------|--------------------|------------|----------|
| `project-admin@egrm.test` | RDAP | *(none — global)* | — | Platform Administrator |
| `triage-officer@egrm.test` | RDAP | `st66aujjca` → Kayonza District | — | District Triage Officer |
| `sector-officer@egrm.test` | RDAP | `st66aujjca` → Kayonza District | — | Sector GRM Officer (test) |
| `grm-dept@egrm.test` | RDAP | `st66aujjca` → Kayonza District | `k69pn2muse` | District GRM Officer (Dept Lead) |
| `grm-officer@egrm.test` | RDAP | `t59cuf5otg` → Nyamatete Village | — | Village Field Officer |

> `field-officer@egrm.test` and `resolver@egrm.test` are not currently
> assigned to RDAP on the live site — re-run
> `bench --site egrm.local execute egrm.cli.seed_rdap.assign_users`
> to (re)attach them, then verify with the project assignments query.

---

## 4. RDAP reference IDs (memorize for API testing)

| Lookup | ID | Display |
|--------|----|---------|
| Project | `RDAP` | Rwanda Digital Acceleration Project |
| Initial Status | `j9sfana2t6` | Open (initial_status=1) |
| In Progress | `j9ss96vv29` | In Progress |
| Resolved | `j9simppofl` | Resolved (final) |
| Closed | `j9svvgchb9` | Closed (final) |
| Rejected | `j9sikk01ro` | Rejected |
| Awaiting Citizen Feedback | `ktt7u7clqr` | Open + awaiting feedback |
| Category — Bursary | `kb4vgum0nr` | RDAP Bursary Disbursement |
| Category — Suggestion | `kdec384dia` | RDAP Suggestion |
| Category — DLP Hardware | `kfoarjnqe6` | RDAP DLP Hardware |
| Issue Type — Hardware | `krcs4ga3m3` | Hardware Issue |
| Issue Type — Complaint | `j9s7cu3suo` | Complaint |
| Issue Type — Inquiry | `j9sba7qh34` | Inquiry |
| Issue Type — Feedback | `j9sppt4p4n` | Feedback |
| Region — Nyamatete Village (mobile actor scope) | `t59cuf5otg` | Nyamatete Village |
| Region — Murama Cell | `t2jcobr729` | Murama Cell |
| Region — Mukarange Sector | `svtu08j7bf` | Mukarange Sector |
| Region — Kayonza District | `st66aujjca` | Kayonza District |
| Region — Eastern Province | `sq5f1bpqbb` | Eastern Province |
| Region — Rwanda | `sncbmujbad` | Rwanda |
| Department — (sample) | `k69pn2muse` | District department for Dept Lead |

---

## 5. Re-provisioning commands

```bash
# Re-create / refresh the four canonical seed users + roles + passwords
bench --site egrm.local execute egrm.cli.sync_test_users.sync

# Re-set the worker (Scenario B inline) passwords to known values
bench --site egrm.local execute egrm.cli.set_worker_passwords.run

# Re-seed all RDAP catalog data (categories, types, statuses, regions, …)
bench --site egrm.local execute egrm.cli.seed_rdap.seed

# Attach test users to RDAP regions
bench --site egrm.local execute egrm.cli.seed_rdap.assign_users

# Hard-purge specific Scenario-B users (used to re-test inline-create flow)
bench --site egrm.local execute \
  "frappe.get_attr('egrm.cli.sync_test_users.purge_users')(['field-officer@egrm.test'])"
```

---

## 6. Mobile actor quickstart

For the React Native app at `/Users/victor/Documents/dev/grm-mobile-app`:

```
Server URL: http://egrm.local:8000
Username:   grm-officer@egrm.test
Password:   GrmOfficer@2026
Project:    RDAP
Region:     Nyamatete Village (Cell-level field actor)
```

This account is **Intake-only**, scoped to one village, and is the
canonical actor for ACT 13 (lookups + upload), ACT 14 (sync push with
attachments), and ACT 15 (Citizen Report flow + Statistics).

---

## 7. Security notes

- These passwords are **DEV-ONLY** test credentials. They MUST NOT
  appear in any production seed script, `.env`, CI variable, or
  Coolify deployment.
- The password hashes for these accounts live in `__Auth` and are
  auto-purged when running `bench --site egrm.local reinstall`.
- If you change `set_worker_passwords.py` to add the missing emails,
  do so in a feature branch and never commit alongside production
  config changes.
