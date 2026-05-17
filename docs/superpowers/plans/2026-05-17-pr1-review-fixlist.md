# PR #1 Review Fix Checklist — `feat/duty-driven-workspace`

> Generated from senior-Frappe review (4 parallel review agents). Each item carries severity, file:line, and concrete fix. Items in the same group are independent and can be fixed in parallel.

---

## Group A — BLOCKING security (must fix before merge)

- [ ] **A1. Cross-project assignment tampering** — add `_assert_project_admin(user, project)` helper; load each assignment by `name`, resolve `assignment.project`, assert caller holds active Supervise duty on that project (or is `System Manager` / `GRM Platform Administrator`). Apply after `_require_wizard_role` / `_gate` in:
  - `egrm/egrm/page/grm_users/grm_users.py` — `update_assignment` (l.329), `delete_assignment`, `resend_activation`, `expire_activation` (l.388)
  - `egrm/egrm/page/grm_project_wizard/grm_project_wizard_user_assignments.py` — `update_assignment_field` (l.230), `bulk_update_assignments`, `bulk_remove_assignments` (l.372)
- [ ] **A2. Weak activation code** — replace `zlib.adler32(...)[:6]` with `f"{secrets.randbelow(10**6):06d}"`:
  - `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py:507–523`
  - `egrm/services/government_worker_importer.py:647`
  - Add `@rate_limit(key="ip", limit=20, seconds=3600)` to the three `*_limited` endpoints in `egrm/api/activation.py:338–353`.
- [ ] **A3. Arbitrary role grant via CSV** — `egrm/api/bulk_import.py:236–240`: restrict assignable roles to `{"GRM Intake", "GRM Review", "GRM Assignment", "GRM Investigate & Resolve", "GRM Feedback"}`; reject any other value with `frappe.throw`.
- [ ] **A4. Shared default password + non-CSPRNG** — `egrm/services/government_worker_importer.py:781,901–903`: move `_generate_temp_password` call inside the per-user loop; replace `random` with `secrets.choice`.
- [ ] **A5. Post-activation 404 redirect** — `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js:336`: change `"Platform"` → `"eGRM"`.
- [ ] **A6. Remove committed backup** — `git rm egrm/api/sync.py.bak.before-perf`; add `*.bak*` to `.gitignore`.
- [ ] **A7. Remove committed `node_modules` symlink** — `git rm egrm/public/node_modules` (already in `.gitignore:63` but was force-added).
- [ ] **A8. Gate `set_worker_passwords.py`** — `egrm/cli/set_worker_passwords.py`: top-of-function guard `if not frappe.conf.developer_mode: frappe.throw("dev-only")`.

---

## Group B — IMPORTANT auth & correctness

- [ ] **B1. Project-scope `get_departments_by_projects`** — `egrm/server_scripts/queries.py:89–126`: loop `_ensure_project_typeahead_access(p)` over each project in the input list.
- [ ] **B2. Project-scope `search_users`** — `egrm/egrm/page/grm_users/grm_users.py:264`: filter to users with at least one existing assignment in the current project, or scope by caller's project list.
- [ ] **B3. Constant-time OTP compare** — replace `if str(code) != str(stored)` with `hmac.compare_digest(...)` in:
  - `egrm/api/rating.py:126,190`
  - `egrm/api/appeal.py:126`
  - `egrm/api/public_submit.py:318`
- [ ] **B4. Defense-in-depth on `permission_query_conditions`** — `egrm/server_scripts/grm_issue_permissions.py:196–204`: also escape backslashes; add regex validator on `project_code` at the wizard input (`grm_project_wizard.py` Step 1) rejecting `[`';\\]`.
- [ ] **B5. Reconcile `ACTIVE_STATUSES`** — single source of truth:
  - `egrm/services/assignee_routing.py:51` (`("Activated", "")`)
  - `egrm/services/duty_coverage.py:105` (`('Activated', 'Pending Activation', '')`)
  - Decide: include `"Pending Activation"` in both (recommended) or in neither; expose as `egrm.services._constants.ACTIVE_ASSIGNMENT_STATUSES`.
- [ ] **B6. i18n-safe workspace filter** — `egrm/public/js/egrm_workspace_filter.js:33–39`: match cards by `data-egrm-phase="intake|triage|..."` attribute injected from the workspace JSON, instead of comparing literal English text.
- [ ] **B7. `app_route_passthrough` deny list** — `egrm/utils/app_route_passthrough.py:_is_passthrough_path`: explicitly reject `app/api/`, `app/method/`, `app/files/`.
- [ ] **B8. CSV filename collision** — `egrm/services/user_import.py:720`: replace `int(time.time())` suffix with `frappe.generate_hash(length=8)`.
- [ ] **B9. Wizard double-submit guards** — `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js:1598` and any other step add/save: add `if (this._submitting) return; this._submitting = true;` flag class-side (mirror `grm_users.js:43`).
- [ ] **B10. `Step1.save()` batched RPC** — `grm_project_wizard.js:581–587`: replace per-field `frappe.db.set_value` loop with one `frappe.db.set_value(dt, name, {...})` call.
- [ ] **B11. `goto_step()` unsaved-data guard** — `grm_project_wizard.js:314`: if `current_step.is_dirty()`, show `frappe.confirm("Discard unsaved changes?")` before switching.
- [ ] **B12. CSV/XLSX row cap** — `egrm/services/user_import.py:721`: reject imports >10,000 rows with `frappe.throw`. Stream-parse if larger imports are required.
- [ ] **B13. `_bulk_insert_users_sql` documentation** — `egrm/services/government_worker_importer.py:687`: add a comment explaining which `User` controller side-effects are intentionally skipped (search index, before_insert hooks, mandatory validation) and which compensating logic (`_post_insert_grant_duty_roles`, `_bulk_set_passwords`) covers them. Alternative: switch to ORM `insert(ignore_mandatory=True)`.
- [ ] **B14. PII in error logs** — `egrm/api/activation.py:151,159,234,242,329`: switch from `frappe.log_error(f"... {email}: ...")` to `frappe.log_error(title="...", message=...)` (no email in the title; redact email in the message).

