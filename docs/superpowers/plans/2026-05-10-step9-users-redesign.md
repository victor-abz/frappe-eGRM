# Step 9 (Users) — Redesign Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current 3-tab Step-9 (CSV / Auto-generate / Activation Codes) with a unified user-management surface that (a) lists existing project users with inline pill-edit, (b) supports single-add via a small form, and (c) handles bulk import of any size by **wrapping Frappe's `Data Import` engine** with a project-aware column mapper that resolves hierarchical admin levels and enforces doctype-driven required fields.

**Architecture (locked):** The wizard does NOT reimplement bulk import. It *wraps* `frappe.core.doctype.data_import.data_import.DataImport` — same background-job runner, same preview/log, same audit trail accessible at `/app/data-import?reference_doctype=GRM User Project Assignment`. The wizard adds three project-shaped extensions on top:
1. **Hierarchical-region preprocessor** — multiple admin-level columns (Province / District / Sector — names defined per project) get resolved into the single `administrative_region` Link expected by the doctype, before Data Import sees the file.
2. **Doctype-introspected required/optional matrix** — the mapper reads `GRM User Project Assignment.fields[]` and `User.fields[]` for `reqd: 1` markers; never hard-codes "what must be in the CSV".
3. **Generic column-mapper UX** — for every source column, user picks a target field from a dropdown; for the special `administrative_region` target, a sub-picker chooses *which project-defined level type* this column represents.

**Tech Stack:** Frappe v16 + the existing `egrm/page/grm_project_wizard` desk Page (jQuery / Bootstrap 4) + the existing `egrm/services/admin_region_importer.py` for region creation reuse.

> **Verified Frappe v16 surface (2026-05-10):**
> - `frappe.client.insert` for creating `Data Import` records
> - `frappe.core.doctype.data_import.data_import.start_import(data_import: str)` whitelisted method
> - `frappe.client.get_value("Data Import", name, ["status","import_log_preview","payload_count"])` for polling
> - `frappe.get_meta(doctype).fields` for required/optional introspection
> - `frappe.utils.csvutils.read_csv_content` and `frappe.utils.xlsxutils.read_xlsx_file_from_attached_file` for parsing
> - All confirmed in `frappe/frappe@version-16` (16.17.5).

---

## Engineering Conventions

1. **Reuse, don't rebuild.** The Data Import engine handles backgrounding, retry, error logging, status polling. Our code only does (a) preprocessing the CSV, (b) creating the Data Import record, (c) rendering its preview/log inline.
2. **Doctype is source of truth.** Required vs optional is read from `frappe.get_meta(...).fields[].reqd` — never duplicated as a constant in JS or Python.
3. **No new doctypes.** The current `GRM User Project Assignment` carries every field we need.
4. **Module ≤ 400 lines.** If `grm_project_wizard.py` grows past 400 lines while adding endpoints, split into `grm_project_wizard_user_import.py` and re-export.
5. **Step 9 class ≤ 400 lines.** The class will host: (1) users-list panel, (2) single-add form, (3) bulk-import flow. If it grows past 400 lines, split into `GRMWizardStep9UsersList`, `GRMWizardStep9UserAdd`, `GRMWizardStep9UserImport` inner classes mounted by an outer composition class — same pattern as `GRMWizardStep2AdminUnits`.
6. **Frappe-native widgets where possible.** Use `frappe.ui.form.make_control({df: {fieldtype:"Link", options:"User"}, parent, render_input:true})` for the User picker so search behaves identically to a regular form.

---

## File Plan

