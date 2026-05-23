# EGRM Onboarding Wizard — XD Fidelity Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four concrete gaps between the implemented onboarding wizard and the XD mockups (`docs/superpowers/plans/xd-links.md`): (1) Step 1 missing fields + instructional copy, (2) bulk admin region upload, (3) user creation step, (4) dedicated issue-routing finalization screen with **Department-or-Role routing propagated through every backend consumer** — and reorder steps to match XD literal ordering.

**Architecture:** All work lives inside the existing custom desk Page `egrm/page/grm_project_wizard` (JS classes per step + Python whitelisted endpoints in `grm_project_wizard.py`). New bulk endpoints reuse the proven CLI pipelines from `egrm/commands/admin_regions.py` (HierarchicalAdminProcessor) and `egrm/commands/create_government_workers.py` (OptimizedBulkWorkerCreator) — we extract the core logic into module-level functions that both the CLI and the new RPC endpoints call. Doctype changes are additive only (new optional fields on `GRM Project` for number/date/currency format; no destructive migrations). Gender (XD Step 4) is intentionally skipped — the existing hardcoded `GRM Issue.gender` Select stays.

**Tech Stack:** Frappe v16 (Python 3.10+, Bootstrap 4 desk pages, jQuery 3, Hooks/Whitelisted RPC, Materialized-path tree DocType pattern), Vitest-style AQE Queen test harness in `docs/superpowers/plans/aqe-generated/`, Playwright-driven UI screenshot suite (`run_ui_screenshots.py`).

> **v16 verification status (2026-05-09):** Every Frappe API used in this plan was verified against `frappe/frappe@version-16` (16.17.5): `frappe.db.get_list({limit:0})`, `frappe.db.get_doc`, `page.set_primary_action(label, fn, icon)`, `frappe.ui.form.make_control({df, parent, render_input:true})`, `frappe.dom.freeze/unfreeze`, `frappe.confirm`, `frappe.set_route`, `@frappe.whitelist()`, custom desk Page pattern, `frappe.ui.form.on(...)`. All intact in v16.

---

## Engineering Conventions (read before any task)

**Modularity & DRY are non-negotiable.** This plan touches three tightly coupled subsystems (wizard JS, service modules, doctype validations). If you find yourself copy-pasting more than 3 lines, stop and extract.

1. **One source of truth per concept.** Routing logic lives ONLY in `egrm/services/category_routing.py`. CSV import for regions lives ONLY in `egrm/services/admin_region_importer.py`. Worker creation lives ONLY in `egrm/services/government_worker_importer.py`. CLI commands and wizard RPC endpoints are thin façades — they call the service, they do not re-implement it.

2. **Extract shared helpers before duplicating.** Examples:
   - `_require_wizard_role()` lives in `grm_project_wizard.py` — reuse for every new whitelisted endpoint, do not copy the role-check. **Note:** the existing helper in the codebase is currently named `_gate()` (see `grm_project_wizard.py:42`); Phase A.0 below renames it to `_require_wizard_role` once. After that rename, every later phase MUST call `_require_wizard_role` and MUST NOT redefine it.
   - `dept_label()`, `role_label()`, `department_options()`, `role_options()` in the wizard JS — define ONCE on the IssueCategories step class, reuse from any inner render.
   - `resolve_department_name()` / `resolve_role_name()` in the AQE driver — define ONCE near the top of `run_onboarding_tests.py`, call from each LAYOUT runner.
   - `_read_file()` for CSV input — define ONCE per step class, reuse in `preview()` AND `do_import()`.
   - The Step 9 Users tabs (CSV / Auto-generate / Codes) and the Step 2 Regions tab share the same upload→validate→import flow — extract a small `BulkUploadController` mixin or shared base class rather than duplicating button wiring.

3. **Keep step classes ≤ 400 lines.** If a step class grows past 400 lines, split inner sub-renderers into their own classes (already done for `Step2AdminLevelsInner` + `Step2AdminRegionsInner`). Same for Python: if `grm_project_wizard.py` crosses 400 lines, split endpoints into a sibling module (e.g. `grm_project_wizard_endpoints.py`) and re-export.

4. **No inline duplication of string templates.** If a CSV header, an error message, or a confirmation prompt is needed in two places, define it as a module-level constant (Python) or a class static (JS).

5. **Reuse the existing AQE driver primitives.** `run_onboarding_tests.py` already has `api.call(...)`, LAYOUT iteration, and assertion helpers — extend them, do not parallel-build a new driver. New per-step assertions go in the existing assertion module.

6. **Prefer composition over inheritance for step classes.** A step that combines two concerns (e.g. Step 2 = Levels + Regions) renders both via a tab control and delegates to inner classes — see the `GRMWizardStep2AdminUnits` pattern. Do not subclass to add a tab.

7. **Type/identifier consistency across phases.** When Phase B renames a class, every later phase MUST use the new name. When Phase E.1 adds a doctype field, every later phase MUST reference that field name verbatim. Search the plan with grep before introducing a new identifier.

8. **Permission-Manager-style checkbox grid is the canonical pattern for any wizard step that maps "rows × toggle columns" with the ability to add/remove rows.** Reference implementation: `frappe/frappe/core/page/permission_manager/permission_manager.js` — study `frappe.PermissionEngine` before writing any new grid step. The pattern (pasted here so you don't have to re-discover it):
   - **Table layout per row.** Each row is one entity (a Project Role, a category, …); columns are descriptive cells (`add_cell()`) plus one cell that holds a `<div class='row'>` of `col-md-4` checkbox cells (`add_check()`). XD calls these "oui/non" toggles — they MUST be checkboxes, not Edit-form fields.
   - **Single delegated checkbox handler.** Don't bind one handler per checkbox. Bind ONCE on the table body: `this.body.on("click", "input[type='checkbox']", function () { ... frappe.call({ method: "update_<thing>", args: { ...data attributes... } }) ... })`. State is read off the input's `data-*` attributes (`data-role`, `data-duty`, `data-category`, etc.).
   - **Optimistic UI with revert.** On successful RPC, leave the checkbox alone; on `r.exc`, flip it back: `chk.prop("checked", !chk.prop("checked"))`. Use `frappe.dom.freeze()`/`unfreeze()` around the RPC.
   - **"Add New Rule" primary action.** Use `this.wizard.page.set_primary_action(__("Add Role"), () => { let d = new frappe.ui.Dialog({...}); d.set_primary_action(__("Add"), () => { frappe.call(...).then(() => this.refresh()); d.hide(); }); d.show(); }, "small-add")`. The dialog collects the minimum fields needed to seed a row; the row's checkboxes are then edited inline.
   - **Per-row delete button.** `<button class='btn btn-danger btn-remove-perm btn-xs'>${frappe.utils.icon("x")}</button>` appended to the last cell of each row, with `data-name` attribute, wired to a delete RPC that calls `this.refresh()` on success.
   - **Restore-defaults secondary action.** Where applicable (e.g. Step 7 Project Roles can be reseeded from `GRM_DEFAULT_DUTIES`), use `this.wizard.page.set_secondary_action(__("Restore Default Roles"), () => { ... })` mirroring `make_reset_button()`.
   - **Refresh strategy.** `refresh()` re-renders the whole table from a fresh `frappe.db.get_list` + `get_doc` fan-out. Do not patch the DOM in place — re-render. The delegated handler keeps working because event delegation is on the parent `body`.

   **Steps that MUST follow this pattern:**
   - Step 7 Project Roles (User Types) — duties become inline checkbox columns on each role row. xd-links.md line 11 explicitly says: *"these oui or no can be checkboxes as frappe does for permissions when setup … we should have add new which add a new row to the bottom and user edits ad we do for frappe permission edits."*
   - Any later step that grows beyond one toggle column (Step 10 Routing if it adds per-category multi-target editing; Step 8 Departments if heads/members become a grid; Step 5 Citizen Groups if multi-attribute toggles are added).

   **Steps that may keep simpler controls:** Step 3 Issue Categories (single inline routing toggle — Phase E.4 is fine as a single Select per row, not a grid). Step 11 SLAs (per-status numeric inputs, not toggles).

**Commit cadence:** This plan deliberately omits per-step commit instructions. Commit on a cadence that makes sense for your branch strategy — typically one commit per **Task** (not per Step) — using Conventional Commits as set in the repo root rules. Do not commit unless explicitly asked.

---

## File Structure

**Wizard (modify):**
- `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` — add 2 new step classes (`GRMWizardStep1bAdminUpload`, `GRMWizardStep9Users`, `GRMWizardStep10Routing`), enhance `GRMWizardStep1ProjectInfo`, **refactor `GRMWizardStep7ProjectRoles` (formerly `Step4ProjectRoles`) to the Permission-Manager-style checkbox grid** (Task B.2 — see Engineering Convention 8), rebuild `STEP_TITLES` + `step_class()` map for new ordering. Currently 3,161 lines — split into per-step files if it crosses 4,000.
- `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py` — add whitelisted endpoints: `parse_admin_regions_csv`, `bulk_insert_admin_regions`, `parse_users_csv`, `bulk_create_users`, `auto_generate_regional_users`, `export_activation_codes`, `update_category_routing`, **`project_role_add` + `project_role_toggle_duty` + `project_role_delete` + `project_role_seed_defaults`** (Task B.2). Currently 93 lines — will grow to ~700.

**Doctype (modify):**
- `egrm/egrm/doctype/grm_project/grm_project.json` — add `number_format`, `date_format`, `currency`, `time_zone`, `country` fields. Bump field_order accordingly.
- `egrm/egrm/doctype/grm_issue_category/grm_issue_category.json` — add `routing_target_type` (Select: Department/Role) field next to existing `assigned_department`.

**Reusable modules (extract from CLI):**
- `egrm/services/admin_region_importer.py` — extract `HierarchicalAdminProcessor` core logic from `commands/admin_regions.py` so both CLI and wizard RPC call shared functions.
- `egrm/services/government_worker_importer.py` — extract `OptimizedBulkWorkerCreator` core logic from `commands/create_government_workers.py` so both CLI and wizard RPC call shared functions.
- `egrm/services/category_routing.py` (NEW) — single source of truth for resolving a category's routing target (Department or Role). Every consumer that previously read `assigned_department` directly MUST switch to `resolve_category_routing()`.

**Backend consumers refactored to use the routing helper (Phase E.6):**
- `egrm/egrm/doctype/grm_issue/grm_issue.py` (line 580 — default routing on issue create; also adds new `assigned_role` field)
- `egrm/api/lookup.py` (lines 56-81 — mobile API enrichment)
- `egrm/server_scripts/queries.py` (lines 318-324 — auto-routing query)
- `egrm/number_card/number_card.py` (line 103 — dashboard SQL excludes role-routed categories)
- `egrm/egrm/doctype/grm_issue_category/grm_issue_category.py` (validation extended for `assigned_role`)
- `egrm/egrm/doctype/grm_issue_category/grm_issue_category.js` (typeahead `set_query` for `assigned_role`)
- `egrm/egrm/doctype/grm_issue_department/grm_issue_department.js` (annotation only — filter is correct)
- `egrm/egrm/doctype/grm_project_role/grm_project_role.js` (NEW or extended — mirror of dept "Issues" button)

**Out of scope:** appeal + escalation department fields stay department-only (`assigned_appeal_department`, `assigned_escalation_department`, plus the escalation cron in `scheduled_tasks.py:99` and `issue_actions.py:98-102`). Symmetric role-based escalation is a follow-up milestone.

**Tests (modify + add):**
- `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py` — extend `LAYOUTS` with `admin_regions_csv` + `users_csv` per project, add step assertions for new steps, update step-counter expectations.
- `docs/superpowers/plans/aqe-generated/run_ui_screenshots.py` — add screenshot capture for new steps (admin upload, users, routing).
- `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/RW-WB.csv` (NEW) — Rwanda 6-level region CSV for AQE seed.
- `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/KE-EAC.csv` (NEW) — Kenya 5-level.
- `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/STJ-HOSP.csv` (NEW) — Hospital 4-level non-geographic.
- `docs/superpowers/plans/aqe-generated/fixtures/users/RW-WB.csv` (NEW) — sample worker CSV.

---

## Phase A.0 — Prerequisite Renames & Constants

Before any later phase can reuse the wizard role-check helper, the existing private name `_gate()` in `egrm/page/grm_project_wizard/grm_project_wizard.py:42` must be renamed to `_require_wizard_role()` so every new endpoint can call it without redefining a parallel helper (Engineering Convention 2).

### Task A.0.1: Rename `_gate` → `_require_wizard_role`

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`

- [ ] **Step 1: Rename the function**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`, change:

```python
def _gate() -> None:
```

to:

```python
def _require_wizard_role() -> None:
```

- [ ] **Step 2: Update the single in-file call site**

In the same file, change `_gate()` (called from inside `activate_project`) to `_require_wizard_role()`.

- [ ] **Step 3: Verify there are no other callers**

Run: `grep -rn "_gate\b" /Users/victor/egrm/apps/egrm/egrm/`
Expected: zero hits (the helper is module-private; only `activate_project` calls it).

### Task A.0.2: Bump `current_setup_step` constant on activation to TOTAL_STEPS

The activation function currently hardcodes `current_setup_step: 12`. Phase B raises `TOTAL_STEPS` to 13 — the activation must follow.

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`

- [ ] **Step 1: Replace hardcoded 12 with module constant**

In `grm_project_wizard.py`, add near the top alongside `ALLOWED_PAGE_ROLES`:

```python
TOTAL_SETUP_STEPS = 13   # Must match TOTAL_STEPS in grm_project_wizard.js
```

Then in `activate_project()`, replace:

```python
"GRM Project", project, {"is_setup_complete": 1, "current_setup_step": 12},
```

with:

```python
"GRM Project", project, {"is_setup_complete": 1, "current_setup_step": TOTAL_SETUP_STEPS},
```

- [ ] **Step 2: Add a docstring note linking to JS counterpart**

Add a comment above the constant: `# Kept in lock-step with grm_project_wizard.js TOTAL_STEPS — bump both together.`

- [ ] **Step 3: Smoke verify**

After Phase B lands, run AQE full-suite for one layout and assert the activated project's `current_setup_step == 13`. Concrete check appears in Phase F.1 Step 1.

---

## Phase A — Step 1 ProjectInfo Enhancements

XD Step 0 shows: Project Name, Project Code, Country, Default Language, Number Format, Date Format, Currency, Time Zone, Logo, Description, Active flag, Citizen Feedback toggle — each preceded by a short instructional sentence. Implementation currently shows only 8 fields with no helper copy. Note: `default_language` is **already a `Link → Language`** field on the `GRM Project` doctype (verified in `grm_project.json`); the wizard JS (`grm_project_wizard.js:240`) renders it as a free-text `<input type="text">` instead of mounting the Link control. The doctype itself does NOT need to change for `default_language`. Only the wizard JS render needs to switch to a `make_control` Link, which Task A.2 already covers.

### Task A.1: Add missing fields to GRM Project doctype

**Files:**
- Modify: `egrm/egrm/doctype/grm_project/grm_project.json`
- Test: manual JSON schema validation

- [ ] **Step 1: Add new fields to field_order**

In `egrm/egrm/doctype/grm_project/grm_project.json`, insert into `field_order` after `"description"`:

```json
"country",
"number_format",
"date_format",
"currency",
"time_zone",
```

- [ ] **Step 2: Add field definitions**

In `egrm/egrm/doctype/grm_project/grm_project.json`, append to `fields` array:

```json
{ "fieldname": "country", "fieldtype": "Link", "label": "Country", "options": "Country" },
{ "fieldname": "number_format", "fieldtype": "Select", "label": "Number Format", "options": "#,###.##\n#.###,##\n# ###.##\n#,##,###.##", "default": "#,###.##" },
{ "fieldname": "date_format", "fieldtype": "Select", "label": "Date Format", "options": "yyyy-mm-dd\ndd-mm-yyyy\nmm-dd-yyyy\ndd/mm/yyyy\nmm/dd/yyyy", "default": "yyyy-mm-dd" },
{ "fieldname": "currency", "fieldtype": "Link", "label": "Currency", "options": "Currency" },
{ "fieldname": "time_zone", "fieldtype": "Autocomplete", "label": "Time Zone" },
```

- [ ] **Step 3: Verify schema parses (no migrate yet — will run with all phases)**

Run: `cd /Users/victor/egrm && python -c "import json; json.load(open('apps/egrm/egrm/egrm/doctype/grm_project/grm_project.json'))"`
Expected: no output (valid JSON).


### Task A.2: Rewrite Step 1 ProjectInfo render with helper copy and proper field controls

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js:188-331`
- Test: manual browser smoke + AQE screenshot suite Step 1

- [ ] **Step 1: Replace render() body to include section copy + new controls**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, replace the body of `GRMWizardStep1ProjectInfo.render()` (lines 196-260) with:

```javascript
render() {
    const p = this.project || {};
    const code_disabled = this.project ? "disabled" : "";
    const code_warning = this.project
        ? `<small class="text-muted">${__("Project code cannot be changed after creation.")}</small>`
        : `<small class="text-warning">${__("Heads up: project code becomes the record name and cannot be changed after save.")}</small>`;

    this.$body.html(`
        <div class="grm-step1-form" style="max-width: 760px;">

          <p class="text-muted">${__("Tell us about your project. The information below will appear across the platform — citizen-facing portals, mobile apps, and notification templates.")}</p>

          <h4 class="mt-4">${__("Identity")}</h4>
          <p class="text-muted small">${__("These fields identify your project to staff and citizens.")}</p>
          <div class="form-group">
            <label class="control-label reqd">${__("Project Code")}</label>
            <input type="text" class="form-control" id="grm-f-project_code"
                   value="${frappe.utils.escape_html(p.project_code || "")}" ${code_disabled}>
            ${code_warning}
          </div>
          <div class="form-group">
            <label class="control-label reqd">${__("Project Title")}</label>
            <input type="text" class="form-control" id="grm-f-title"
                   value="${frappe.utils.escape_html(p.title || "")}">
          </div>
          <div class="form-group">
            <label class="control-label">${__("Description")}</label>
            <textarea class="form-control" id="grm-f-description" rows="3">${frappe.utils.escape_html(p.description || "")}</textarea>
          </div>

          <h4 class="mt-4">${__("Schedule")}</h4>
          <p class="text-muted small">${__("Optional. Used in dashboards and to gate intake outside the project window.")}</p>
          <div class="row">
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Start Date")}</label>
                <input type="date" class="form-control" id="grm-f-start_date"
                       value="${frappe.utils.escape_html(p.start_date || "")}">
              </div>
            </div>
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("End Date")}</label>
                <input type="date" class="form-control" id="grm-f-end_date"
                       value="${frappe.utils.escape_html(p.end_date || "")}">
              </div>
            </div>
          </div>

          <h4 class="mt-4">${__("Locale")}</h4>
          <p class="text-muted small">${__("How dates, numbers, and currency are formatted across the platform. Default Language drives label translations for citizens and staff.")}</p>
          <div class="row">
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Country")}</label>
                <div id="grm-f-country-wrap"></div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Default Language")}</label>
                <div id="grm-f-default_language-wrap"></div>
              </div>
            </div>
          </div>
          <div class="row">
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Number Format")}</label>
                <select class="form-control" id="grm-f-number_format">
                  <option value="#,###.##" ${ (p.number_format || "#,###.##") === "#,###.##" ? "selected" : "" }>1,234.56 (en-US)</option>
                  <option value="#.###,##" ${ p.number_format === "#.###,##" ? "selected" : "" }>1.234,56 (de-DE)</option>
                  <option value="# ###.##"  ${ p.number_format === "# ###.##"  ? "selected" : "" }>1 234.56 (fr-FR)</option>
                  <option value="#,##,###.##" ${ p.number_format === "#,##,###.##" ? "selected" : "" }>1,23,456.78 (Indic)</option>
                </select>
              </div>
            </div>
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Date Format")}</label>
                <select class="form-control" id="grm-f-date_format">
                  ${["yyyy-mm-dd","dd-mm-yyyy","mm-dd-yyyy","dd/mm/yyyy","mm/dd/yyyy"].map(fmt =>
                    `<option value="${fmt}" ${ (p.date_format || "yyyy-mm-dd") === fmt ? "selected" : "" }>${fmt}</option>`).join("")}
                </select>
              </div>
            </div>
          </div>
          <div class="row">
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Currency")}</label>
                <div id="grm-f-currency-wrap"></div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Time Zone")}</label>
                <input type="text" class="form-control" id="grm-f-time_zone"
                       placeholder="Africa/Kigali"
                       value="${frappe.utils.escape_html(p.time_zone || "")}">
              </div>
            </div>
          </div>

          <h4 class="mt-4">${__("Operational Defaults")}</h4>
          <p class="text-muted small">${__("Project-wide behavioural defaults. You can adjust these later from project settings.")}</p>
          <div class="row">
            <div class="col-md-6">
              <div class="form-group">
                <label class="control-label">${__("Auto Escalation Days")}</label>
                <input type="number" min="0" class="form-control" id="grm-f-auto_escalation_days"
                       value="${p.auto_escalation_days != null ? p.auto_escalation_days : 7}">
                <small class="text-muted">${__("Days before an unresolved issue auto-escalates to the next tier.")}</small>
              </div>
            </div>
            <div class="col-md-6">
              <div class="form-group">
                <label class="checkbox">
                  <input type="checkbox" id="grm-f-enable_citizen_feedback" ${p.enable_citizen_feedback ? "checked" : ""}>
                  ${__("Enable Citizen Feedback")}
                </label>
                <small class="text-muted d-block">${__("Allow citizens to rate the resolution of their complaints.")}</small>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label class="checkbox">
              <input type="checkbox" id="grm-f-is_active" ${(p.is_active == null ? 1 : p.is_active) ? "checked" : ""}>
              ${__("Is Active")}
            </label>
            <small class="text-muted d-block">${__("Inactive projects are hidden from intake screens but stay queryable in reports.")}</small>
          </div>
        </div>
    `);

    this._mount_link_controls(p);
}
```

- [ ] **Step 2: Add `_mount_link_controls` method**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, insert immediately after the new `render()` method (before `read_form()`):

```javascript
_mount_link_controls(p) {
    const make = (parent_id, fieldname, doctype, value) => {
        const ctl = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname, options: doctype, label: "" },
            parent: this.$body.find(`#${parent_id}`)[0],
            render_input: true,
        });
        ctl.set_value(value || "");
        this[`_ctl_${fieldname}`] = ctl;
    };
    make("grm-f-country-wrap",          "country",          "Country",  p.country);
    make("grm-f-default_language-wrap", "default_language", "Language", p.default_language || "en");
    make("grm-f-currency-wrap",         "currency",         "Currency", p.currency);
}
```

- [ ] **Step 3: Update `read_form()` to include new fields**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, replace the body of `read_form()` (lines 262-277) with:

```javascript
read_form() {
    const get = (id) => this.$body.find(`#${id}`).val();
    const checked = (id) => this.$body.find(`#${id}`).is(":checked") ? 1 : 0;
    const trim = (v) => (v == null ? "" : String(v).trim());
    const auto_esc = parseInt(get("grm-f-auto_escalation_days"), 10);
    return {
        project_code: trim(get("grm-f-project_code")),
        title: trim(get("grm-f-title")),
        description: trim(get("grm-f-description")),
        start_date: trim(get("grm-f-start_date")) || null,
        end_date: trim(get("grm-f-end_date")) || null,
        country: this._ctl_country ? this._ctl_country.get_value() : "",
        default_language: this._ctl_default_language ? this._ctl_default_language.get_value() : "en",
        number_format: trim(get("grm-f-number_format")) || "#,###.##",
        date_format: trim(get("grm-f-date_format")) || "yyyy-mm-dd",
        currency: this._ctl_currency ? this._ctl_currency.get_value() : "",
        time_zone: trim(get("grm-f-time_zone")) || "",
        is_active: checked("grm-f-is_active"),
        enable_citizen_feedback: checked("grm-f-enable_citizen_feedback"),
        auto_escalation_days: isNaN(auto_esc) ? 7 : auto_esc,
    };
}
```

- [ ] **Step 4: Run AQE screenshot for Step 1 to verify**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_ui_screenshots.py --only-step 1 --project RW-WB`
Expected: PNG saved with all 4 sections (Identity, Schedule, Locale, Operational Defaults) visible.