---

## Group C — Code-health cleanups (low risk)

- [ ] **C1. Fix `__all__`** — `egrm/services/__init__.py:3`: add `user_import`, `assignee_routing`, `duty_coverage`.
- [ ] **C2. Delete `_find_source_for`** — `egrm/services/user_import.py:910` (no callers).
- [ ] **C3. Drop unused param** — `egrm/services/admin_region_importer.py:160`: remove `rows` from `_detect_level_columns` signature.
- [ ] **C4. Simplify `category_routing.resolve_category_routing`** — `egrm/services/category_routing.py:40`: replace `frappe.get_doc("GRM Project Role", ...)` with `frappe.db.exists` (target_doc unused).
- [ ] **C5. Consolidate RPC coercion** — wizard wrappers (`grm_project_wizard_user_data_import.py`, `_user_import.py`, `_user_create.py`, `_user_assignments.py`) define local `_coerce_dict/_coerce_bool/_coerce_list`; these duplicate `egrm/utils/rest_form_decode.normalize_resource_form_dict` which is already registered as the universal REST normalizer in `hooks.py`. Remove per-endpoint coercion or import from `rest_form_decode`.
- [ ] **C6. Tuple assignment keys** — `egrm/services/government_worker_importer.py:530`: replace `f"{user}_{project}_{region}"` with tuple keys.
- [ ] **C7. Portal `postJson` extraction** — create `grm-portal/src/lib/api.ts`; move the duplicated `postJson<T>` and `csrf_token` cast out of `grm-portal/src/hooks/useAppeal.ts:9` and `useRating.ts:16`.
- [ ] **C8. Decide on `egrm/api/v1.py`** — `get_user_projects` (l.20) and `get_system_info` (l.87) are whitelisted but have no observable consumer. Either wire to the mobile API spec (`docs/superpowers/plans/2026-05-08-mobile-api-surface-test-plan.md`) or delete.
- [ ] **C9. Dead CLI scripts** — 13 modules under `egrm/cli/` (cleanup_catalog_dups, cleanup_region_dups, cleanup_role_dups, diag_dups, diag_region_chain, diag_regions, diag_user_roles, dump_errlog, dump_push_errors, inspect_reviewers, reset_test_state, seed_rdap, set_worker_passwords) have 0 callers and aren't in `pyproject.toml` `console_scripts`. Move to `scripts/dev-ops/` (outside the importable package) **or** add a `__DEV_ONLY__ = True` top-of-file marker for visibility. Choose one; do not delete without confirmation.
- [ ] **C10. Email-from-position dedup** — `egrm/services/government_worker_importer._generate_email_from_position` and `egrm/services/user_import._synthesize_email`: pick one signature, move to shared helper.

---

## Group D — Deferred to follow-up PR (DO NOT do in this PR)

These are large refactors. Doing them in the same PR as security fixes makes the diff impossible to review and increases revert risk. Track as separate tickets.

- [ ] **D1. Split `grm_project_wizard.js`** — 6,138 lines → per-step ES modules under `grm_project_wizard/steps/`.
- [ ] **D2. Split `user_import.py`** — 970 lines → `_user.py`, `_mapping.py`, `_region.py`, `_materialize.py`.
- [ ] **D3. Split `government_worker_importer.py`** — 945 lines → `bulk_creator.py`, `csv_parsing.py`, `activation_codes.py`.
- [ ] **D4. Split `grm_users.js`** — 915 lines → `form.js`, `table.js`, `typeahead.js`.
- [ ] **D5. CSV-reading helper** — extract `csv_utils` shared by `user_import`, `government_worker_importer`, `admin_region_importer`.
- [ ] **D6. Region-resolution helper** — extract from `user_import.resolve_region:235`, `_resolve_region_dryrun:924`, `admin_region_importer._create_region_at_level:316`.
- [ ] **D7. Routing helper consolidation** — fold `get_least_loaded_user` (queries.py:431) into `assignee_routing._pick_least_loaded` (l.214).
- [ ] **D8. Bulk-insert User path for `user_import.materialize_staged_csv`** — currently `get_doc().insert()` per row; mirror `gwi._bulk_insert_users_sql` once #B13 is documented.

---

## Verification gates (after each group lands)

```bash
# After Group A
bench --site <site> migrate  # idempotent
pytest egrm/tests/services/test_user_assignment_endpoints.py -v
pytest egrm/tests/services/test_user_import.py -v
# Manual: log in as Supervise user on Project A, attempt to PATCH/DELETE a Project B assignment via /api/method — must 403

# After Group B
pytest egrm/tests/ -v
# Manual: i18n test — switch site language, confirm workspace filter still hides phase cards correctly

# After Group C
ruff check egrm/
pyflakes egrm/
```
