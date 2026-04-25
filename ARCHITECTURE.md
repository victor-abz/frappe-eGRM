# eGRM Architecture

> **Status:** Design · 2026-04-25 (revised after schema audit)
> **Audience:** Engineers, project sponsors, World Bank GRM teams
> **Source materials:** WB GRM Customization Questionnaire (3-Mar-2023), WB Approach to Grievance Redress in Projects, CAO/IFC/MIGA Implementation Guide (2008), the existing eGRM codebase

This document describes the target architecture as **enhancements to the existing eGRM Frappe app**, not a replacement. The existing schema already implements per-project lookups, region hierarchies, SLA configuration, routing, citizen-confidentiality controls, and the issue lifecycle. What's missing is a thin layer that gates the UI by the **actions** a user can perform on those existing doctypes.

---

## 1. Two Truths

1. **The existing schema is the right schema.** `GRM Project`, `GRM Administrative Level Type`, `GRM Administrative Region`, `GRM Issue Category` (with `assigned_department` + appeal/escalation variants), `GRM Issue Type`, `GRM Issue Status`, `GRM Issue Department`, `GRM User Project Assignment`, `GRM Issue` and its child tables already model the whole grievance lifecycle. The `GRM Project Link` m:m bridge already makes lookups project-scoped.
2. **What's missing is one layer above the schema:** a way to express *what actions a user is allowed to perform* — not as Frappe roles (today's model) but as composable **duties** that gate the UI per project.

This document is small because the work is small.

---

## 2. The 6 Duties — Actions on Existing Doctypes

The WB Customization Questionnaire defines 7 duties; in the digital-only operating model Uptake and Data Entry collapse into one. Each duty maps to specific **actions on existing doctypes**, not to new schema.

| Duty | What it lets a user do | What it touches |
|---|---|---|
| **Intake** | Create a new `GRM Issue` (Draft → Submitted) | `GRM Issue` insert |
| **Review** | Move a Submitted issue to a Reviewed/Rejected `GRM Issue Status`; refine `category`, `issue_type`, `confidentiality` | `GRM Issue.status`, `category`, `issue_type` |
| **Assignment** | Set or change `GRM Issue.assignee` and routing | `GRM Issue.assignee` |
| **Investigate & Resolve** | Add `grm_issue_comment`, `grm_issue_attachment`; set `resolution_text`, `resolved_by`, `resolution_date`; submit the issue | `GRM Issue.resolution_*`, child tables, `submit` |
| **Feedback** | Capture citizen rating, appeal flow (`appeal_submitted`, `appeal_date`), close the issue | `GRM Issue.rating`, `appeal_*`, final-status transition |
| **Supervise** | Read all in-scope issues, force-reassign, force-close, see dashboards, manage `GRM User Project Assignment` rows within scope | Cross-cutting read + assignment management |

All actions exist today on `GRM Issue` and `GRM User Project Assignment`. The duty system gates **which UI surfaces each user sees**; the underlying Frappe permissions still authorize each API call.

---

## 3. New Schema — 3 DocTypes + 2 Fields

That's it. Everything else uses what's already there.

### 3.1 `GRM Duty` (catalog)

A six-row catalog of standard duties. Seeded via patch.

```
fields:
  duty_name (Data, unique)              # "Intake", "Review", ...
  label (Data)                          # display label
  description (Small Text)
  lifecycle_phase (Select)              # Intake / Triage / Resolution / Feedback / Oversight
  icon (Data)                           # lucide icon name for UI
```

### 3.2 `GRM Project Role`

A role definition scoped to one project, composing duties.

```
fields:
  role_name (Data)                      # e.g. "GRC Chair", "Field Officer"
  project (Link → GRM Project)
  admin_level (Link → GRM Administrative Level Type, optional)
  duties (Table → GRM Project Role Duty)
  description (Small Text)
  is_active (Check, default 1)

autoname: format:{project}-{role_name}
```

### 3.3 `GRM Project Role Duty` (child of Project Role)

```
fields:
  duty (Link → GRM Duty)
istable: 1
```

### 3.4 Two new fields on `GRM Project`