| File | Action | Purpose |
|---|---|---|
| `egrm/egrm/page/grm_project_wizard/grm_project_wizard.js` | Modify (`GRMWizardStep9Users` class) | Replace existing 3-tab class with composition: List + Add + Import |
| `egrm/egrm/page/grm_project_wizard/grm_project_wizard.css` | Add | Pill styles, mapper-table styles, bulk-actions strip (re-use existing `.grm-bulk-*` patterns) |
| `egrm/egrm/page/grm_project_wizard/grm_project_wizard.py` | Modify | Add 6 whitelisted endpoints (see API surface below) |
| `egrm/services/user_import.py` | **New** | Region-hierarchy resolver + CSV/XLSX preprocessor + Data Import record creator. Pure functions, callable from RPC and CLI. |
| `egrm/commands/import_users.py` | **New** | Thin CLI façade around `services/user_import.py` for non-wizard usage |
| `docs/superpowers/plans/aqe-generated/run_step9_user_import_tests.py` | **New** | Playwright walker covering: empty-state, single-add, CSV mapping, region auto-create, large-list pagination |

---

## API Surface (Python, all `@frappe.whitelist()`)

```python
# 1. Existing assignments — paginated, searchable
list_project_users(project, search=None, level_type=None, role=None, status=None,
                   start=0, limit=25) -> {rows, total, summary: {active, pending, draft, unmapped}}

# 2. Single-add
create_assignment(project, user, role, administrative_region=None,
                  department=None, position_title=None) -> {name, activation_code}

# 3. Inline pill-edit + bulk-actions
update_assignment_field(name, fieldname, value) -> {ok}
bulk_update_assignments(names: list, fieldname, value) -> {updated, errors}
bulk_remove_assignments(names: list) -> {removed, errors}

# 4. Doctype introspection (used by mapper)
get_assignment_field_meta(project) -> {
    fields: [{fieldname, label, fieldtype, reqd, options, ...}],
    project_levels: [{name, level, level_type}],  # ordered highest→lowest
    project_roles:  [{name, role_name, admin_level_type}],
}

# 5. Bulk import — wraps Data Import
prepare_user_import(project, file_url, header_mapping: dict, level_mapping: dict,
                    auto_create_regions=True) -> {
    data_import: name,         # the created Data Import doc
    rows_total, rows_ready, rows_skipped,
    regions_to_create: list,
    warnings: list, errors: list,
    preview: [first 50 rows resolved]
}
start_user_import(data_import) -> {ok, job_id}
poll_user_import(data_import) -> {status, progress, log_html, succeeded, failed}

# 6. Template downloads
download_user_template(project, format="csv") -> file (csv|xlsx)
```

---

## Column-Mapper Logic (the wrap point)

Source CSV/XLSX has arbitrary headers. For each source column, the mapper offers two-tier targets:

```
Target                              Sub-picker
─────────────────────────────────────────────────────────────
(skip)                              —
User → email                        —
User → first_name                   —
User → last_name                    —
User → phone                        —
User → gender                       —
Assignment → role                   —
Assignment → position_title         —
Assignment → department             —
Assignment → administrative_region  Pick project-defined level type
                                    (Province / District / Sector / …
                                     each is a row in GRM Administrative Level Type
                                     filtered to this.project)
```

**Auto-detect heuristic** (best-effort; user can override every guess):
1. Header-name fuzzy match against doctype field labels (case-insensitive, strip spaces/underscores).
2. For unmatched columns, try matching against `GRM Administrative Level Type` rows for the project — if header == level type name, propose `administrative_region → ‹that level›`.
3. Headers containing "name" → first/last_name (split if one column has full name; user confirms).