- [ ] **Step 5: Run AQE onboarding test for project creation**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --layout RW-WB --until-step 1`
Expected: project created with `country`, `currency`, `time_zone`, `number_format`, `date_format` set.


---

## Phase B — Reorder Wizard to XD Literal Order

XD ordering: 0 Project Details → 1 Upload Admin Units → 2 Categories → 3 Sub-categories → ~~4 Gender (skipped)~~ → 5 Age Groups → 6 Demographic Groups → 7 Other Groups → 8 Notifications → 9 User Types → 10 Users → 11 Issue Routing → 12 Summary.

Implementation maps onto **12 steps** (Gender skipped, sub-categories implemented as IssueTypes, demographic+other-groups handled in one CitizenLookups step):

| New # | Title | Class | XD Origin |
|---|---|---|---|
| 1 | Project Information | `GRMWizardStep1ProjectInfo` | XD 0 |
| 2 | Administrative Levels & Regions | `GRMWizardStep2AdminUnits` (NEW — wraps existing `Step3AdminLevels` + new bulk upload) | XD 1 |
| 3 | Issue Categories | `GRMWizardStep3IssueCategories` (renamed from `Step5IssueCategories`) | XD 2 |
| 4 | Issue Types (Sub-categories) | `GRMWizardStep4IssueTypes` (renamed from `Step6IssueTypes`) | XD 3 |
| 5 | Citizen Groups (Age + Demographic + Other) | `GRMWizardStep5CitizenLookups` (renamed from `Step10CitizenLookups`) | XD 5,6,7 |
| 6 | Notification Templates | `GRMWizardStep6NotificationTemplates` (renamed from `Step11`) | XD 8 |
| 7 | User Types (Project Roles) | `GRMWizardStep7ProjectRoles` (renamed from `Step4ProjectRoles`) | XD 9 |
| 8 | Departments | `GRMWizardStep8Departments` (kept name) | (unchanged) |
| 9 | Users | `GRMWizardStep9Users` (NEW) | XD 10 |
| 10 | Issue Routing | `GRMWizardStep10Routing` (NEW) | XD 11 |
| 11 | SLAs | `GRMWizardStep11SLAs` (renamed from `Step9SLAs`) | (unchanged) |
| 12 | Issue Statuses | `GRMWizardStep12IssueStatuses` (renamed from `Step7IssueStatuses`) | (unchanged) |
| 13 | Activate / Summary | `GRMWizardStep13Activate` (renamed from `Step12Activate`) | XD 12 |

That gives **13 steps** total. Update `TOTAL_STEPS`, `STEP_TITLES`, `step_class()` map. Two new step classes (`Step2AdminUnits` and `Step9Users`, `Step10Routing`) are stubbed in this phase and built out in C/D/E.

> **Note:** Class identifiers carry the suffix only; we are *not* renaming the `name`-only doctype map keys or activation logic. Only the JS classes get renamed for clarity. Existing AQE step assertions reference step *numbers* not class names — only the LAYOUT step counts need updating.

### Task B.1: Update STEP_TITLES + TOTAL_STEPS + step_class() map

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js:10-26,98-114`

- [ ] **Step 1: Replace STEP_TITLES + TOTAL_STEPS**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, replace lines 10-26 with:

```javascript
const STEP_TITLES = [
    "",
    "Project Information",
    "Administrative Levels & Regions",
    "Issue Categories",
    "Issue Types",
    "Citizen Groups",
    "Notification Templates",
    "User Types",
    "Departments",
    "Users",
    "Issue Routing",
    "SLAs",
    "Issue Statuses",
    "Activate",
];

const TOTAL_STEPS = 13;
```

- [ ] **Step 2: Rewrite step_class() map**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, replace lines 98-114 with:

```javascript
step_class(n) {
    const map = {
        1:  GRMWizardStep1ProjectInfo,
        2:  GRMWizardStep2AdminUnits,
        3:  GRMWizardStep3IssueCategories,
        4:  GRMWizardStep4IssueTypes,
        5:  GRMWizardStep5CitizenLookups,
        6:  GRMWizardStep6NotificationTemplates,
        7:  GRMWizardStep7ProjectRoles,
        8:  GRMWizardStep8Departments,
        9:  GRMWizardStep9Users,
        10: GRMWizardStep10Routing,
        11: GRMWizardStep11SLAs,
        12: GRMWizardStep12IssueStatuses,
        13: GRMWizardStep13Activate,
    };
    return map[n] || null;
}
```

- [ ] **Step 3: Add stub classes for new steps + rename existing classes**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, search-and-replace these class names (whole-word, not the textual references in comments — verify each hit):

| Old | New |
|---|---|
| `GRMWizardStep3AdminLevels` | `GRMWizardStep2AdminLevelsInner` (about to be wrapped) |
| `GRMWizardStep5IssueCategories` | `GRMWizardStep3IssueCategories` |
| `GRMWizardStep6IssueTypes` | `GRMWizardStep4IssueTypes` |
| `GRMWizardStep10CitizenLookups` | `GRMWizardStep5CitizenLookups` |
| `GRMWizardStep11NotificationTemplates` | `GRMWizardStep6NotificationTemplates` |
| `GRMWizardStep4ProjectRoles` | `GRMWizardStep7ProjectRoles` |
| `GRMWizardStep8Departments` | (unchanged) |
| `GRMWizardStep9SLAs` | `GRMWizardStep11SLAs` |
| `GRMWizardStep7IssueStatuses` | `GRMWizardStep12IssueStatuses` |
| `GRMWizardStep12Activate` | `GRMWizardStep13Activate` |
| `GRMWizardStep2UptakeNotes` | (delete — Uptake Notes is folded into Step 1 helper copy) |