```
is_setup_complete (Check, default 0)   # set by wizard on completion
current_setup_step (Int, default 1)    # wizard resume marker
```

### 3.5 Frappe Role catalog rewrite

| Action | Roles |
|---|---|
| Create | `GRM Intake`, `GRM Review`, `GRM Assignment`, `GRM Investigate & Resolve`, `GRM Feedback`, `GRM Supervise`, `GRM Platform Administrator` |
| Delete | `GRM Administrator`, `GRM Project Manager`, `GRM Department Head`, `GRM Field Officer` |

Driven by patches:
- `seed_grm_role_catalog.py` — creates the seven new roles (idempotent)
- `migrate_users_to_duty_roles.py` — for each user, replaces legacy roles with duty-roles derived from their active Project Roles, then removes the legacy roles from `tabHas Role`
- `delete_legacy_grm_roles.py` — drops the four legacy `Role` records once no user references them
- A doctype-permission migration that rewrites `permissions[]` arrays in every GRM JSON

That's the entire schema + role-catalog delta.

---

## 4. The Existing Schema (Reference Map)

For each questionnaire concern, here is the existing doctype that already covers it:

| Questionnaire concern | Lives on |
|---|---|
| Project info, code, dates, language | `GRM Project` direct fields |
| Uptake channels (web/SMS/letter/in-person) | **Operational, not data** — the public portal already accepts submissions; the mobile app via `api/sync.py`; in-person via desk Intake form. No schema needed. |
| Administrative levels with custom names + SLA per level | `GRM Administrative Level Type` (per-project, fields: `level_order`, `acknowledgment_days`, `resolution_days`, `reminder_before_days`, `auto_escalate`) |
| Administrative regions with hierarchy | `GRM Administrative Region` (per-project, `parent_region` self-link, materialized `path`) |
| GRC committee membership at each level | A user holding a `GRM Project Role` whose `admin_level` matches. **No separate "Member" doctype needed** — users are committee members by virtue of their assignment + role. |
| Issue categories + routing target | `GRM Issue Category` with `assigned_department`, `assigned_appeal_department`, `assigned_escalation_department`, optional `administrative_level`. Per-project via `grm_project_link`. |
| Per-category SLA override | Optional new field on `GRM Issue Category.override_resolution_days` if needed; the questionnaire flags this as optional |
| Departments per project, with head | `GRM Issue Department` with `head` (Link → User), per-project via `grm_project_link` |
| Issue types | `GRM Issue Type`, per-project via `grm_project_link` |
| Issue states (Draft/Submitted/Resolved/etc.) | `GRM Issue Status` with `initial_status`/`final_status`/`open_status`/`rejected_status` flags, per-project via `grm_project_link` |
| Issue tracking record | `GRM Issue` with full audit log via `grm_issue_log` child table |
| Resolution workflow | `GRM Issue.resolution_text/_by/_date/_days/_accepted/rating` + `resolution_agreement_*` |
| Appeal workflow | `GRM Issue.appeal_submitted`, `appeal_date`. Routing via `GRM Issue Category.assigned_appeal_department`. |
| Citizen confidentiality (visible / confidential / on behalf of) | `GRM Issue.citizen_type` Select + `citizen_confidential`, `contact_info_confidential` Password fields |
| Confidentiality of sensitive categories (e.g. GBV, corruption) | `GRM Issue Category.confidentiality_level` Select |
| Citizen demographics (age, gender, group) | `GRM Issue.gender`, `citizen_age_group` Link, `citizen_group_1/2` Link → `GRM Issue Age Group` / `GRM Issue Citizen Group` (per-project lookups) |
| Government-worker activation | `GRM User Project Assignment` with `activation_code`, `activation_status`, expiry, attempts |
| Notifications, escalations, scheduled checks | `GRM Notification Template` + `egrm/scheduled_jobs/sla_monitor.py` |
| Public reports + transparency | Already via `api/public_metrics.py`, `api/public_reports.py`, the React portal |

**The wizard's job is to set up rows in these existing doctypes — not to introduce parallel structures.**

---

## 5. Authority Layers