**Multiple admin-level columns:** mapper enforces "at most one column per level type". Order of source columns implies hierarchy (left-to-right = highest-to-lowest in the project's level tree). User can swap via drag handles.

**Required-field gate:** "Continue → preview" button disabled until every `reqd: 1` field on `GRM User Project Assignment` (and the implied `User.email`, `User.first_name`, `User.last_name`) has a mapped source column.

---

## Region Resolution (the preprocessor)

Per row, walk the mapped admin-level columns top-down:

```python
def resolve_region(row, level_columns_ordered, project, auto_create=True):
    """
    level_columns_ordered = [(level_type_name, source_value), ...] from highest to lowest
    Returns: (administrative_region_id, [created_levels_along_the_way])
    """
    parent = None
    created = []
    for level_type, value in level_columns_ordered:
        if not value:
            continue  # skip empty cells; resolution stops at last non-empty
        existing = frappe.db.exists("GRM Administrative Region", {
            "project": project, "administrative_level": level_type,
            "name1": value, "parent_administrative_region": parent,
        })
        if existing:
            parent = existing
            continue
        if not auto_create:
            raise ValidationError(f"Region not found: {level_type}={value}")
        new_id = frappe.get_doc({
            "doctype": "GRM Administrative Region",
            "project": project, "administrative_level": level_type,
            "name1": value, "parent_administrative_region": parent,
        }).insert(ignore_permissions=False).name
        created.append((level_type, value, new_id))
        parent = new_id
    return parent, created
```

This runs ONCE during `prepare_user_import` to:
1. Materialize the resolved `administrative_region` value for every row.
2. Stage the rows into a temp CSV (one per project, in `frappe.local_site_path/private/files/grm_user_import/{data_import_name}.csv`).
3. Attach that staged CSV to the `Data Import` record's `import_file` field.
4. Frappe's Data Import then handles the rest (preview / errors / start_import / log).

---

## UI Layout (matches mockup at `/tmp/wiz-walker/step9-mockup.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│ Project users · 247 assigned                                    │
│   [search]  [level filter]  [role filter]  [status]   [pager]   │
│   ── bulk-actions strip (when ≥1 selected) ──────────────────── │
│   table.users:                                                  │
│      ☐ │ Name/Email │ Position │ Role pill │ Level pill │ Duty? │
│      ──┼────────────┼──────────┼───────────┼────────────┼──────│
│        │ …                                                      │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ Add users                                                        │
│   [Single user] [CSV/Excel import]  ← toggle                    │
│   { single: form with required/optional driven by doctype }     │
│   { bulk: 4-stage flow                                          │
│     1) Download template (csv / xlsx, project-tailored)         │
│     2) Upload file                                              │
│     3) Map columns (source → target; admin-levels get sub-pick) │
│     4) Preview + Import (creates Data Import doc, polls log)    │
│   }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phased Tasks

### Phase A — Service module + doctype introspection (server only)

- [x] **A.1** Create `egrm/services/user_import.py` with: `resolve_region(...)`, `auto_detect_mapping(headers, project_meta)`, `validate_mapping(mapping, project_meta)`, `materialize_staged_csv(rows, mapping, project, auto_create_regions)`.
- [x] **A.2** Add unit test `tests/services/test_user_import.py` covering: 3-level hierarchy resolution, partial path (only Province + District given), missing-region with `auto_create=False` raises, missing-region with `auto_create=True` creates the chain.
- [x] **A.3** Add `get_assignment_field_meta(project)` whitelisted endpoint that returns: doctype field metadata for `GRM User Project Assignment` + `User`, project's level types ordered by `level` (highest first), project's roles with their `admin_level` link.

### Phase B — Wrap Data Import (server)

- [x] **B.1** Add `prepare_user_import(project, file_url, header_mapping, level_mapping, auto_create_regions)` whitelisted endpoint. Steps: (1) read uploaded file from `file_url`, (2) call `materialize_staged_csv`, (3) save staged CSV under `private/files/grm_user_import/`, (4) create a `Data Import` record with `reference_doctype="GRM User Project Assignment"`, `import_type="Insert New Records"`, `import_file=<staged>`, (5) return preview rows + `data_import` name.
- [x] **B.2** Add `start_user_import(data_import)` whitelisted endpoint that calls `frappe.core.doctype.data_import.data_import.form_start_import(data_import)`.
- [x] **B.3** Add `poll_user_import(data_import)` whitelisted endpoint that returns `{status, payload_count, import_log_preview, succeeded, failed}` from the Data Import doc.
- [x] **B.4** Add `download_user_template(project, format)` — generates CSV (or XLSX) with one column per project's level type + required User/Assignment fields. Reuse `frappe.utils.xlsxutils`.

### Phase C — Existing-users panel (Section A of Step 9)