- [ ] **Step 4: Add temporary stub `GRMWizardStep2AdminUnits` (composite of legacy AdminLevels + future bulk-upload tabs)**

Insert after the Step 1 class definition:

```javascript
class GRMWizardStep2AdminUnits {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }
    render() {
        this.$body.html(`
            <div class="grm-step2-admin">
              <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item"><a class="nav-link active" data-toggle="tab" href="#grm-tab-levels">${__("Levels")}</a></li>
                <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#grm-tab-regions">${__("Regions")}</a></li>
              </ul>
              <div class="tab-content pt-3">
                <div class="tab-pane fade show active" id="grm-tab-levels"></div>
                <div class="tab-pane fade" id="grm-tab-regions"></div>
              </div>
            </div>
        `);
        this.levels_inner = new GRMWizardStep2AdminLevelsInner(this.$body.find("#grm-tab-levels"), this.project, this.wizard);
        // Phase C will mount: this.regions_inner = new GRMWizardStep2AdminRegionsInner(...)
        this.$body.find("#grm-tab-regions").html(`<p class="text-muted">${__("Bulk region upload — implemented in Phase C.")}</p>`);
    }
    async save() {
        return this.levels_inner.save();
    }
}
```

- [ ] **Step 5: Add stub `GRMWizardStep9Users` and `GRMWizardStep10Routing`**

Insert before the `GRMWizardStep13Activate` class:

```javascript
class GRMWizardStep9Users {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }
    render() {
        this.$body.html(`<p class="text-muted">${__("User creation — implemented in Phase D.")}</p>`);
    }
    async save() { return true; }
}

class GRMWizardStep10Routing {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }
    render() {
        this.$body.html(`<p class="text-muted">${__("Issue routing finalization — implemented in Phase E.")}</p>`);
    }
    async save() { return true; }
}
```

- [ ] **Step 6: Browser smoke — load wizard with each step number**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_ui_screenshots.py --project RW-WB`
Expected: 13 PNGs captured, no JS console errors.

- [ ] **Step 7: Update AQE LAYOUTS step expectations**

In `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`, find the assertion that the project's `current_setup_step` reaches 12 after full run. Update to 13. Search for `TOTAL_STEPS = 12`, `current_setup_step.*12`, etc., and bump.

### Task B.2: Refactor Step 7 ProjectRoles to Permission-Manager-style checkbox grid

**Why:** XD Step 9 explicitly calls for a checkbox-grid + add-row UI like Frappe's Permission Manager (`xd-links.md` line 11). The current `GRMWizardStep4ProjectRoles` (renamed to `GRMWizardStep7ProjectRoles` in B.1) hides duties behind an Edit form — every duty toggle requires opening a form, ticking checkboxes, then Save. The XD expects each role to be one row in a table with duties shown inline as checkboxes that save on click. Reference: `frappe/frappe/core/page/permission_manager/permission_manager.js` (see Engineering Convention 8 above for the full pattern).

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` (rewrite `GRMWizardStep7ProjectRoles` body — keep `load_lookups()`, replace `render_table()` + `render_form()` + `start_add()` + `start_edit()` with grid pattern)
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py` (add 3 endpoints)

- [ ] **Step 1: Add three whitelisted endpoints in `grm_project_wizard.py`**

Add to `grm_project_wizard.py`:

```python
@frappe.whitelist()
def project_role_add(project: str, role_name: str, admin_level: str | None = None) -> dict:
    """Create a new GRM Project Role row (no duties yet — duties are toggled inline)."""
    _require_wizard_role()
    project = (project or "").strip()
    role_name = (role_name or "").strip()
    if not project or not role_name:
        frappe.throw(_("project and role_name are required"))
    if frappe.db.exists("GRM Project Role", {"project": project, "role_name": role_name}):
        frappe.throw(_("A role named {0} already exists for this project.").format(role_name))
    doc = frappe.get_doc({
        "doctype": "GRM Project Role",
        "project": project,
        "role_name": role_name,
        "admin_level": admin_level or None,
        "is_active": 1,
        "duties": [],
    }).insert()
    return {"name": doc.name, "role_name": doc.role_name}


@frappe.whitelist()
def project_role_toggle_duty(role: str, duty: str, value: int) -> dict:
    """Add or remove a single duty on a Project Role. Idempotent."""
    _require_wizard_role()
    role = (role or "").strip()
    duty = (duty or "").strip()
    if not role or not duty:
        frappe.throw(_("role and duty are required"))
    doc = frappe.get_doc("GRM Project Role", role)
    existing = {d.duty for d in (doc.duties or [])}
    want = bool(int(value))
    if want and duty not in existing:
        doc.append("duties", {"duty": duty})
        doc.save()
    elif not want and duty in existing:
        doc.duties = [d for d in doc.duties if d.duty != duty]
        doc.save()
    return {"role": role, "duty": duty, "value": 1 if want else 0}


@frappe.whitelist()
def project_role_delete(role: str) -> dict:
    """Delete a Project Role (only if no users currently bound)."""
    _require_wizard_role()
    role = (role or "").strip()
    if not role:
        frappe.throw(_("role is required"))
    bound = frappe.db.count("GRM Government Worker", {"project_role": role})
    if bound:
        frappe.throw(_("Cannot delete: {0} user(s) currently use this role.").format(bound))
    frappe.delete_doc("GRM Project Role", role)
    return {"deleted": role}
```

The role-check `_require_wizard_role()` is the existing helper — DO NOT redefine it (Engineering Convention 2).

- [ ] **Step 2: Replace the body of `GRMWizardStep7ProjectRoles` in the wizard JS**

Replace the entire class body (after the existing `load_lookups()` method, which is kept verbatim) with this grid implementation:

```javascript
class GRMWizardStep7ProjectRoles {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];          // [{name, role_name, admin_level, is_active, duties: Set<string>}]
        this.admin_levels = [];
        this.duties = [];        // [{name, label, lifecycle_phase}]
        this.render();
    }

    async render() {
        if (!this.project) {
            this.$body.html(`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`);
            return;
        }
        this.$body.html(`
            <div class="grm-step7-roles" style="max-width: 1180px;">
              <div class="grm-step7-intro" style="margin-bottom: 12px;">
                <p>${__("Define the project's user types (e.g. \"District GRM Officer\") and tick the duties each role performs in the case lifecycle.")}</p>
                <p class="text-muted small">${__("Click a checkbox to toggle a duty — saves immediately. Use \"Add Role\" to create a new row.")}</p>
              </div>
              <div class="grm-perm-engine" style="min-height: 200px;"></div>
            </div>
        `);
        this.body = this.$body.find(".grm-perm-engine");
        this.install_page_actions();
        this.add_check_events();
        await this.load_lookups();    // unchanged from existing implementation
        await this.refresh();
    }

    install_page_actions() {
        // Primary action: open Add-Role dialog (mirrors permission_manager show_add_rule)
        this.wizard.page.set_primary_action(__("Add Role"), () => this.show_add_role_dialog(), "small-add");
        // Secondary action: restore default roles seeded from GRM_DEFAULT_DUTIES
        this.wizard.page.set_secondary_action(__("Restore Default Roles"), () => this.restore_defaults());
    }

    async refresh() {
        const list_rows = await frappe.db.get_list("GRM Project Role", {
            filters: { project: this.project.name },
            fields: ["name", "role_name", "admin_level", "is_active"],
            limit: 0,
            order_by: "role_name asc",
        });
        const docs = await Promise.all(
            list_rows.map((r) => frappe.db.get_doc("GRM Project Role", r.name).catch(() => null)),
        );
        this.rows = list_rows.map((r, i) => {
            const doc = docs[i];
            const duties = new Set(
                doc && Array.isArray(doc.duties) ? doc.duties.map((d) => d.duty).filter(Boolean) : [],
            );
            return Object.assign({}, r, { duties });
        });
        this.render_table();
    }

    render_table() {
        if (!this.rows.length) {
            this.body.html(`
                <p class="text-muted">${__("No roles yet — click \"Add Role\" to create the first one.")}</p>
            `);
            return;
        }
        const headers = `
            <thead>
              <tr>
                <th style="width:220px;">${__("Role")}</th>
                <th style="width:160px;">${__("Admin Level")}</th>
                <th>${__("Duties")}</th>
                <th style="width:60px;"></th>
              </tr>
            </thead>
        `;
        this.body.html(`
            <table class="table table-bordered table-sm grm-perm-table">
              ${headers}
              <tbody></tbody>
            </table>
        `);
        const $tbody = this.body.find("tbody");
        for (const row of this.rows) {
            const $tr = $("<tr>").attr("data-name", row.name).appendTo($tbody);
            this.add_cell($tr, row.role_name || row.name);
            this.add_cell($tr, row.admin_level || "");
            const $duty_cell = $("<td class='pt-2'>").appendTo($tr);
            const $duty_row = $("<div class='row'></div>").appendTo($duty_cell);
            for (const d of this.duties) {
                this.add_check($duty_row, row, d);
            }
            this.add_delete_button($tr, row);
        }
    }

    add_cell($tr, text) {
        return $("<td class='pt-3'>").text(text || "").appendTo($tr);
    }

    add_check($cell, row, duty) {
        const checked = row.duties.has(duty.name) ? "checked" : "";
        const $box = $(`
            <div class='col-md-4'>
              <div class='checkbox'>
                <label>
                  <input type='checkbox' ${checked}>
                  ${frappe.utils.escape_html(duty.label)}
                </label>
              </div>
            </div>
        `).appendTo($cell);
        $box.find("input")
            .attr("data-role", row.name)
            .attr("data-duty", duty.name);
        return $box;
    }

    add_delete_button($tr, row) {
        const $td = $("<td class='pt-3'>").appendTo($tr);
        $(`<button class='btn btn-danger btn-remove-perm btn-xs' title='${__("Delete role")}'>${frappe.utils.icon("x")}</button>`)
            .appendTo($td)
            .attr("data-name", row.name)
            .on("click", () => this.confirm_delete(row));
    }

    add_check_events() {
        // Single delegated handler — survives re-renders because it's bound on this.body.
        const me = this;
        this.body.on("click", "input[type='checkbox']", function () {
            const $chk = $(this);
            const role = $chk.attr("data-role");
            const duty = $chk.attr("data-duty");
            const value = $chk.prop("checked") ? 1 : 0;
            frappe.dom.freeze();
            frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_toggle_duty",
                args: { role, duty, value },
                callback: (r) => {
                    frappe.dom.unfreeze();
                    if (r.exc) {
                        // Revert on failure (mirrors permission_manager.js).
                        $chk.prop("checked", !$chk.prop("checked"));
                        return;
                    }
                    // Update local cache so subsequent re-renders are consistent.
                    const row = me.rows.find((x) => x.name === role);
                    if (row) {
                        if (value) row.duties.add(duty);
                        else row.duties.delete(duty);
                    }
                },
            });
        });
    }

    show_add_role_dialog() {
        const d = new frappe.ui.Dialog({
            title: __("Add User Type"),
            fields: [
                {
                    fieldtype: "Data",
                    label: __("Role Name"),
                    fieldname: "role_name",
                    reqd: 1,
                    description: __("e.g. District GRM Officer"),
                },
                {
                    fieldtype: "Select",
                    label: __("Administrative Level (optional)"),
                    fieldname: "admin_level",
                    options: ["", ...this.admin_levels.map((l) => l.name)].join("\n"),
                    description: __("Bind this role to an admin level (e.g. District). Leave blank for project-wide roles."),
                },
            ],
        });
        d.set_primary_action(__("Add"), () => {
            const args = d.get_values();
            if (!args || !args.role_name) return;
            frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_add",
                args: { project: this.project.name, role_name: args.role_name, admin_level: args.admin_level || null },
                callback: (r) => {
                    if (r.exc) return;
                    d.hide();
                    this.refresh();
                },
            });
        });
        d.show();
    }

    confirm_delete(row) {
        frappe.confirm(
            __("Delete role {0}? This cannot be undone.", [row.role_name || row.name]),
            () => {
                frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_delete",
                    args: { role: row.name },
                    callback: (r) => {
                        if (!r.exc) this.refresh();
                    },
                });
            },
        );
    }

    restore_defaults() {
        // Seeds any missing default roles (one per duty in GRM_DEFAULT_DUTIES if not already present).
        // Pattern mirrors permission_manager.make_reset_button — confirm, then call a "restore" RPC.
        frappe.confirm(
            __("Restore the default roles & duties for this project? Existing roles are preserved; only missing defaults are added."),
            () => {
                // Reuse existing seeding helper; if absent, create one in grm_project_wizard.py
                // that loops GRM_DEFAULT_DUTIES and calls project_role_add() per missing role.
                frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_seed_defaults",
                    args: { project: this.project.name },
                    callback: (r) => {
                        if (!r.exc) this.refresh();
                    },
                });
            },
        );
    }

    async load_lookups() {
        // Unchanged from the legacy class — kept verbatim:
        try {
            this.admin_levels = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project: this.project.name },
                fields: ["name", "level_name"],
                limit: 0,
                order_by: "level_order asc",
            });
        } catch (e) { this.admin_levels = []; }
        try {
            const duty_rows = await frappe.db.get_list("GRM Duty", {
                fields: ["name", "duty_name", "label", "lifecycle_phase"],
                limit: 0,
                order_by: "lifecycle_phase asc",
            });
            this.duties = (duty_rows && duty_rows.length)
                ? duty_rows.map((d) => ({ name: d.name, label: d.label || d.duty_name || d.name, lifecycle_phase: d.lifecycle_phase || "" }))
                : GRM_DEFAULT_DUTIES.slice();
        } catch (e) { this.duties = GRM_DEFAULT_DUTIES.slice(); }
    }

    async save() {
        // Grid is auto-saved per-click. Validate that at least one role exists with at least one duty.
        const ok_rows = this.rows.filter((r) => r.duties && r.duties.size > 0);
        if (!ok_rows.length) {
            frappe.throw(__("Define at least one role with at least one duty before continuing."));
        }
        return true;
    }
}
```

- [ ] **Step 3: Add `project_role_seed_defaults` endpoint (used by Restore Default Roles)**

Add to `grm_project_wizard.py`:

```python
@frappe.whitelist()
def project_role_seed_defaults(project: str) -> dict:
    """Idempotently insert any missing default project roles for this project.

    Default roles are derived from the universal duty catalog (GRM Duty) — one role per
    lifecycle phase, mirroring the legacy GRM_DEFAULT_DUTIES list in the wizard JS.
    Existing roles are left untouched.
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(_("project is required"))

    # Defaults: one role per lifecycle phase. Duty names taken from GRM Duty if present,
    # otherwise the JS-side fallback constants.
    defaults = [
        ("Intake Officer",            ["Intake"]),
        ("Review Officer",            ["Review"]),
        ("Assignment Officer",        ["Assignment"]),
        ("Investigation Officer",     ["Investigate & Resolve"]),
        ("Feedback Officer",          ["Feedback"]),
        ("Supervisor",                ["Supervise"]),
    ]
    added: list[str] = []
    for role_name, duty_names in defaults:
        if frappe.db.exists("GRM Project Role", {"project": project, "role_name": role_name}):
            continue
        doc = frappe.get_doc({
            "doctype": "GRM Project Role",
            "project": project,
            "role_name": role_name,
            "is_active": 1,
            "duties": [{"duty": d} for d in duty_names if frappe.db.exists("GRM Duty", d)],
        }).insert()
        added.append(doc.name)
    return {"added": added, "count": len(added)}
```

- [ ] **Step 4: Run the wizard, verify the grid renders, smoke each interaction**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_ui_screenshots.py --project RW-WB --steps 7`

Manual checks (one browser session):
1. Step 7 loads with default roles already present (or empty + visible "Add Role" primary button).
2. Click a duty checkbox in any row → saved indicator briefly visible → reload page → checkbox state preserved.
3. Click "Add Role" → dialog opens with Role Name + Admin Level (Select populated from project's admin levels) → Add → new row appears at bottom.
4. Click delete-X on a role with no users bound → confirm → row disappears.
5. Click delete-X on a role with users bound → error message (count > 0).
6. Click "Restore Default Roles" → confirm → any missing default roles re-seeded (no duplicates).

- [ ] **Step 5: Add AQE assertion for Step 7 grid behavior**

In `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`, extend the Step 7 assertion to:
1. Call `project_role_add` for one custom role.
2. Call `project_role_toggle_duty` for two duties on that role.
3. Re-fetch the role doc and assert both duties present in `duties` child table.
4. Call `project_role_toggle_duty` with `value=0` for one duty; assert it was removed.
5. Call `project_role_delete` for the custom role; assert role deleted.

Reuse existing `api.call(...)` helper — do not parallel-build a new HTTP client (Engineering Convention 5).


---

## Phase C — Step 2 Admin Units Bulk Upload (Regions tab)

The legacy `Step3AdminLevels` (now `Step2AdminLevelsInner`) only captures level *metadata* (level_order + name). Citizens need actual *regions* — administrative units like provinces, districts, sectors. The CLI `egrm/commands/admin_regions.py` already imports them from CSV with proper materialized paths; we extract its core into a reusable service module and add a Regions tab to Step 2.

### Task C.1: Extract HierarchicalAdminProcessor into shared service module

**Files:**
- Create: `egrm/services/__init__.py`
- Create: `egrm/services/admin_region_importer.py`
- Modify: `egrm/commands/admin_regions.py` (call the new service)

- [ ] **Step 1: Create services package**

Create `egrm/services/__init__.py`:

```python
"""Shared service-layer utilities. Used by both CLI commands and whitelisted RPC endpoints."""

__all__ = ["admin_region_importer", "government_worker_importer"]
```

- [ ] **Step 2: Read existing HierarchicalAdminProcessor**

Run: `grep -n "class HierarchicalAdminProcessor" /Users/victor/egrm/apps/egrm/egrm/commands/admin_regions.py`
Then read the entire class (typically ~300 lines).

- [ ] **Step 3: Move HierarchicalAdminProcessor + helpers into the service module**

Create `egrm/services/admin_region_importer.py`. Body:

```python
"""Project-scoped administrative region bulk-importer.