| Layer | Roles | Scope |
|---|---|---|
| **Platform** | `System Manager`, `GRM Platform Administrator` | Create projects, manage Frappe Users globally, run the Setup Wizard, manage system catalogs (`GRM Administrative Level Type` template lists, `Android App Version`, `GRM Duty`) |
| **Project** | Any `GRM Project Role` for that project | Day-to-day work; data scope enforced by existing `GRM User Project Assignment` + auto-synced `User Permission` rows |

The Platform layer is **not described in the WB questionnaire** because the questionnaire defines what a project configures *inside* the system. Creating projects is the act that *issues* questionnaires.

---

## 6. Permissions — Duty-Keyed L1, Project-Scoped L2, Field-Level L3

**The four legacy Frappe Roles** (`GRM Administrator`, `GRM Project Manager`, `GRM Department Head`, `GRM Field Officer`) **are deleted**. They are replaced with **six duty-named Frappe Roles**, one per duty:

```
GRM Intake
GRM Review
GRM Assignment
GRM Investigate & Resolve
GRM Feedback
GRM Supervise
```

Plus a single **platform role** outside the duty system: `GRM Platform Administrator` (creates projects, manages users, runs the wizard). `System Manager` retains full bypass.

### 6.1 L1 — Doctype Permission Matrix (rebuilt around duties)

Every GRM doctype's `permissions[]` is rewritten so each duty-role unlocks the actions appropriate to that duty.

| Frappe Role | `GRM Issue` | Lookup doctypes (Category / Type / Status / Department / Age Group / Citizen Group) | `GRM User Project Assignment` |
|---|---|---|---|
| `GRM Intake` | Create | Read | – |
| `GRM Review` | Read + Write | Read | – |
| `GRM Assignment` | Read + Write | Read | – |
| `GRM Investigate & Resolve` | Read + Write + Submit | Read | – |
| `GRM Feedback` | Read + Write | Read | – |
| `GRM Supervise` | Read + Write + Delete + Cancel + Amend | Create + Read + Write | Create + Read + Write |
| `GRM Platform Administrator` | Read + Write + Create + Delete | Full | Full |
| `System Manager` | Full bypass | Full bypass | Full bypass |

### 6.2 L2 — Record Scope (unchanged)

`User Permission` auto-synced from `GRM User Project Assignment` (helper: `egrm/utils/user_permissions.py`). Filters every doctype that links to `GRM Project` to the user's assigned projects. Applies even to a user with multiple duties — they can act on records from *their* projects only.

### 6.3 L3 — Field-Level Discipline (controller validation)

Frappe doctype permissions are doctype-wide, not per-field. To enforce "a `GRM Review` user can only edit `status` and `category`, not `assignee` or `resolution_text`", the `GRM Issue.validate()` controller adds field-changed checks:

```python
# Pseudocode in egrm/egrm/doctype/grm_issue/grm_issue.py
def _assert_can_change(self, field: str, required_duty: str) -> None:
    if self.has_value_changed(field) and not _user_has_duty(required_duty, self.project):
        frappe.throw(_(f"You need the {required_duty} duty to change {field}."))

def validate(self):
    self._assert_can_change("status", "Review")
    self._assert_can_change("category", "Review")
    self._assert_can_change("assignee", "Assignment")
    self._assert_can_change("resolution_text", "Investigate & Resolve")
    self._assert_can_change("rating", "Feedback")
    self._assert_can_change("appeal_submitted", "Feedback")
    # ... existing validation continues ...
```

`_user_has_duty(duty, project)` reads from the user's active assignments — it bypasses if the user has `Supervise` for that project, `GRM Platform Administrator`, or `System Manager`. This means the API enforces the same rules the UI displays, with no client-trust assumption.

### 6.4 How a user gets duties

When an admin creates a `GRM User Project Assignment`:
1. They pick a `GRM Project Role` (a per-project bundle of duties — e.g. "GRC Chair = Review + Assignment + Supervise").
2. The assignment controller's `assign_role_to_user()` walks the Project Role's `duties[]` table and grants each corresponding Frappe duty-role on the User's `roles` table (idempotent — only adds missing roles).
3. On `is_active=0` or `on_trash`, the controller's `remove_role_from_user()` removes a duty-role only if no *other* active assignment of the same user uses that duty (so a multi-project user keeps their `GRM Review` role as long as at least one project still assigns it).