- [x] **C.1** Add `list_project_users(...)`, `update_assignment_field`, `bulk_update_assignments`, `bulk_remove_assignments` endpoints.
- [x] **C.2** Build `GRMWizardStep9UsersList` inner class: search bar, filter dropdowns, pager, bulk-actions strip (using existing `grm_render_bulk_toolbar` + `grm_wire_bulk_table` helpers), table with inline pills.
- [x] **C.3** Pill-edit popovers: clicking a pill opens a small dropdown grounded next to the pill — pick role / level / duty / region — calls `update_assignment_field`.

### Phase D — Single-add form (Section B-Single)

- [ ] **D.1** Build `GRMWizardStep9UserAdd` inner class. Use `frappe.get_meta("GRM User Project Assignment").fields` to drive which fields are shown and which are required (red asterisks). User picker uses `frappe.ui.form.make_control`.
- [ ] **D.2** Region picker: cascading select fed by project's level tree. When user picks a Project Role, the cascade resets to the role's `admin_level` and disables levels below.
- [ ] **D.3** Submit calls `create_assignment` then auto-refreshes the list above.

### Phase E — Bulk import flow (Section B-Bulk)

- [ ] **E.1** Build `GRMWizardStep9UserImport` inner class with 4 stages.
- [ ] **E.2** Stage 1 (template): "Download CSV template" + "Download Excel template" buttons → `download_user_template(project, format)`.
- [ ] **E.3** Stage 2 (upload): drag-drop zone + `<input type=file>`. After upload, call `upload_file` → file_url.
- [ ] **E.4** Stage 3 (mapping): call `auto_detect_mapping`, render mapper table, allow dropdown overrides, render required-field-gate banner.
- [ ] **E.5** Stage 4 (preview + import): call `prepare_user_import` → show first 50 resolved rows + warnings + "regions to create" checkbox + "Start import" button. Button calls `start_user_import` then polls `poll_user_import` every 1.5s, rendering progress bar + log tail. On completion, refresh the users list.
- [ ] **E.6** Empty-state: when project has 0 assignments, show only Section B (collapsed Section A with "No users yet"), with bulk-import as the default tab.

### Phase F — Test plan

- [ ] **F.1** Unit tests: `test_user_import.py` — region resolution, header auto-detect, mapping validation, missing-required-field rejection.
- [ ] **F.2** Integration test: import the actual `eGRM users.xlsx` against RDAP — verify 24 users created, 8 regions auto-created, all linked to correct admin region, role/duty unmapped pills visible.
- [ ] **F.3** Playwright walker `run_step9_user_import_tests.py` (visible browser) covering: empty-state → upload → mapping → preview → import-running → log → list-refresh-shows-new-users.
- [ ] **F.4** Large-list test: import 1000 synthetic users; verify pagination + search + bulk-actions remain responsive.

### Phase G — Migration / cleanup

- [ ] **G.1** Remove existing `parse_users_csv`, `bulk_create_users`, `auto_generate_regional_users`, `export_user_template`, `export_activation_codes` whitelisted methods (or leave as deprecated façades that delegate to new endpoints — decide based on whether any other code calls them; verify with grep first).
- [ ] **G.2** Update `STEP_TITLES` if the step's title needs adjustment (probably stays "Users").

---

## Open Questions (none blocking)

- Does the user picker need to support inviting brand-new users (auto-creating a `User` doc) or only assigning existing Frappe users? **Decision:** auto-create User docs from the CSV's `email/first_name/last_name`; if email already maps to an existing User, link to that one.
- Should the staged CSV be deleted after the import succeeds, or kept for audit? **Decision:** keep — Frappe's `Data Import.import_file` is the audit trail. Add a daily cleanup hook for staged files older than 30 days.
- Should bulk-import support "update existing" mode (re-running the same CSV updates assignments rather than erroring on duplicates)? **Decision:** v1 is insert-only; v2 can add the toggle (Frappe Data Import natively supports it).

---

## Out of scope

- SMS provider integration for activation codes (already exists; reuse).
- Mobile-side flows (the activation code path on the mobile app is unchanged).
- Permission roles on the `Data Import` doctype itself (Frappe's defaults suffice).