This module is the single source of truth for hierarchical admin-region
ingestion. The CLI command (``import-admin-regions``) and the wizard
RPC endpoint (``parse_admin_regions_csv`` / ``bulk_insert_admin_regions``)
both call ``HierarchicalAdminProcessor``.

The importer:
1. Validates the CSV header (level columns + optional Latitude/Longitude).
2. Auto-creates the highest-level GRM Administrative Level Type
   (level_order=0) plus any missing inner levels (level_order=1..N).
3. Inserts GRM Administrative Region rows with parent_region links and
   computes the materialized ``path`` field.
4. Returns a structured report (created/updated counts, errors).
"""

# (Move the entire HierarchicalAdminProcessor class + its module-level
#  constants and helper functions here verbatim. Do not refactor logic;
#  only relocate.)

# Add a slim public API at the bottom:
def parse_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Parse + validate CSV. Returns {'preview': [...], 'errors': [...]}.

    Does NOT touch the database — safe for a wizard preview pane.
    """
    proc = HierarchicalAdminProcessor(project=project, highest_level=highest_level)
    return proc.parse_only(csv_text)


def import_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Parse + validate + insert. Returns {'created': N, 'updated': N, 'errors': [...]}."""
    proc = HierarchicalAdminProcessor(project=project, highest_level=highest_level)
    return proc.run(csv_text)
```

- [ ] **Step 4: Add `parse_only` method to HierarchicalAdminProcessor**

In `egrm/services/admin_region_importer.py`, add to the class:

```python
def parse_only(self, csv_text: str) -> dict:
    """Validate CSV without writing. Returns preview rows and errors."""
    rows = list(self._read_csv_rows(csv_text))
    errors = self._validate_rows(rows)
    return {
        "preview": rows[:50],  # cap preview to 50 rows for UI
        "total_rows": len(rows),
        "errors": errors,
        "highest_level": self.highest_level,
        "level_columns": self._detect_level_columns(rows),
    }
```

(The `_read_csv_rows`, `_validate_rows`, `_detect_level_columns` helpers should already exist or be trivially extractable from the existing `run()` method — split rather than duplicate.)

- [ ] **Step 5: Update CLI to call the service**

In `egrm/commands/admin_regions.py`, replace the inline `HierarchicalAdminProcessor` definition with:

```python
from egrm.services.admin_region_importer import HierarchicalAdminProcessor, import_csv  # noqa: F401
```

Verify the CLI command body now just calls `import_csv(project, highest_level, csv_text)`.

- [ ] **Step 6: Smoke the service directly (NOT the click command)**

`egrm.commands.admin_regions.import_admin_regions` is `@click.command(...)`-decorated, so `bench execute` cannot invoke it (Click intercepts via `sys.exit`). Smoke the service function instead — it accepts CSV **text**, not a file path:

```bash
cd /Users/victor/egrm && \
  bench --site egrm.local execute egrm.services.admin_region_importer.import_csv \
    --kwargs '{"project": "RW-WB", "highest_level": "Country", "csv_text": "Province,District\nKigali,Gasabo\n"}'
```

Expected: dict with `created`, `updated`, `errors` keys; row count matches CSV.

Then run the click command end-to-end against a temp file (this exercises the CLI façade — invoke from the shell, not via `bench execute`):

```bash
echo -e "Province,District\nKigali,Gasabo\n" > /tmp/sample_regions.csv
bench --site egrm.local import-admin-regions Country RW-WB /tmp/sample_regions.csv
```

Expected: same row counts as the service smoke.

### Task C.2: Add whitelisted RPC endpoints for region preview + import

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`
- Test: `egrm/tests/test_wizard_admin_upload.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `egrm/tests/test_wizard_admin_upload.py`:

```python
import frappe
import pytest

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
    parse_admin_regions_csv,
    bulk_insert_admin_regions,
)


@pytest.fixture
def sample_project():
    code = "TEST-ADMIN-UPLOAD"
    if not frappe.db.exists("GRM Project", code):
        frappe.get_doc({
            "doctype": "GRM Project",
            "project_code": code,
            "title": "Test Admin Upload",
        }).insert(ignore_permissions=True)
    yield code
    frappe.delete_doc("GRM Project", code, force=True)


def test_parse_admin_regions_csv_returns_preview(sample_project):
    csv_text = "Province,District,Sector\nKigali,Gasabo,Kacyiru\nKigali,Gasabo,Remera\n"
    result = parse_admin_regions_csv(project=sample_project, highest_level="Country", csv_text=csv_text)
    assert result["total_rows"] == 2
    assert "Kigali" in str(result["preview"])
    assert result["errors"] == []


def test_bulk_insert_admin_regions_creates_levels_and_regions(sample_project):
    csv_text = "Province,District\nKigali,Gasabo\n"
    result = bulk_insert_admin_regions(project=sample_project, highest_level="Country", csv_text=csv_text)
    assert result["created"] >= 3  # Country (auto), Kigali, Gasabo
    levels = frappe.get_all("GRM Administrative Level Type", filters={"project": sample_project})
    assert len(levels) >= 3
```

- [ ] **Step 2: Run test (expect FAIL — endpoints not defined)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_wizard_admin_upload`
Expected: ImportError on `parse_admin_regions_csv`.

- [ ] **Step 3: Add endpoints to grm_project_wizard.py**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`, append:

```python
# `frappe` and `_require_wizard_role` are already imported/defined at the top of
# grm_project_wizard.py — DO NOT redefine. (Engineering Convention 2; see Phase A.0.1.)
from egrm.services.admin_region_importer import (
    parse_csv as _parse_admin_csv,
    import_csv as _import_admin_csv,
)


@frappe.whitelist()
def parse_admin_regions_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Validate-only preview of a region CSV. Does not write."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _parse_admin_csv(project=project, highest_level=highest_level, csv_text=csv_text)


@frappe.whitelist()
def bulk_insert_admin_regions(project: str, highest_level: str, csv_text: str) -> dict:
    """Validate + insert regions. Returns counts and any errors."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _import_admin_csv(project=project, highest_level=highest_level, csv_text=csv_text)
```

- [ ] **Step 4: Run test (expect PASS)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_wizard_admin_upload`
Expected: 2 passed.


### Task C.3: Build the Regions tab UI in Step 2

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` (insert `GRMWizardStep2AdminRegionsInner`)

- [ ] **Step 1: Write the inner class**

Insert into `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` after `GRMWizardStep2AdminLevelsInner`:

```javascript
class GRMWizardStep2AdminRegionsInner {
    constructor($container, project, wizard) {
        this.$container = $container;
        this.project = project;
        this.wizard = wizard;
        this.parsed = null;
        this.render();
    }

    render() {
        this.$container.html(`
            <p class="text-muted">${__("Upload a CSV with one column per administrative level (e.g. Province, District, Sector). The highest level is auto-created from the project's country.")}</p>
            <div class="form-group">
              <label>${__("Highest level (single value, applied to all rows)")}</label>
              <input type="text" class="form-control" id="grm-rg-highest" placeholder="Country" value="Country">
            </div>
            <div class="form-group">
              <label>${__("CSV file")}</label>
              <input type="file" accept=".csv" id="grm-rg-file" class="form-control-file">
            </div>
            <button class="btn btn-default btn-sm" id="grm-rg-preview">${__("Preview")}</button>
            <button class="btn btn-primary btn-sm" id="grm-rg-import" disabled>${__("Import Regions")}</button>
            <div id="grm-rg-result" class="mt-3"></div>
        `);
        this.$container.find("#grm-rg-preview").on("click", () => this.preview());
        this.$container.find("#grm-rg-import").on("click",  () => this.do_import());
    }

    async _read_file() {
        const file = this.$container.find("#grm-rg-file")[0].files[0];
        if (!file) {
            frappe.show_alert({ message: __("Pick a CSV first."), indicator: "orange" });
            return null;
        }
        return await file.text();
    }

    async preview() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.parse_admin_regions_csv",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        this.parsed = r.message;
        this._render_preview();
    }

    _render_preview() {
        const p = this.parsed;
        const $r = this.$container.find("#grm-rg-result").empty();
        if (p.errors && p.errors.length) {
            $r.append(`<div class="alert alert-danger"><strong>${__("Errors")}:</strong><ul>${p.errors.map(e => `<li>${frappe.utils.escape_html(e)}</li>`).join("")}</ul></div>`);
            this.$container.find("#grm-rg-import").prop("disabled", true);
            return;
        }
        $r.append(`<div class="alert alert-info">${__("Detected {0} rows across levels: {1}", [p.total_rows, p.level_columns.join(" → ")])}</div>`);
        const cols = p.level_columns;
        const $tbl = $(`<table class="table table-sm table-bordered"><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody></tbody></table>`);
        p.preview.forEach(row => {
            $tbl.find("tbody").append(`<tr>${cols.map(c => `<td>${frappe.utils.escape_html(row[c] || "")}</td>`).join("")}</tr>`);
        });
        $r.append($tbl);
        this.$container.find("#grm-rg-import").prop("disabled", false);
    }

    async do_import() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_insert_admin_regions",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        const m = r.message;
        const $r = this.$container.find("#grm-rg-result").empty();
        $r.append(`<div class="alert alert-success">${__("Imported {0} regions ({1} updated). {2} errors.", [m.created, m.updated, (m.errors || []).length])}</div>`);
        if (m.errors && m.errors.length) {
            $r.append(`<ul>${m.errors.map(e => `<li class="text-danger">${frappe.utils.escape_html(e)}</li>`).join("")}</ul>`);
        }
    }

    async save() {
        // The Regions tab does not gate step navigation — bulk upload is optional.
        return true;
    }
}
```

- [ ] **Step 2: Mount it in `GRMWizardStep2AdminUnits.render()`**

Replace the placeholder line in `GRMWizardStep2AdminUnits.render()`:

```javascript
this.$body.find("#grm-tab-regions").html(`<p class="text-muted">${__("Bulk region upload — implemented in Phase C.")}</p>`);
```

with:

```javascript
this.regions_inner = new GRMWizardStep2AdminRegionsInner(this.$body.find("#grm-tab-regions"), this.project, this.wizard);
```

And update `save()` to wait for both:

```javascript
async save() {
    const ok1 = await this.levels_inner.save();
    if (!ok1) return false;
    return this.regions_inner.save();
}
```

- [ ] **Step 3: AQE Regions upload smoke**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --layout RW-WB --until-step 2`
Expected: regions imported, `current_setup_step=2`.


### Task C.4: Seed AQE fixtures for region CSVs

**Files:**
- Create: `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/RW-WB.csv`
- Create: `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/KE-EAC.csv`
- Create: `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/STJ-HOSP.csv`
- Modify: `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`

- [ ] **Step 1: Write RW-WB CSV (Province → District → Sector)**

Create `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/RW-WB.csv`:

```csv
Province,District,Sector
Kigali,Gasabo,Kacyiru
Kigali,Gasabo,Remera
Kigali,Nyarugenge,Nyarugenge
Northern,Musanze,Muhoza
Eastern,Kayonza,Mukarange
```

- [ ] **Step 2: Write KE-EAC CSV (County → Sub-County)**

Create `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/KE-EAC.csv`:

```csv
County,Sub-County
Nairobi,Westlands
Nairobi,Dagoretti
Mombasa,Mvita
Kisumu,Kisumu Central
```