Bonus: a user with `GRM Review` granted via Project A continues to receive UI gates restricted to Project A only, because `frappe.boot.egrm.duties` is the **active project's** duty subset (not the union). The L1 role lets them act; L2 (User Permission) restricts to records they can see; L3 (controller) catches edge cases like multi-project drift.

---

## 7. Rendering Strategy — Standard Workspace + display_depends_on

The eGRM workspace uses Frappe v16's standard Workspace JSON. Per-item visibility comes from the `display_depends_on` field — a JS expression evaluated client-side against `frappe.boot`.

A `boot_session` hook injects per-user duty data:

```python
# egrm/utils/boot.py
bootinfo.egrm = {
    "active_project": <user's currently-active project>,
    "duties": ["Intake", "Investigate & Resolve", ...],
    "is_platform_admin": True/False,
    "available_projects": [...],
}
```

Workspace JSON wires items:

```json
{
  "label": "Pending Review",
  "link_to": "GRM Issue",
  "filters": "[[\"GRM Issue\",\"status\",\"=\",\"Submitted\"]]",
  "display_depends_on": "eval:frappe.boot.egrm.duties.includes('Review')"
}
```

Single workspace, items adapt per user. No JS rendering loop, no custom Vue page, no fork of the framework.

**Custom desk pages** are needed only for two surfaces the standard workspace can't deliver:

1. **Project Setup Wizard** (`/desk/grm-project-wizard`) — orchestrates writes to existing doctypes through a guided multi-step UI.
2. **Users-by-project** (`/desk/grm-users`) — aggregated view of `User × GRM User Project Assignment` with inline grant/revoke. Standard Frappe list view doesn't aggregate cross-doctype.

---

## 8. UI Phase-Groups (Single Workspace, Conditional Cards)

The single `egrm` workspace contains five phase-group cards. Each is shown only if the user has a triggering duty.

```
┌─ INTAKE ────────────────┐  Trigger: Intake
│ • Log a Grievance       │     → opens GRM Issue new form
│ • Drafts                │     → list of GRM Issue with status="Draft"
└─────────────────────────┘

┌─ TRIAGE ────────────────┐  Trigger: Review or Assignment
│ • Pending Review        │     → list of status="Submitted"
│ • Ready to Assign       │     → list of status="Reviewed"
└─────────────────────────┘

┌─ RESOLUTION ────────────┐  Trigger: Investigate & Resolve
│ • My Cases              │     → list filtered by assignee
│ • All Cases in Scope    │     → list with status="In Progress"
└─────────────────────────┘

┌─ FEEDBACK ──────────────┐  Trigger: Feedback
│ • Awaiting Feedback     │     → list with status="Awaiting Feedback"
│ • Appeals               │     → list with appeal_submitted=1
└─────────────────────────┘

┌─ OVERSIGHT ─────────────┐  Trigger: Supervise
│ • Project Health        │     → existing GRM Issue Dashboard
│ • Escalations           │     → list with escalate_flag=1
│ • Team                  │     → /desk/grm-users (custom page)
└─────────────────────────┘
```

A user with all six duties sees the full grid. A user with only Intake sees one card.

---

## 9. Project Setup Wizard — An Orchestrator over Existing Schema

The wizard is a custom desk page. Each of its 12 sections (mirroring the WB Questionnaire) **writes to existing doctypes** — there is no parallel "wizard data store". Drafts persist via `GRM Project.current_setup_step`; activation flips `is_setup_complete = 1` after validation.