- [ ] **Step 3: Write STJ-HOSP CSV (Wing → Department → Ward)**

Create `docs/superpowers/plans/aqe-generated/fixtures/admin_regions/STJ-HOSP.csv`:

```csv
Wing,Department,Ward
North,Cardiology,Ward A
North,Cardiology,Ward B
South,Pediatrics,Ward C
East,Maternity,Ward D
```

- [ ] **Step 4: Wire fixtures into LAYOUTS**

In `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`, find each LAYOUT entry (RW-WB, KE-EAC, STJ-HOSP). Add to each:

```python
"admin_regions_csv_path": "fixtures/admin_regions/RW-WB.csv",  # adjust per layout
"admin_regions_highest_level": "Country",  # for RW-WB / KE-EAC; "Hospital" for STJ-HOSP
```

- [ ] **Step 5: Add test step driver**

In `run_onboarding_tests.py`, find the function that walks Step 2 (formerly `Step3AdminLevels`). After the levels are saved, add a sub-call:

```python
# Step 2 — Regions tab (bulk upload)
csv_text = pathlib.Path(layout["admin_regions_csv_path"]).read_text()
r = api.call("egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_insert_admin_regions",
             project=project_code, highest_level=layout["admin_regions_highest_level"], csv_text=csv_text)
assert r["created"] > 0, f"Region import failed: {r}"
```

- [ ] **Step 6: Run AQE for all three layouts**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --until-step 2`
Expected: 3 layouts pass; regions exist in DB.


---

## Phase D — Step 9 User Creation

XD Step 10 wants bulk user creation with two flows: (a) upload CSV (mirrors `create-government-workers` CLI), (b) auto-generate one worker per region (mirrors `auto-generate-regional-workers` CLI). Both produce activation codes; both should support the `position.region@domain` email pattern.

### Task D.1: Extract OptimizedBulkWorkerCreator into shared service module

**Files:**
- Create: `egrm/services/government_worker_importer.py`
- Modify: `egrm/commands/create_government_workers.py`

- [ ] **Step 1: Locate the class**

Run: `grep -n "class OptimizedBulkWorkerCreator\|def create_from_csv\|def generate_for_regions\|def _bulk_validate\|def _bulk_insert_users_sql\|def _bulk_insert_assignments_sql" /Users/victor/egrm/apps/egrm/egrm/commands/create_government_workers.py`

- [ ] **Step 2: Move OptimizedBulkWorkerCreator into the service**

Create `egrm/services/government_worker_importer.py`. Move the entire class verbatim plus its helper functions (slug, email pattern, activation-code helpers).

- [ ] **Step 2a: Add text-mode methods to the class (REQUIRED — these do not exist on the current class)**

The existing `OptimizedBulkWorkerCreator` reads CSV from a file path; the wizard sends CSV as a string over RPC. Before adding the public façade, add three text-input wrappers as instance methods on the moved class. Each should `import io` at the top of the file (if not already) and reuse the existing file-based logic by routing through `io.StringIO`:

```python
class OptimizedBulkWorkerCreator:
    # ... existing code unchanged ...

    def validate_csv_text(self, csv_text: str) -> dict:
        """Validate CSV provided as a string. Returns the same shape as the file-based validator."""
        import io
        return self._validate_csv_stream(io.StringIO(csv_text))

    def create_from_csv_text(self, csv_text: str, default_password: str | None = None) -> dict:
        """Insert workers from a CSV string. Returns counts + activation codes."""
        import io
        return self._create_from_csv_stream(io.StringIO(csv_text), default_password=default_password)

    def export_activation_codes_csv(self) -> str:
        """Return CSV text of all uncrossed activation codes for the project (no file I/O)."""
        import io
        buf = io.StringIO()
        self._write_activation_codes_csv(buf)
        return buf.getvalue()
```

If the existing class exposes `_validate_csv_stream` / `_create_from_csv_stream` / `_write_activation_codes_csv` under different private names, rename the calls above accordingly. If the existing class only takes file paths and never opens a stream internally, refactor the existing `create_from_csv(path)` / `validate_csv(path)` / `export_activation_codes_csv(path)` methods so they `open(path)` and pass the resulting handle to a new `_*_stream(handle)` helper containing the body — then have the new text wrappers call the same `_*_stream` helper. Do NOT duplicate parsing/insertion logic.

Verify with: `grep -n "def validate_csv_text\|def create_from_csv_text\|def export_activation_codes_csv" egrm/services/government_worker_importer.py` — must return three matches before proceeding to Step 2b.

- [ ] **Step 2b: Add slim public API at the bottom of the service module**

```python
def parse_users_csv(project: str, csv_text: str) -> dict:
    """Validate-only preview of a worker CSV."""
    creator = OptimizedBulkWorkerCreator(project=project)
    return creator.validate_csv_text(csv_text)


def bulk_create_from_csv(project: str, csv_text: str, default_password: str | None = None) -> dict:
    """Insert workers from CSV. Returns counts + activation codes."""
    creator = OptimizedBulkWorkerCreator(project=project)
    return creator.create_from_csv_text(csv_text, default_password=default_password)


def auto_generate_per_region(project: str, level_type: str, position_template: str = "{level}_officer") -> dict:
    """Auto-generate one worker per region at the given level."""
    creator = OptimizedBulkWorkerCreator(project=project)
    return creator.generate_for_regions(level_filter=level_type, position_template=position_template)


def export_activation_codes(project: str) -> str:
    """Return CSV text of all uncrossed activation codes for the project."""
    creator = OptimizedBulkWorkerCreator(project=project)
    return creator.export_activation_codes_csv()
```

- [ ] **Step 3: Update CLI to delegate**

In `egrm/commands/create_government_workers.py`, replace the local class import with:

```python
from egrm.services.government_worker_importer import OptimizedBulkWorkerCreator  # noqa: F401
```

- [ ] **Step 4: Smoke the service directly (NOT the click command)**

`egrm.commands.create_government_workers.export_activation_codes` is `@click.command(...)`-decorated — `bench execute` cannot invoke it. Smoke the service function:

```bash
cd /Users/victor/egrm && \
  bench --site egrm.local execute egrm.services.government_worker_importer.export_activation_codes \
    --kwargs '{"project": "RW-WB"}'
```

Expected: CSV text. Then exercise the CLI façade from the shell:

```bash
bench --site egrm.local export-activation-codes RW-WB
```

Expected: same content as the service smoke.


### Task D.2: Add whitelisted RPC endpoints for user creation

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`
- Test: `egrm/tests/test_wizard_user_creation.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `egrm/tests/test_wizard_user_creation.py`:

```python
import frappe
import pytest

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
    parse_users_csv,
    bulk_create_users,
    auto_generate_regional_users,
    export_activation_codes,
)


@pytest.fixture
def project_with_regions():
    code = "TEST-USER-IMPORT"
    if not frappe.db.exists("GRM Project", code):
        frappe.get_doc({"doctype": "GRM Project", "project_code": code, "title": "Test"}).insert(ignore_permissions=True)
    # ... seed minimum: one level + one region (use existing helpers)
    yield code
    frappe.delete_doc("GRM Project", code, force=True)


def test_parse_users_csv_returns_validation(project_with_regions):
    csv_text = "first_name,last_name,position,region,phone\nAlice,Doe,Field Officer,Kacyiru,+250788000001\n"
    r = parse_users_csv(project=project_with_regions, csv_text=csv_text)
    assert r["total_rows"] == 1


def test_bulk_create_users_inserts_and_returns_codes(project_with_regions):
    csv_text = "first_name,last_name,position,region,phone\nAlice,Doe,Field Officer,Kacyiru,+250788000001\n"
    r = bulk_create_users(project=project_with_regions, csv_text=csv_text)
    assert r["created"] >= 1
    assert "activation_codes" in r
```

- [ ] **Step 2: Run test (expect FAIL)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_wizard_user_creation`
Expected: ImportError.

- [ ] **Step 3: Add endpoints**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`, append:

```python
from egrm.services.government_worker_importer import (
    parse_users_csv as _parse_users_csv,
    bulk_create_from_csv as _bulk_create_from_csv,
    auto_generate_per_region as _auto_generate_per_region,
    export_activation_codes as _export_codes,
)


@frappe.whitelist()
def parse_users_csv(project: str, csv_text: str) -> dict:
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _parse_users_csv(project=project, csv_text=csv_text)


@frappe.whitelist()
def bulk_create_users(project: str, csv_text: str, default_password: str | None = None) -> dict:
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _bulk_create_from_csv(project=project, csv_text=csv_text, default_password=default_password)


@frappe.whitelist()
def auto_generate_regional_users(project: str, level_type: str, position_template: str = "{level}_officer") -> dict:
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _auto_generate_per_region(project=project, level_type=level_type, position_template=position_template)


@frappe.whitelist()
def export_activation_codes(project: str) -> str:
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(f"Project {project} not found")
    return _export_codes(project=project)


@frappe.whitelist(allow_guest=False)
def export_user_template() -> str:
    """Return a CSV template for the bulk users upload tab.

    Bound to a whitelisted method (NOT the existing click command
    ``generate_worker_template`` — click commands cannot be served via
    ``/api/method/``). Returns the CSV body as a plain string; the
    Frappe HTTP layer serves it as ``application/json`` containing the
    string in ``message`` — the wizard JS pulls ``response.message``
    and writes it to a Blob for download.
    """
    _require_wizard_role()
    headers = "first_name,last_name,position,region,phone,email\n"
    sample = (
        "Alice,Mukamana,Field Officer,Kacyiru,+250788000001,\n"
        "Bob,Habimana,Field Officer,Remera,+250788000002,bob@example.org\n"
    )
    return headers + sample
```

> **JS-side adjustment for Step D.3:** the `<a href="/api/method/...export_user_template" download>` element receives JSON, not CSV. Replace the anchor with a button that calls `frappe.call({method: "...export_user_template"})`, then writes `r.message` to a Blob and triggers download — same pattern as `_export_codes()` in D.3.

- [ ] **Step 4: Run test (expect PASS)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_wizard_user_creation`
Expected: 2 passed.