| Wizard step | Data it edits |
|---|---|
| 1. Project info | `GRM Project` direct fields (existing) |
| 2. Uptake notes | Free-text notes on `GRM Project.description` (uptake is operational, not schema) |
| 3. Administrative levels | Creates/edits `GRM Administrative Level Type` rows (existing, per-project) |
| 4. GRC member roles | Creates `GRM Project Role` rows (NEW); committee members are users assigned to those roles via existing `GRM User Project Assignment` |
| 5. Issue categories + routing | Creates `GRM Issue Category` rows + sets `assigned_department`/`assigned_appeal_department`/`assigned_escalation_department` (all existing) |
| 6. Issue types | Creates `GRM Issue Type` rows (existing) |
| 7. Issue statuses | Creates `GRM Issue Status` rows with `initial_status`/`final_status`/etc. flags (existing) |
| 8. Departments | Creates `GRM Issue Department` rows with `head` (existing) |
| 9. SLAs | Edits `GRM Administrative Level Type` SLA fields (existing) |
| 10. Citizen lookups | Creates `GRM Issue Age Group` and `GRM Issue Citizen Group` rows (existing) |
| 11. Notifications | Selects/creates `GRM Notification Template` rows; links to `GRM Project` template fields (existing) |
| 12. Activation | Validates internal consistency; sets `is_setup_complete = 1` |

**Result:** zero new schema for steps 1, 2, 3, 5–12. Only step 4 introduces the new `GRM Project Role`.

---

## 10. Existing Functionality Already in Place

For clarity — these capabilities exist today and **do not need rebuilding**:

- **Public submission** via React portal (`grm-portal/`)
- **Mobile sync** via `api/sync.py` (WatermelonDB sync)
- **Anonymous intake + tracking codes** (`generate_tracking_code` in commands)
- **Government-worker activation flow** (6-digit codes, 48 h expiry, retry handling)
- **SLA tracking + auto-escalation** (`scheduled_jobs/sla_monitor.py`, `SLAManager`)
- **Notification templates** per project (`GRM Notification Template` + `send_notification`)
- **Public reports** (`api/public_reports.py`, monthly/quarterly aggregation)
- **Public metrics dashboard** (`api/public_metrics.py`)
- **Region hierarchy traversal + permission cascade** (`is_child_region` in `grm_issue_permissions.py`)
- **Issue dashboard** (commit `234495f` — "Add comprehensive GRM Issue Dashboard")
- **Manual escalate / resend notification** whitelisted methods on `GRM Issue`
- **Issue Actions** (commit `5592e48`)

---

## 11. Migration

Three phases, each independently shippable:

1. **Schema + Role Catalog** (Phase 1):
   - Add `GRM Duty` catalog + seed 6 duties.
   - Add `GRM Project Role` + child table.
   - Add 2 fields to `GRM Project` (`is_setup_complete`, `current_setup_step`).
   - **Create the 7 new Frappe Roles** (6 duty-roles + `GRM Platform Administrator`).
   - **Rewrite `permissions[]` on every GRM doctype JSON** to use duty-roles.
   - **Migrate User → Role mappings**: for each active `GRM User Project Assignment`, expand the legacy role to the matching duty-role set on the user; remove legacy roles after cutover.
   - **Repoint `GRM User Project Assignment.role`** Link target from `Role` → `GRM Project Role`.
   - Update assignment controller's `assign_role_to_user()` / `remove_role_from_user()` to manage duty-roles by walking the Project Role's `duties[]` table.
   - Add `validate()` field-level enforcement to `GRM Issue` controller (L3).
   - `boot_session` hook + `User Permission` auto-sync helper.
   - **Drop the four legacy Frappe Roles** once no user references them.
2. **Workspace consolidation** (Phase 2): single duty-driven `egrm` workspace + Platform workspace; delete the four legacy role-workspaces.
3. **Wizard + Users page** (Phase 3): two custom desk pages.

Each phase ends with a tagged commit; reversible until the next phase begins.

---

## 12. References

- WB GRM Customization Template (3 March 2023) — `Empty - GRM Customization Questionnairre.pdf`
- *The World Bank's Approach to Grievance Redress in Projects* — `wb_approach_to_grievance_redress_in_projects_0.pdf`
- *CAO/IFC/MIGA Grievance Mechanism Implementation Guide (2008)*
- Frappe Framework v16 Workspace + boot_session documentation
- The existing eGRM codebase, particularly:
  - `egrm/egrm/doctype/grm_issue/` (the lifecycle source of truth)
  - `egrm/egrm/doctype/grm_issue_category/` (the routing source of truth)
  - `egrm/egrm/doctype/grm_administrative_level_type/` (the SLA source of truth)
  - `egrm/server_scripts/grm_issue_permissions.py` (the existing permission cascade)