### Task D.3: Build Step 9 Users UI

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` — replace `GRMWizardStep9Users` stub

- [ ] **Step 1: Replace the stub class**

In `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js`, replace the stub `GRMWizardStep9Users` with:

```javascript
class GRMWizardStep9Users {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }

    render() {
        this.$body.html(`
            <p class="text-muted">${__("Create government workers in bulk. Either upload a CSV or auto-generate one worker per administrative region.")}</p>
            <ul class="nav nav-tabs">
              <li class="nav-item"><a class="nav-link active" data-toggle="tab" href="#grm-u-csv">${__("Upload CSV")}</a></li>
              <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#grm-u-auto">${__("Auto-generate per Region")}</a></li>
              <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#grm-u-codes">${__("Activation Codes")}</a></li>
            </ul>
            <div class="tab-content pt-3">
              <div class="tab-pane fade show active" id="grm-u-csv"></div>
              <div class="tab-pane fade" id="grm-u-auto"></div>
              <div class="tab-pane fade" id="grm-u-codes"></div>
            </div>
        `);
        this._render_csv_tab();
        this._render_auto_tab();
        this._render_codes_tab();
    }

    _render_csv_tab() {
        this.$body.find("#grm-u-csv").html(`
            <p>${__("Required columns: first_name, last_name, position, region, phone. Optional: email.")}</p>
            <button class="btn btn-link btn-sm p-0" id="grm-u-template">${__("Download template")}</button>
            <div class="form-group mt-2">
              <input type="file" accept=".csv" id="grm-u-file" class="form-control-file">
            </div>
            <button class="btn btn-default btn-sm" id="grm-u-validate">${__("Validate")}</button>
            <button class="btn btn-primary btn-sm" id="grm-u-import" disabled>${__("Create Users")}</button>
            <div id="grm-u-result" class="mt-3"></div>
        `);
        this.$body.find("#grm-u-validate").on("click", () => this._validate());
        this.$body.find("#grm-u-import").on("click",   () => this._import());
        this.$body.find("#grm-u-template").on("click", () => this._download_template());
    }

    async _download_template() {
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.export_user_template",
        });
        const csv_text = r.message || "";
        const blob = new Blob([csv_text], { type: "text/csv" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "government-workers-template.csv";
        a.click();
    }

    _render_auto_tab() {
        this.$body.find("#grm-u-auto").html(`
            <p>${__("Pick the level at which to create one worker per region. The CLI position template defaults to '{level}_officer'.")}</p>
            <div class="form-group">
              <label>${__("Administrative Level Type")}</label>
              <input type="text" class="form-control" id="grm-u-level" placeholder="Sector">
            </div>
            <div class="form-group">
              <label>${__("Position template")}</label>
              <input type="text" class="form-control" id="grm-u-tmpl" value="{level}_officer">
            </div>
            <button class="btn btn-primary btn-sm" id="grm-u-gen">${__("Auto-generate")}</button>
            <div id="grm-u-gen-result" class="mt-3"></div>
        `);
        this.$body.find("#grm-u-gen").on("click", () => this._auto_generate());
    }

    _render_codes_tab() {
        this.$body.find("#grm-u-codes").html(`
            <p>${__("Download a CSV of all activation codes for this project. Codes expire 48 hours after creation.")}</p>
            <button class="btn btn-default btn-sm" id="grm-u-export">${__("Export CSV")}</button>
        `);
        this.$body.find("#grm-u-export").on("click", () => this._export_codes());
    }

    async _read_file() {
        const f = this.$body.find("#grm-u-file")[0].files[0];
        if (!f) { frappe.show_alert({ message: __("Pick a CSV first."), indicator: "orange" }); return null; }
        return await f.text();
    }

    async _validate() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.parse_users_csv",
            args: { project: this.project.name, csv_text },
        });
        const m = r.message || {};
        const $r = this.$body.find("#grm-u-result").empty();
        if (m.errors && m.errors.length) {
            $r.append(`<div class="alert alert-danger"><ul>${m.errors.map(e => `<li>${frappe.utils.escape_html(e)}</li>`).join("")}</ul></div>`);
            return;
        }
        $r.append(`<div class="alert alert-info">${__("Detected {0} valid rows.", [m.total_rows])}</div>`);
        this.$body.find("#grm-u-import").prop("disabled", false);
    }

    async _import() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_create_users",
            args: { project: this.project.name, csv_text },
        });
        const m = r.message || {};
        this.$body.find("#grm-u-result").empty().append(
            `<div class="alert alert-success">${__("Created {0} users. Failures: {1}.", [m.created, (m.errors || []).length])}</div>`
        );
    }

    async _auto_generate() {
        const level = this.$body.find("#grm-u-level").val().trim();
        const tmpl  = this.$body.find("#grm-u-tmpl").val().trim() || "{level}_officer";
        if (!level) { frappe.show_alert({ message: __("Pick a level."), indicator: "orange" }); return; }
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.auto_generate_regional_users",
            args: { project: this.project.name, level_type: level, position_template: tmpl },
        });
        const m = r.message || {};
        this.$body.find("#grm-u-gen-result").empty().append(
            `<div class="alert alert-success">${__("Generated {0} users.", [m.created])}</div>`
        );
    }

    async _export_codes() {
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.export_activation_codes",
            args: { project: this.project.name },
        });
        const csv_text = r.message || "";
        const blob = new Blob([csv_text], { type: "text/csv" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${this.project.name}-activation-codes.csv`;
        a.click();
    }

    async save() {
        // User creation is optional per step. Continue freely.
        return true;
    }
}
```

- [ ] **Step 2: Add user CSV fixture**

Create `docs/superpowers/plans/aqe-generated/fixtures/users/RW-WB.csv`:

```csv
first_name,last_name,position,region,phone
Alice,Mukamana,Field Officer,Kacyiru,+250788000001
Bob,Habimana,Field Officer,Remera,+250788000002
Charles,Iradukunda,Department Head,Gasabo,+250788000003
```

- [ ] **Step 3: Extend AQE driver**

In `run_onboarding_tests.py`, after Step 8 driver, add:

```python
# Step 9 — Users (CSV upload)
csv_text = pathlib.Path(layout["users_csv_path"]).read_text()
r = api.call("egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_create_users",
             project=project_code, csv_text=csv_text)
assert r["created"] >= 1, f"User creation failed: {r}"
```

And add `"users_csv_path": "fixtures/users/RW-WB.csv"` to each LAYOUT.

- [ ] **Step 4: Run AQE up to Step 9**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --layout RW-WB --until-step 9`
Expected: 3+ users created, no errors.


---

## Phase E — Step 10 Issue Routing Finalization

XD Step 11 wants a dedicated screen showing all issue categories with a per-category "route to" picker (role OR department). Currently, `Step3IssueCategories` (formerly `Step5`) embeds `assigned_department` inline; we keep that, but add Step 10 as the *finalization* screen where admins can review and re-assign at the end (after all roles + departments + users exist).

### Task E.1: Add `routing_target_type` field to GRM Issue Category

**Files:**
- Modify: `egrm/egrm/doctype/grm_issue_category/grm_issue_category.json`

- [ ] **Step 1: Add field**

In `grm_issue_category.json`, add to `field_order` (after `assigned_department`):

```json
"routing_target_type",
"assigned_role",
```

Append to `fields`:

```json
{ "fieldname": "routing_target_type", "fieldtype": "Select", "label": "Route To", "options": "Department\nRole", "default": "Department" },
{ "fieldname": "assigned_role", "fieldtype": "Link", "label": "Assigned Role", "options": "GRM Project Role", "depends_on": "eval:doc.routing_target_type == 'Role'" }
```


### Task E.2: Add whitelisted endpoint to update routing per category

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py`

- [ ] **Step 1: Append endpoint**

```python
@frappe.whitelist()
def update_category_routing(project: str, category: str, target_type: str, target: str) -> dict:
    """Set routing target on an issue category. target_type: 'Department' | 'Role'."""
    _require_wizard_role()
    if target_type not in ("Department", "Role"):
        frappe.throw("target_type must be Department or Role")
    cat = frappe.get_doc("GRM Issue Category", category)
    if cat.project != project:
        frappe.throw("Category does not belong to this project")
    cat.routing_target_type = target_type
    if target_type == "Department":
        cat.assigned_department = target
        cat.assigned_role = None
    else:
        cat.assigned_role = target
        cat.assigned_department = None
    cat.save(ignore_permissions=True)
    return {"category": category, "routing_target_type": target_type, "target": target}
```

- [ ] **Step 2: Smoke**

Run: `cd /Users/victor/egrm && bench --site egrm.local execute "egrm.egrm.page.grm_project_wizard.grm_project_wizard.update_category_routing" --kwargs '{"project": "RW-WB", "category": "RW-WB-Water Access", "target_type": "Department", "target": "RW-WB-Water Dept"}'`
Expected: returns dict with updated routing.


### Task E.3: Build Step 10 Routing UI

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` — replace `GRMWizardStep10Routing` stub

- [ ] **Step 1: Replace stub**

```javascript
class GRMWizardStep10Routing {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.categories = [];
        this.departments = [];
        this.roles = [];
        this.render();
    }

    async render() {
        this.$body.html(`<p class="text-muted">${__("Loading…")}</p>`);
        await this._load();
        this._render_table();
    }

    async _load() {
        const [cats, depts, roles] = await Promise.all([
            frappe.db.get_list("GRM Issue Category", {
                filters: { project: this.project.name },
                fields: ["name", "category_name", "routing_target_type", "assigned_department", "assigned_role"],
                limit: 0,
            }),
            frappe.db.get_list("GRM Issue Department", {
                filters: { project: this.project.name },
                fields: ["name", "department_name"],
                limit: 0,
            }),
            frappe.db.get_list("GRM Project Role", {
                filters: { project: this.project.name, is_active: 1 },
                fields: ["name", "role_name"],
                limit: 0,
            }),
        ]);
        this.categories = cats;
        this.departments = depts;
        this.roles = roles;
    }

    _render_table() {
        const dept_opts = this.departments.map(d => `<option value="${d.name}">${frappe.utils.escape_html(d.department_name)}</option>`).join("");
        const role_opts = this.roles.map(r => `<option value="${r.name}">${frappe.utils.escape_html(r.role_name)}</option>`).join("");
        const rows = this.categories.map(c => {
            const tt = c.routing_target_type || "Department";
            return `
              <tr data-cat="${c.name}">
                <td>${frappe.utils.escape_html(c.category_name)}</td>
                <td>
                  <select class="form-control form-control-sm grm-r-type">
                    <option value="Department" ${tt === "Department" ? "selected" : ""}>${__("Department")}</option>
                    <option value="Role"       ${tt === "Role"       ? "selected" : ""}>${__("Role")}</option>
                  </select>
                </td>
                <td>
                  <select class="form-control form-control-sm grm-r-target-dept" ${tt === "Role" ? "style='display:none'" : ""}>
                    ${dept_opts.replace(`value="${c.assigned_department}"`, `value="${c.assigned_department}" selected`)}
                  </select>
                  <select class="form-control form-control-sm grm-r-target-role" ${tt === "Department" ? "style='display:none'" : ""}>
                    ${role_opts.replace(`value="${c.assigned_role}"`, `value="${c.assigned_role}" selected`)}
                  </select>
                </td>
              </tr>`;
        }).join("");
        this.$body.html(`
            <p class="text-muted">${__("Finalise where each category's complaints are routed. Choose a Department for organisational routing, or a Role for cross-department workflows.")}</p>
            <table class="table table-bordered">
              <thead><tr><th>${__("Category")}</th><th>${__("Route To")}</th><th>${__("Target")}</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
        `);
        this.$body.on("change", ".grm-r-type", (e) => {
            const $tr = $(e.target).closest("tr");
            const t = $(e.target).val();
            $tr.find(".grm-r-target-dept").toggle(t === "Department");
            $tr.find(".grm-r-target-role").toggle(t === "Role");
        });
    }

    async save() {
        const tasks = [];
        this.$body.find("tbody tr").each((_, tr) => {
            const $tr = $(tr);
            const cat = $tr.data("cat");
            const t = $tr.find(".grm-r-type").val();
            const target = t === "Department"
                ? $tr.find(".grm-r-target-dept").val()
                : $tr.find(".grm-r-target-role").val();
            if (!target) return;
            tasks.push(frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.update_category_routing",
                args: { project: this.project.name, category: cat, target_type: t, target },
            }));
        });
        try { await Promise.all(tasks); return true; }
        catch (e) { return false; }
    }
}
```

- [ ] **Step 2: Run AQE through Step 10**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --layout RW-WB --until-step 10`
Expected: routing rows persisted on each category.

### Task E.4: Inline routing controls in Step 3 IssueCategories form

The legacy IssueCategories step (`grm_project_wizard.js:1468-1719`) lets admins set `assigned_department` / `assigned_appeal_department` / `assigned_escalation_department` inline as they create each category. We MUST also surface `routing_target_type` + `assigned_role` here so the inline form stays the source of truth — the Step 10 finalization screen is a *review*, not the only entry point.

**Files:**
- Modify: `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js:1468-1719` (the IssueCategories step class — note this gets renamed `GRMWizardStep3IssueCategories` in Phase B Task B.1 Step 3)

- [ ] **Step 1: Extend the form-row render to include routing toggle**

In the IssueCategories step's category-form render (around line 1595), wrap the three department selects in a section preceded by a `Route To` toggle:

```javascript
// Replace the existing PRIMARY <select> for assigned_department with a routing block.
// The appeal + escalation department selects stay department-only — out of scope
// for the routing-target-type feature.

const routing_block = `
  <div class="form-group">
    <label class="control-label">${__("Route To")}</label>
    <select class="form-control" id="grm-cf-routing_target_type">
      <option value="Department" ${ (r.routing_target_type || "Department") === "Department" ? "selected" : "" }>${__("Department")}</option>
      <option value="Role"       ${ r.routing_target_type === "Role" ? "selected" : "" }>${__("Role")}</option>
    </select>
  </div>
  <div class="form-group" id="grm-cf-target-dept-wrap" ${ r.routing_target_type === "Role" ? `style="display:none"` : "" }>
    <label class="control-label">${__("Assigned Department")}</label>
    <select class="form-control" id="grm-cf-assigned_department">
      <option value="">— ${__("None")} —</option>
      ${this.department_options(r.assigned_department, false)}
    </select>
  </div>
  <div class="form-group" id="grm-cf-target-role-wrap" ${ r.routing_target_type !== "Role" ? `style="display:none"` : "" }>
    <label class="control-label">${__("Assigned Role")}</label>
    <select class="form-control" id="grm-cf-assigned_role">
      <option value="">— ${__("None")} —</option>
      ${this.role_options ? this.role_options(r.assigned_role) : ""}
    </select>
  </div>
`;
```

- [ ] **Step 2: Add `role_options` + `role_label` helpers and load roles alongside departments**

Mirror the existing `department_options`. In the class body:

```javascript
role_options(selected) {
    const roles = this.project_roles || [];
    return roles.map(x =>
        `<option value="${x.name}" ${selected === x.name ? "selected" : ""}>${frappe.utils.escape_html(x.role_name)}</option>`
    ).join("");
}

role_label(name) {
    const r = (this.project_roles || []).find(x => x.name === name);
    return r ? r.role_name : (name || "");
}
```

In `render()` setup, fetch in parallel:

```javascript
const [depts, roles] = await Promise.all([
    frappe.db.get_list("GRM Issue Department", {
        filters: { project: this.project.name },
        fields: ["name", "department_name"], limit: 0,
    }),
    frappe.db.get_list("GRM Project Role", {
        filters: { project: this.project.name, is_active: 1 },
        fields: ["name", "role_name"], limit: 0,
    }),
]);
this.departments = depts;
this.project_roles = roles;
```

- [ ] **Step 3: Update `read_form()` (around line 1658)**

```javascript
return {
    // ...existing fields...
    routing_target_type: trim("grm-cf-routing_target_type") || "Department",
    assigned_department: trim("grm-cf-assigned_department") || null,
    assigned_role: trim("grm-cf-assigned_role") || null,
    assigned_appeal_department: trim("grm-cf-assigned_appeal_department") || null,
    assigned_escalation_department: trim("grm-cf-assigned_escalation_department") || null,
};
```

- [ ] **Step 4: Update `validate()` (around line 1681)**

```javascript
if (v.routing_target_type === "Role") {
    if (!v.assigned_role) errors.push(__("Assigned Role is required when Route To = Role."));
} else {
    if (!v.assigned_department) errors.push(__("Assigned Department is required."));
}
```

- [ ] **Step 5: Update `save()` (around lines 1699 and 1713)**

```javascript
doc.routing_target_type = v.routing_target_type;
doc.assigned_department = v.assigned_department;
doc.assigned_role = v.assigned_role;
doc.assigned_appeal_department = v.assigned_appeal_department;
doc.assigned_escalation_department = v.assigned_escalation_department;
// ...
const payload = {
    project: this.project.name,
    label: v.label,
    routing_target_type: v.routing_target_type,
};
if (v.assigned_department) payload.assigned_department = v.assigned_department;
if (v.assigned_role) payload.assigned_role = v.assigned_role;
if (v.assigned_appeal_department) payload.assigned_appeal_department = v.assigned_appeal_department;
if (v.assigned_escalation_department) payload.assigned_escalation_department = v.assigned_escalation_department;
```

- [ ] **Step 6: Update the read-only category list render (around line 1511)**

```javascript
// Replace:  <td>${frappe.utils.escape_html(dept_label(r.assigned_department))}</td>
const target_label = r.routing_target_type === "Role"
    ? this.role_label(r.assigned_role)
    : dept_label(r.assigned_department);
const target_kind = r.routing_target_type === "Role" ? __("Role") : __("Dept");
// Row HTML:
<td><span class="badge badge-secondary">${target_kind}</span> ${frappe.utils.escape_html(target_label)}</td>
```

- [ ] **Step 7: Wire toggle behaviour**

```javascript
this.$body.on("change", "#grm-cf-routing_target_type", (e) => {
    const t = $(e.target).val();
    this.$body.find("#grm-cf-target-dept-wrap").toggle(t === "Department");
    this.$body.find("#grm-cf-target-role-wrap").toggle(t === "Role");
});
```

### Task E.5: Add `resolve_category_routing` helper as single source of truth

Today every consumer that needs "where does this category route to?" reads `assigned_department` directly. After this change, consumers must respect `routing_target_type`. Rather than duplicate the `if/else` everywhere, add ONE helper and refactor all callsites to use it.

**Files:**
- Create: `egrm/services/category_routing.py`
- Test: `egrm/tests/test_category_routing.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `egrm/tests/test_category_routing.py`:

```python
import frappe
import pytest

from egrm.services.category_routing import resolve_category_routing


@pytest.fixture
def routed_category():
    proj = "TEST-ROUTING"
    if not frappe.db.exists("GRM Project", proj):
        frappe.get_doc({"doctype": "GRM Project", "project_code": proj, "title": "T"}).insert(ignore_permissions=True)
    dept = frappe.get_doc({"doctype": "GRM Issue Department", "project": proj, "department_name": "DeptA"}).insert(ignore_permissions=True)
    role = frappe.get_doc({"doctype": "GRM Project Role", "project": proj, "role_name": "RoleA", "is_active": 1}).insert(ignore_permissions=True)
    cat_dept = frappe.get_doc({
        "doctype": "GRM Issue Category", "project": proj, "category_name": "C-Dept",
        "routing_target_type": "Department", "assigned_department": dept.name,
    }).insert(ignore_permissions=True)
    cat_role = frappe.get_doc({
        "doctype": "GRM Issue Category", "project": proj, "category_name": "C-Role",
        "routing_target_type": "Role", "assigned_role": role.name,
    }).insert(ignore_permissions=True)
    yield {"dept_cat": cat_dept.name, "role_cat": cat_role.name, "dept": dept.name, "role": role.name}


def test_resolve_returns_department(routed_category):
    r = resolve_category_routing(routed_category["dept_cat"])
    assert r["target_type"] == "Department"
    assert r["target_name"] == routed_category["dept"]


def test_resolve_returns_role(routed_category):
    r = resolve_category_routing(routed_category["role_cat"])
    assert r["target_type"] == "Role"
    assert r["target_name"] == routed_category["role"]


def test_resolve_legacy_category_falls_back_to_department(routed_category):
    # Pre-migration row: routing_target_type NULL
    frappe.db.set_value("GRM Issue Category", routed_category["dept_cat"], "routing_target_type", None)
    r = resolve_category_routing(routed_category["dept_cat"])
    assert r["target_type"] == "Department"
    assert r["target_name"] == routed_category["dept"]
```

- [ ] **Step 2: Run test (expect FAIL — module not found)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_category_routing`
Expected: ImportError on `egrm.services.category_routing`.

- [ ] **Step 3: Implement helper**

Create `egrm/services/category_routing.py`:

```python
"""Single source of truth for resolving a GRM Issue Category's routing target.

Consumers MUST call ``resolve_category_routing(category_name)`` instead of
reading ``assigned_department`` directly. Keeps the dept-vs-role logic in
one place and lets us evolve routing (e.g. add a 'User' target type) without
hunting through the codebase.
"""
import frappe


def resolve_category_routing(category_name: str) -> dict:
    """Resolve where issues of this category should be routed.

    Returns:
        ``{"target_type": "Department" | "Role", "target_name": str | None,
            "target_doc": <Frappe Document> | None}``

    Backwards-compatibility:
        Categories whose ``routing_target_type`` is NULL (pre-migration) are
        treated as ``"Department"`` and routed to ``assigned_department``.
    """
    cat = frappe.db.get_value(
        "GRM Issue Category",
        category_name,
        ["routing_target_type", "assigned_department", "assigned_role"],
        as_dict=True,
    )
    if not cat:
        return {"target_type": "Department", "target_name": None, "target_doc": None}

    target_type = cat.routing_target_type or "Department"
    if target_type == "Role":
        target_name = cat.assigned_role
        target_doc = frappe.get_doc("GRM Project Role", target_name) if target_name else None
    else:
        target_name = cat.assigned_department
        target_doc = frappe.get_doc("GRM Issue Department", target_name) if target_name else None

    return {"target_type": target_type, "target_name": target_name, "target_doc": target_doc}


def resolve_routing_for_issue_creation(category_name: str) -> dict:
    """Wizard-friendly variant returning the values to write onto a new GRM Issue.

    For Department routing: ``{"assigned_department": <name>, "assigned_role": None}``.
    For Role routing:       ``{"assigned_department": None, "assigned_role": <name>}``.
    """
    r = resolve_category_routing(category_name)
    if r["target_type"] == "Role":
        return {"assigned_department": None, "assigned_role": r["target_name"]}
    return {"assigned_department": r["target_name"], "assigned_role": None}
```

- [ ] **Step 4: Run test (expect PASS)**

Run: `cd /Users/victor/egrm && bench --site egrm.local run-tests --module egrm.tests.test_category_routing`
Expected: 3 passed.

### Task E.6: Propagate routing target to all backend consumers

Refactor every callsite that previously read `assigned_department` to use the helper. Below is the file-by-file plan derived from `grep -rn "assigned_department"`.

**Inventory (from grep — verified 2026-05-09):**

| File | Line(s) | What it actually reads/does | Action |
|---|---|---|---|
| `egrm/egrm/doctype/grm_issue/grm_issue.json` | (entire) | **GRM Issue has no `assigned_department` or `assigned_role` field today** — both are net-new | E.6.a (add both fields) |
| `egrm/egrm/doctype/grm_issue/grm_issue.py` | 232-239 (`before_insert`) | currently only generates codes — no auto-routing exists | E.6.a (add auto-routing here) |
| `egrm/egrm/doctype/grm_issue/grm_issue.py` | 580 (inside `has_permission_to_view_sensitive_data`) | reads `assigned_department` of the **category** to gate Department-Head sensitive-data view | E.6.a-bis (read-side perm check; separate task) |
| `egrm/egrm/doctype/grm_issue/grm_issue.py` | 497 | `assigned_escalation_department` (escalation flow) | **out of scope** — escalation stays dept-only |
| `egrm/api/lookup.py` | 56-81 | exposes `assigned_department` to mobile clients | E.6.b |
| `egrm/server_scripts/queries.py` | 318-324 | auto-routing query | E.6.c |
| `egrm/number_card/number_card.py` | 103 | dashboard count SQL `WHERE assigned_department IN (...)` | E.6.d |
| `egrm/server_scripts/scheduled_tasks.py` | 99 | escalation cron uses `assigned_escalation_department` | **out of scope** |
| `egrm/server_scripts/issue_actions.py` | 98,102 | escalation handler | **out of scope** |
| `egrm/egrm/doctype/grm_issue_department/grm_issue_department.js` | 13 | form list filter | E.6.e (annotation only) |
| `egrm/egrm/doctype/grm_issue_category/grm_issue_category.py` | 56-115 | project-scope validation | E.6.g (add role validation) |
| `egrm/egrm/doctype/grm_issue_category/grm_issue_category.js` | 45-73 | typeahead `set_query` | E.6.h (add role set_query) |
| `egrm/egrm/doctype/grm_project_role/...` | NEW | mirror of dept "Issues" button | E.6.f |
| `egrm/egrm/doctype/grm_issue_category/grm_issue_category.json` | 15-63 | declares dept fields | covered in Phase E Task E.1 (already adds `assigned_role`, `routing_target_type`) |
| `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py` | 26,525,534 | seed payload | E.7 |

**Out of scope for this milestone:** appeal/escalation routing stays department-only. If users want role-based escalation, plan a follow-up that adds `appeal_routing_target_type` + `assigned_appeal_role` and `escalation_routing_target_type` + `assigned_escalation_role` symmetrically — same pattern as primary routing.

#### E.6.a — Add `assigned_department` + `assigned_role` to GRM Issue and auto-route on create

> **Important reality check:** GRM Issue today has **neither** `assigned_department` nor `assigned_role`. The issue's per-row routing target is implicit — every consumer reads it from the **category** instead. The plan introduces both fields to GRM Issue so role-routed cases can be filtered/aggregated by role without re-resolving the category each time. The auto-population happens in `before_insert` (which currently only generates codes — no routing logic exists today).

- [ ] **Step 1: Read context**

```bash
grep -n "fieldname.*assigned_\|assigned_department\|assigned_role" /Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_issue/grm_issue.json
grep -n "before_insert\|self.assigned" /Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_issue/grm_issue.py
```

Confirm: `grm_issue.json` has neither field; `grm_issue.py:232 before_insert` only calls `self.generate_codes()`.

- [ ] **Step 2: Add both `assigned_department` and `assigned_role` to GRM Issue doctype**

In `egrm/egrm/doctype/grm_issue/grm_issue.json`, append to `fields`:

```json
{ "fieldname": "assigned_department", "fieldtype": "Link", "label": "Assigned Department", "options": "GRM Issue Department" },
{ "fieldname": "assigned_role",       "fieldtype": "Link", "label": "Assigned Role",       "options": "GRM Project Role" }
```

Add both to `field_order` (location: alongside other assignment fields — e.g. immediately after `category`).

- [ ] **Step 3: Add the auto-routing call to `before_insert`**

In `egrm/egrm/doctype/grm_issue/grm_issue.py`, replace the existing `before_insert`:

```python
def before_insert(self):
    try:
        self.generate_codes()
        frappe.log(f"Generated codes for GRM Issue {self.name}")
    except Exception as e:
        frappe.log(f"Error generating codes for GRM Issue: {str(e)}")
        raise
```

with:

```python
def before_insert(self):
    try:
        self.generate_codes()
        self._apply_default_routing_from_category()
        frappe.log(f"Generated codes + applied default routing for GRM Issue {self.name}")
    except Exception as e:
        frappe.log(f"Error in before_insert for GRM Issue: {str(e)}")
        raise

def _apply_default_routing_from_category(self) -> None:
    """Populate ``assigned_department`` / ``assigned_role`` from the category
    when neither was explicitly set on the incoming payload."""
    if self.assigned_department or self.assigned_role:
        return  # respect caller-provided routing
    if not self.category:
        return
    from egrm.services.category_routing import resolve_routing_for_issue_creation
    routing = resolve_routing_for_issue_creation(self.category)
    if routing["assigned_department"]:
        self.assigned_department = routing["assigned_department"]
    if routing["assigned_role"]:
        self.assigned_role = routing["assigned_role"]
```

> Why a separate helper: keeps `before_insert` short and the routing logic unit-testable in isolation. Caller-provided values take precedence (respects manual overrides from mobile API or admin desk).

- [ ] **Step 4: Add tests for the auto-routing path**

In `egrm/tests/test_category_routing.py`, append:

```python
def test_new_issue_inherits_role_routing(routed_category):
    project = frappe.db.get_value("GRM Issue Category", routed_category["role_cat"], "project")
    issue = frappe.get_doc({
        "doctype": "GRM Issue", "project": project, "category": routed_category["role_cat"],
        "title": "T", "description": "D",
    }).insert(ignore_permissions=True)
    assert issue.assigned_role == routed_category["role"]
    assert not issue.assigned_department


def test_new_issue_inherits_department_routing(routed_category):
    project = frappe.db.get_value("GRM Issue Category", routed_category["dept_cat"], "project")
    issue = frappe.get_doc({
        "doctype": "GRM Issue", "project": project, "category": routed_category["dept_cat"],
        "title": "T", "description": "D",
    }).insert(ignore_permissions=True)
    assert issue.assigned_department == routed_category["dept"]
    assert not issue.assigned_role


def test_caller_overrides_default_routing(routed_category):
    """Caller-supplied assigned_department wins over the category default."""
    project = frappe.db.get_value("GRM Issue Category", routed_category["role_cat"], "project")
    other_dept = frappe.get_doc({
        "doctype": "GRM Issue Department", "project": project, "department_name": "Override",
    }).insert(ignore_permissions=True)
    issue = frappe.get_doc({
        "doctype": "GRM Issue", "project": project, "category": routed_category["role_cat"],
        "title": "T", "description": "D",
        "assigned_department": other_dept.name,
    }).insert(ignore_permissions=True)
    assert issue.assigned_department == other_dept.name
    assert not issue.assigned_role  # role auto-assignment skipped because dept was provided
```

Run: `bench --site egrm.local run-tests --module egrm.tests.test_category_routing`
Expected: 6 passed.

#### E.6.a-bis — Update sensitive-data permission check for role routing

The existing `has_permission_to_view_sensitive_data` (line 556) reads `assigned_department` of the category at line 580 and grants view to that department's Head. Role-routed categories have no `assigned_department`, so the current check silently denies access to anyone — including the assigned role's holders. Extend the check.

- [ ] **Step 1: Replace the dept-only block with a routing-aware block**

Around `grm_issue.py:578-592`, replace:

```python
# Department Head for this category can view
category_dept = frappe.db.get_value(
    "GRM Issue Category", self.category, "assigned_department"
)
if category_dept and frappe.db.exists(
    "GRM User Project Assignment",
    {
        "user": frappe.session.user,
        "project": self.project,
        "role": "GRM Department Head",
        "department": category_dept,
        "is_active": 1,
    },
):
    return True
```

with:

```python
# Department Head OR Role assignee for this category can view sensitive data.
from egrm.services.category_routing import resolve_category_routing
routing = resolve_category_routing(self.category)
if routing["target_type"] == "Department" and routing["target_name"]:
    if frappe.db.exists("GRM User Project Assignment", {
        "user": frappe.session.user, "project": self.project,
        "role": "GRM Department Head",
        "department": routing["target_name"], "is_active": 1,
    }):
        return True
elif routing["target_type"] == "Role" and routing["target_name"]:
    if frappe.db.exists("GRM User Project Assignment", {
        "user": frappe.session.user, "project": self.project,
        "project_role": routing["target_name"], "is_active": 1,
    }):
        return True
```

- [ ] **Step 2: Verify the GRM User Project Assignment doctype has a `project_role` link field**

```bash
grep -n "project_role\|fieldname" /Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json | head -20
```

If the field doesn't exist, this perm-check change becomes a follow-up: open a tracking issue and gate it behind a `routing["target_type"] == "Role"` early-return that **denies** access (current behavior) until the assignment doctype is extended. Note this in the plan's Self-Review.

- [ ] **Step 3: Test**

Add to `egrm/tests/test_category_routing.py`:

```python
def test_role_assignee_can_view_sensitive_data_on_role_routed_issue(routed_category):
    """A user with the role bound to a role-routed category sees sensitive data."""
    # Skipped if GRM User Project Assignment lacks `project_role` — see E.6.a-bis Step 2.
    if not frappe.get_meta("GRM User Project Assignment").has_field("project_role"):
        pytest.skip("GRM User Project Assignment.project_role not yet defined")
    # ... fixture user + assignment + issue, then call has_permission_to_view_sensitive_data
```

#### E.6.b — `egrm/api/lookup.py` (mobile API)

- [ ] **Step 1: Read context**

Read `egrm/api/lookup.py:50-95`.

- [ ] **Step 2: Add `assigned_role` + `routing_target_type` to fetched fields, enrich response**

Around line 56 (the GRM Issue Category field list), add `"assigned_role"` and `"routing_target_type"`. Around line 64-81 (enrichment block), replace with:

```python
from egrm.services.category_routing import resolve_category_routing

for category in categories:
    routing = resolve_category_routing(category["name"])
    category["routing_target_type"] = routing["target_type"]
    category["routing_target"] = routing["target_name"]
    if routing["target_type"] == "Department" and routing["target_doc"]:
        category["department"] = routing["target_name"]
        category["department_name"] = routing["target_doc"].department_name
        category["role"] = None
        category["role_name"] = None
    elif routing["target_type"] == "Role" and routing["target_doc"]:
        category["role"] = routing["target_name"]
        category["role_name"] = routing["target_doc"].role_name
        category["department"] = None
        category["department_name"] = None
    else:
        category["department"] = category.get("assigned_department")
        category["role"] = None
```

- [ ] **Step 3: Test the mobile API surface**

Create `egrm/tests/test_lookup_routing.py`:

```python
import frappe
from egrm.api.lookup import get_categories  # adjust import to whatever endpoint exposes routing


def test_lookup_returns_role_routing(routed_category):
    project = frappe.db.get_value("GRM Issue Category", routed_category["role_cat"], "project")
    cats = get_categories(project=project)
    role_cat = next(c for c in cats if c["name"] == routed_category["role_cat"])
    assert role_cat["routing_target_type"] == "Role"
    assert role_cat["role"] == routed_category["role"]
    assert role_cat["department"] is None


def test_lookup_returns_department_routing(routed_category):
    project = frappe.db.get_value("GRM Issue Category", routed_category["dept_cat"], "project")
    cats = get_categories(project=project)
    dept_cat = next(c for c in cats if c["name"] == routed_category["dept_cat"])
    assert dept_cat["routing_target_type"] == "Department"
    assert dept_cat["department"] == routed_category["dept"]
    assert dept_cat["role"] is None
```

Run: `bench --site egrm.local run-tests --module egrm.tests.test_lookup_routing`
Expected: 2 passed.

#### E.6.c — `egrm/server_scripts/queries.py:318-324` (auto-routing query)

- [ ] **Step 1: Read context**

Read `egrm/server_scripts/queries.py:300-340`.

- [ ] **Step 2: Replace direct field read**

Around lines 318-324, replace:

```python
category_info = frappe.db.get_value(
    "GRM Issue Category", category, ["assigned_department", "redirection_protocol"], as_dict=True,
)
return {
    "department": category_info.assigned_department,
    "redirection_protocol": category_info.redirection_protocol,
}
```

with:

```python
from egrm.services.category_routing import resolve_category_routing

routing = resolve_category_routing(category)
redirection_protocol = frappe.db.get_value("GRM Issue Category", category, "redirection_protocol")
return {
    "target_type": routing["target_type"],
    "department": routing["target_name"] if routing["target_type"] == "Department" else None,
    "role": routing["target_name"] if routing["target_type"] == "Role" else None,
    "redirection_protocol": redirection_protocol,
}
```

- [ ] **Step 3: Audit callers**

Run: `grep -rn "redirection_protocol" /Users/victor/egrm/apps/egrm --include="*.py" --include="*.js"`
For each caller that destructures `["department"]`, ensure they handle `None` (when the category is role-routed) and respect `target_type`.

#### E.6.d — `egrm/number_card/number_card.py:103` (dashboard SQL)

- [ ] **Step 1: Read context**

Read `egrm/number_card/number_card.py:80-130`.

- [ ] **Step 2: Update SQL — exclude role-routed categories explicitly**

Replace the WHERE clause around line 103:

```python
sql = f"""
    SELECT COUNT(*) FROM `tabGRM Issue` issue
    JOIN `tabGRM Issue Category` cat ON cat.name = issue.category
    WHERE issue.assigned_department IN ('{department_list}')
      AND (cat.routing_target_type IS NULL OR cat.routing_target_type = 'Department')
"""
```

Rationale: a department dashboard card should not double-count Role-routed categories that may have a stale `assigned_department` from a legacy migration.

#### E.6.e — `grm_issue_department.js:13` (form list filter)

- [ ] **Step 1: Annotate the existing filter**

Read `egrm/egrm/doctype/grm_issue_department/grm_issue_department.js:1-30`. The filter `{ assigned_department: frm.doc.name }` is correct as-is — role-routed issues by definition have no `assigned_department`. Add a comment so reviewers don't change it later:

```javascript
// Lists issues whose snapshot assigned_department matches this department.
// Role-routed issues (routing_target_type = 'Role') intentionally excluded —
// see egrm/services/category_routing.py for the routing model.
filters: { assigned_department: frm.doc.name }
```

#### E.6.f — Add equivalent "Issues" filter to GRM Project Role form

- [ ] **Step 1: Locate or create role form JS**

Run: `find /Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_project_role -type f`

If `grm_project_role.js` exists, add a button mirroring the department one. If not, create:

```javascript
frappe.ui.form.on("GRM Project Role", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Issues"), () => {
            frappe.set_route("List", "GRM Issue", { assigned_role: frm.doc.name });
        });
    },
});
```

#### E.6.g — `grm_issue_category.py:50-115` (Python validation)

- [ ] **Step 1: Read the validation block**

Read `egrm/egrm/doctype/grm_issue_category/grm_issue_category.py:45-120`.

- [ ] **Step 2: Add validation for `assigned_role`**

Insert after the existing `assigned_department` validation (around line 75):

```python
if self.routing_target_type == "Role":
    if not self.assigned_role:
        frappe.throw(_("Assigned Role is required when Route To = Role"))
    role_project = frappe.db.get_value("GRM Project Role", self.assigned_role, "project")
    if role_project != project:
        frappe.throw(
            _("Assigned Role {0} does not belong to project {1}").format(
                self.assigned_role, project
            )
        )
elif self.routing_target_type == "Department":
    if not self.assigned_department:
        frappe.throw(_("Assigned Department is required when Route To = Department"))
```

(The existing project-scope check for `assigned_department` already runs above. The new block adds the role-side equivalent and the require-when-Role gate.)

#### E.6.h — `grm_issue_category.js:45-73` (typeahead `set_query`)

- [ ] **Step 1: Add `set_query` for `assigned_role`**

In `egrm/egrm/doctype/grm_issue_category/grm_issue_category.js`, alongside the existing three `set_query` calls:

```javascript
frm.set_query('assigned_role', function() {
    return { filters: { project: frm.doc.project, is_active: 1 } };
});
```

### Task E.7: AQE — extend onboarding seed to cover role-routed categories

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`

> **Heads-up — breaking shape change:** Today `LAYOUTS["categories"]` is a flat list of strings (`["General Complaint", "Information Request", ...]`), and the seed loop at line 526 reads `for cat_name in layout["categories"]:`. Steps 1 + 2 below switch the list to a list of dicts AND update the loop variable / unpacking. **Both must land in the same commit** or the existing AQE run will crash with `TypeError: string indices must be integers` on the first category seed.

- [ ] **Step 1: Mark at least one category in each LAYOUT as Role-routed (NEW SHAPE)**

In `run_onboarding_tests.py`, update the categories per LAYOUT (around line 94, 129, 170 — three LAYOUT entries). Example for RW-WB:

```python
"categories": [
    {"label": "General Complaint",   "routing_target_type": "Department", "department": "Project Coordination"},
    {"label": "Information Request", "routing_target_type": "Department", "department": "Project Coordination"},
    {"label": "Suggestion",          "routing_target_type": "Department", "department": "Local Government"},
    {"label": "Appreciation",        "routing_target_type": "Role",       "role": "Field Officer"},
],
```

Repeat for KE-EAC (mark one of "Service Delivery"/"Devolved Funds"/"Land" as Role) and STJ-HOSP (mark one of "Patient Care"/"Billing"/"Staff Conduct" as Role).

- [ ] **Step 2: Update the seed loop to consume the dict shape**

Around `run_onboarding_tests.py:520-540`, replace the existing block:

```python
default_dept = next(iter(state["departments"].values()), None)
if not default_dept:
    suite.ok(f"OB-{code}.default_department_available", False,
             "no department was created → categories will fail")

# ---- step 7a: categories (require label + assigned_department) ----
for cat_name in layout["categories"]:
    c, b, rec_name, _ = upsert_doc(
        s,
        {
            "doctype": "GRM Issue Category",
            "category_name": cat_name,
            "label": cat_name,
            "abbreviation": "".join(w[0] for w in cat_name.split())[:6].upper() or "GEN",
            "assigned_department": default_dept,
            "confidentiality_level": "Public",
            "redirection_protocol": 0,
            "grm_project_link": [{"project": project_name}],
        },
        lookup_filters=[["category_name", "=", cat_name]],
    )
```

with the dict-aware version:

```python
# ---- step 7a: categories (now route to Department OR Role per LAYOUT spec) ----
for cat in layout["categories"]:
    cat_label = cat["label"]
    payload = {
        "doctype": "GRM Issue Category",
        "category_name": cat_label,
        "label": cat_label,
        "abbreviation": "".join(w[0] for w in cat_label.split())[:6].upper() or "GEN",
        "routing_target_type": cat["routing_target_type"],
        "confidentiality_level": cat.get("confidentiality_level", "Public"),
        "redirection_protocol": cat.get("redirection_protocol", 0),
        "grm_project_link": [{"project": project_name}],
    }
    if cat["routing_target_type"] == "Department":
        dept_name = resolve_department_name(s, project_name, cat["department"])
        if not dept_name:
            suite.ok(f"OB-{code}.cat.{cat_label}.dept_lookup", False,
                     f"could not resolve department '{cat['department']}' for category {cat_label}")
            continue
        payload["assigned_department"] = dept_name
    else:  # "Role"
        role_name = resolve_role_name(s, project_name, cat["role"])
        if not role_name:
            suite.ok(f"OB-{code}.cat.{cat_label}.role_lookup", False,
                     f"could not resolve role '{cat['role']}' for category {cat_label}")
            continue
        payload["assigned_role"] = role_name

    c, b, rec_name, _ = upsert_doc(
        s, payload,
        lookup_filters=[["category_name", "=", cat_label]],
    )
```

Add the lookup helpers near the top of the file (after imports, before LAYOUTS):

```python
def resolve_department_name(s, project, department_name):
    """Project-scoped GRM Issue Department lookup. Returns the doc name or None."""
    r = api.call(s, "frappe.client.get_value", doctype="GRM Issue Department",
                 filters={"project": project, "department_name": department_name},
                 fieldname="name")
    return (r or {}).get("name")

def resolve_role_name(s, project, role_name):
    """Project-scoped GRM Project Role lookup. Returns the doc name or None."""
    r = api.call(s, "frappe.client.get_value", doctype="GRM Project Role",
                 filters={"project": project, "role_name": role_name},
                 fieldname="name")
    return (r or {}).get("name")
```

(Adjust `api.call(...)` to match the existing helper signature in `run_onboarding_tests.py` — Engineering Convention 5: do not parallel-build a new HTTP client.)

- [ ] **Step 3: Add an end-to-end assertion**

In the LAYOUT runner, after Step 9 (Users) and before Step 10 (Routing finalisation):

```python
# Verify role-routed categories resolve correctly via the helper
r = api.call("egrm.services.category_routing.resolve_category_routing",
             category_name=f"{project_code}-Education")
assert r["target_type"] == "Role", f"Expected Role routing, got {r}"
assert r["target_name"], "Role target should be set"

# Verify department-routed categories still work
r2 = api.call("egrm.services.category_routing.resolve_category_routing",
              category_name=f"{project_code}-Water Access")
assert r2["target_type"] == "Department"
```

- [ ] **Step 4: Run all 3 layouts**

```bash
cd /Users/victor/egrm/apps/egrm
for layout in RW-WB KE-EAC STJ-HOSP; do
  python docs/superpowers/plans/aqe-generated/run_onboarding_tests.py --layout $layout --until-step 10
done
```

Expected: all green; role-routed categories resolve correctly; legacy department-routed categories still work.

---

## Phase F — AQE Queen Test Integration & UI Screenshot Suite

### Task F.1: Update step assertions across the AQE suite

**Files:**
- Modify: `docs/superpowers/plans/aqe-generated/run_onboarding_tests.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_ui_screenshots.py`
- Modify: `docs/superpowers/plans/aqe-generated/run_full_suite.py`

- [ ] **Step 1: Bump TOTAL_STEPS expectation to 13**

Search & replace in `aqe-generated/`:
- `TOTAL_STEPS = 12` → `TOTAL_STEPS = 13`
- `current_setup_step.*== 12` → `current_setup_step == 13`
- `--until-step 12` (in default invocations) → `--until-step 13`

- [ ] **Step 2: Add per-step assertions for new steps**

In `run_onboarding_tests.py`, add validation calls:

```python
def assert_step2_regions(api, project_code, expected_min_regions):
    n = api.call("frappe.client.get_count", doctype="GRM Administrative Region",
                 filters={"project": project_code})
    assert n >= expected_min_regions, f"Step 2 region count {n} < {expected_min_regions}"


def assert_step9_users(api, project_code, expected_min_users):
    n = api.call("frappe.client.get_count", doctype="GRM Government Worker",
                 filters={"project": project_code})
    assert n >= expected_min_users, f"Step 9 user count {n} < {expected_min_users}"


def assert_step10_routing(api, project_code):
    cats = api.call("frappe.client.get_list", doctype="GRM Issue Category",
                    filters={"project": project_code},
                    fields=["name", "routing_target_type", "assigned_department", "assigned_role"],
                    limit_page_length=0)
    for c in cats:
        target = c["assigned_department"] if c["routing_target_type"] == "Department" else c["assigned_role"]
        assert target, f"Category {c['name']} has no routing target"
```

Wire each assertion into the LAYOUT runner immediately after the corresponding step driver.

- [ ] **Step 3: Add screenshot capture for new steps**

In `run_ui_screenshots.py`, ensure the loop iterates `range(1, 14)` and captures each step. Verify with:

```bash
cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_ui_screenshots.py --project RW-WB
```

Expected: 13 PNGs saved (one per step).

- [ ] **Step 4: Run full suite end-to-end**

Run: `cd /Users/victor/egrm/apps/egrm && python docs/superpowers/plans/aqe-generated/run_full_suite.py --layout RW-WB`
Expected: all phases pass; project reaches `is_setup_complete=1`.


### Task F.2: Run all 3 layouts & capture failure report

- [ ] **Step 1: Sequential layout runs**

```bash
cd /Users/victor/egrm/apps/egrm
for layout in RW-WB KE-EAC STJ-HOSP; do
  python docs/superpowers/plans/aqe-generated/run_full_suite.py --layout $layout 2>&1 | tee /tmp/aqe-$layout.log
done
```

Expected: 3 zero-exit runs.

- [ ] **Step 2: If any failure, run systematic-debugging**

For any failing layout:
- Read the layout-specific log carefully
- Reproduce by re-running with `--debug --keep-project`
- Check the project's `current_setup_step` and DB state at the failure point
- DO NOT guess — find root cause first (per superpowers:systematic-debugging)
- Document failure + fix as a follow-up task

---

## Self-Review Notes

**Spec coverage:** Each XD step (0-12) is mapped above except Step 4 Gender (intentionally skipped per user direction). All four explicit gaps + the Step 1 enhancement requested are covered.

**Type/identifier consistency:** Step class names follow `GRMWizardStep{N}{Purpose}` and all numbers in `step_class()` match the new `STEP_TITLES` array indexes (1-based). Service module names (`admin_region_importer`, `government_worker_importer`) match between Python imports.

**Testability:** Each phase has at least one Python pytest module + an AQE Queen integration assertion. UI changes have screenshot coverage.

**Verified — no follow-up needed:** GRM Project's `default_language`, `currency`, and `country` are Link fields targeting `Language`, `Currency`, and `Country` respectively. All three doctypes ship pre-seeded with Frappe v16 core (verified against `frappe/frappe/core/doctype/{language,currency,country}/` fixtures), so no additional seeding migration is required for fresh sites. The only locale-specific gap that would warrant a fixture is if a project requires a non-ISO custom locale (e.g., a regional dialect not in Frappe's default Language seed) — that is a per-deployment data concern, not a plan-level task.
