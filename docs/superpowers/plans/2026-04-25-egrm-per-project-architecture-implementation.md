# eGRM Duty-Driven Workspace + Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a duty-driven workspace layer over the existing eGRM schema, plus a Project Setup wizard and a Users-by-project page. The existing schema is preserved intact; we add three small DocTypes and two fields on `GRM Project`, then build UI on top.

**Architecture:** Three phases. Phase 1 introduces the `GRM Duty` catalog, the `GRM Project Role` + child table, **rewrites the L1 Frappe-Role catalog** (deletes the four legacy roles, creates 6 duty-roles + 1 platform role, rewrites every GRM doctype's `permissions[]` JSON to be keyed by duty), migrates existing user-role mappings, adds field-level enforcement in the `GRM Issue` controller, plumbs the `boot_session` payload, and auto-syncs `User Permission`. Phase 2 consolidates four legacy workspaces into one duty-driven `egrm` workspace plus a Platform workspace. Phase 3 ships the Project Setup wizard and the Users-by-project custom page.

**Tech Stack:** Frappe v16, Python 3.14, Frappe Workspace JSON, vanilla JS for desk pages, Playwright for E2E verification.

**Visual ground truth for UI tasks:** Adobe XD prototype at <https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/>. Every UI task ends with a "visual diff against XD" gate.

**Key principle:** **Enhance, do not replicate.** Every wizard step writes to existing doctypes (`GRM Project`, `GRM Administrative Level Type`, `GRM Administrative Region`, `GRM Issue Category`, `GRM Issue Type`, `GRM Issue Status`, `GRM Issue Department`, `GRM Issue Age Group`, `GRM Issue Citizen Group`, `GRM Notification Template`). Only `GRM Duty` and `GRM Project Role` are new.

---

## Phase Overview

| # | Phase | New schema | Output | Days |
|---|---|---|---|---|
| 1 | Schema + plumbing | `GRM Duty`, `GRM Project Role`, `GRM Project Role Duty`, 2 fields on `GRM Project` | Boot payload, User Permission sync, role link migrated | 2 |
| 2 | Workspace consolidation | none | One duty-driven `egrm` workspace + Platform workspace; 4 legacy workspaces removed | 1 |
| 3 | Wizard + Users page | none | `/desk/grm-project-wizard` (custom page), `/desk/grm-users` (custom page) | 4 |

Total: ~7 working days. Existing functionality (issue lifecycle, SLA, notifications, public portal, mobile sync) is untouched.

---

## File Structure

### Created

```
egrm/egrm/doctype/
├── grm_duty/                              (Phase 1)
│   ├── __init__.py
│   ├── grm_duty.json
│   └── grm_duty.py
├── grm_project_role/                      (Phase 1)
│   ├── __init__.py
│   ├── grm_project_role.json
│   └── grm_project_role.py
└── grm_project_role_duty/                 (Phase 1, child)
    ├── __init__.py
    ├── grm_project_role_duty.json
    └── grm_project_role_duty.py

egrm/egrm/workspace/
├── egrm/                                  (Phase 2)
│   ├── __init__.py
│   └── egrm.json
└── egrm_platform/                         (Phase 2)
    ├── __init__.py
    └── egrm_platform.json

egrm/page/
├── grm_project_wizard/                    (Phase 3)
│   ├── __init__.py
│   ├── grm_project_wizard.json
│   ├── grm_project_wizard.py
│   ├── grm_project_wizard.js
│   └── grm_project_wizard.css
└── grm_users/                             (Phase 3)
    ├── __init__.py
    ├── grm_users.json
    ├── grm_users.py
    ├── grm_users.js
    └── grm_users.css

egrm/utils/
├── boot.py                                (Phase 1)
├── duties.py                              (Phase 1)
└── user_permissions.py                    (Phase 1)

egrm/patches/v16_0/
├── __init__.py
├── seed_duty_catalog.py                   (Phase 1)
├── backfill_default_project_roles.py      (Phase 1)
├── migrate_assignments_to_project_roles.py (Phase 1)
├── backfill_project_user_permissions.py   (Phase 1)
└── delete_legacy_workspaces.py            (Phase 2)
```

### Modified

```
egrm/hooks.py                              (Phases 1, 2 — boot_session, app_home, role_home_page)
egrm/egrm/doctype/grm_project/grm_project.json     (Phase 1 — 2 new fields)
egrm/egrm/doctype/grm_user_project_assignment/    (Phase 1 — role Link target swap, validate_creator_permissions, sync hook)
egrm/patches.txt                           (Phases 1, 2)
```

### Deleted

```
egrm/egrm/workspace/grm_administrator/     (Phase 2)
egrm/egrm/workspace/grm_project_manager/   (Phase 2)
egrm/egrm/workspace/grm_department_head/   (Phase 2)
egrm/egrm/workspace/grm_field_officer/     (Phase 2)
```

---

# Phase 1 — Schema + plumbing

### Task 1.1: Create the `GRM Duty` catalog DocType

**Files:**
- Create: `egrm/egrm/doctype/grm_duty/__init__.py` (empty)
- Create: `egrm/egrm/doctype/grm_duty/grm_duty.json`
- Create: `egrm/egrm/doctype/grm_duty/grm_duty.py`

- [ ] **Step 1: Scaffold**

```bash
cd /Users/victor/egrm/apps/egrm
mkdir -p egrm/egrm/doctype/grm_duty
touch egrm/egrm/doctype/grm_duty/__init__.py
```

- [ ] **Step 2: JSON**

`egrm/egrm/doctype/grm_duty/grm_duty.json`:

```json
{
  "actions": [],
  "allow_rename": 0,
  "autoname": "field:duty_name",
  "creation": "2026-04-25 00:00:00",
  "doctype": "DocType",
  "engine": "InnoDB",
  "field_order": ["duty_name", "label", "description", "lifecycle_phase", "icon"],
  "fields": [
    { "fieldname": "duty_name", "fieldtype": "Data", "label": "Duty", "reqd": 1, "unique": 1, "in_list_view": 1 },
    { "fieldname": "label", "fieldtype": "Data", "label": "Display Label", "reqd": 1, "in_list_view": 1 },
    { "fieldname": "description", "fieldtype": "Small Text", "label": "Description" },
    { "fieldname": "lifecycle_phase", "fieldtype": "Select", "label": "Lifecycle Phase",
      "options": "Intake\nTriage\nResolution\nFeedback\nOversight", "reqd": 1, "in_list_view": 1 },
    { "fieldname": "icon", "fieldtype": "Data", "label": "Icon (lucide name)" }
  ],
  "module": "EGRM",
  "name": "GRM Duty",
  "owner": "Administrator",
  "permissions": [
    { "create": 1, "delete": 1, "read": 1, "role": "System Manager", "write": 1 },
    { "read": 1, "role": "GRM Administrator" }
  ],
  "sort_field": "lifecycle_phase",
  "sort_order": "ASC",
  "track_changes": 1
}
```

- [ ] **Step 3: Controller**

`egrm/egrm/doctype/grm_duty/grm_duty.py`:

```python
from frappe.model.document import Document


class GRMDuty(Document):
    pass
```

- [ ] **Step 4: Migrate**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -5
```

- [ ] **Step 5: Smoke-test**

```bash
bench --site egrm.local execute "frappe.db.exists('DocType', 'GRM Duty')"
```

Expected: `'GRM Duty'`.

- [ ] **Step 6: Commit**

```bash
git add egrm/egrm/doctype/grm_duty/
git commit -m "feat(schema): Add GRM Duty catalog DocType"
```

---

### Task 1.2: Seed the 6 standard duties

**Files:**
- Create: `egrm/patches/v16_0/__init__.py` (if missing)
- Create: `egrm/patches/v16_0/seed_duty_catalog.py`
- Modify: `egrm/patches.txt`

- [ ] **Step 1: Patch directory**

```bash
mkdir -p egrm/patches/v16_0
[ -f egrm/patches/__init__.py ] || touch egrm/patches/__init__.py
[ -f egrm/patches/v16_0/__init__.py ] || touch egrm/patches/v16_0/__init__.py
```

- [ ] **Step 2: Seeder**

`egrm/patches/v16_0/seed_duty_catalog.py`:

```python
"""Seed the canonical 6 duties (WB GRM Customization Questionnaire § 4)."""

import frappe

DUTIES = [
    {"duty_name": "Intake", "label": "Intake", "lifecycle_phase": "Intake", "icon": "inbox",
     "description": "Create new GRM Issues. Combines Uptake and Data Entry from the WB template (digital-only)."},
    {"duty_name": "Review", "label": "Review", "lifecycle_phase": "Triage", "icon": "check-circle",
     "description": "Validate categorisation, eligibility, severity. Move issues from Submitted to Reviewed/Rejected."},
    {"duty_name": "Assignment", "label": "Assignment", "lifecycle_phase": "Triage", "icon": "users",
     "description": "Set or change the issue assignee, route to a department or admin level."},
    {"duty_name": "Investigate & Resolve", "label": "Investigate & Resolve", "lifecycle_phase": "Resolution", "icon": "search",
     "description": "Add comments, evidence, and propose a resolution. Submit the issue."},
    {"duty_name": "Feedback", "label": "Feedback", "lifecycle_phase": "Feedback", "icon": "message-square",
     "description": "Track citizen rating, manage the appeal flow, close the issue."},
    {"duty_name": "Supervise", "label": "Supervise", "lifecycle_phase": "Oversight", "icon": "bar-chart",
     "description": "Read all in-scope issues, force-reassign/close, view dashboards, manage user assignments within scope."},
]


def execute() -> None:
    print(f"Seeding {len(DUTIES)} duties into GRM Duty catalog...")
    for d in DUTIES:
        if frappe.db.exists("GRM Duty", d["duty_name"]):
            continue
        doc = frappe.new_doc("GRM Duty")
        doc.update(d)
        doc.flags.ignore_permissions = True
        doc.insert()
    frappe.db.commit()
```

- [ ] **Step 3: Register**

Append to `egrm/patches.txt` under `[post_model_sync]`:

```
egrm.patches.v16_0.seed_duty_catalog
```

- [ ] **Step 4: Run**

```bash
bench --site egrm.local migrate 2>&1 | grep "Seeding 6 duties" | tail -1
```

Expected: prints the seeding line.

- [ ] **Step 5: Verify**

```bash
bench --site egrm.local execute "import frappe; print(frappe.get_all('GRM Duty', pluck='duty_name'))"
```

Expected: list of 6 names.

- [ ] **Step 6: Commit**

```bash
git add egrm/patches/v16_0/seed_duty_catalog.py egrm/patches/__init__.py egrm/patches/v16_0/__init__.py egrm/patches.txt
git commit -m "feat(schema): Seed 6 canonical duties on migrate"
```

---

### Task 1.3: Create `GRM Project Role Duty` (child table)

**Files:**
- Create: `egrm/egrm/doctype/grm_project_role_duty/`

- [ ] **Step 1: Scaffold**

```bash
mkdir -p egrm/egrm/doctype/grm_project_role_duty
touch egrm/egrm/doctype/grm_project_role_duty/__init__.py
```

- [ ] **Step 2: JSON**

`egrm/egrm/doctype/grm_project_role_duty/grm_project_role_duty.json`:

```json
{
  "actions": [],
  "creation": "2026-04-25 00:00:00",
  "doctype": "DocType",
  "engine": "InnoDB",
  "field_order": ["duty"],
  "fields": [
    { "fieldname": "duty", "fieldtype": "Link", "label": "Duty", "options": "GRM Duty", "reqd": 1, "in_list_view": 1 }
  ],
  "istable": 1,
  "module": "EGRM",
  "name": "GRM Project Role Duty",
  "owner": "Administrator",
  "permissions": [],
  "sort_field": "modified",
  "sort_order": "DESC",
  "track_changes": 1
}
```

- [ ] **Step 3: Controller**

`egrm/egrm/doctype/grm_project_role_duty/grm_project_role_duty.py`:

```python
from frappe.model.document import Document


class GRMProjectRoleDuty(Document):
    pass
```

- [ ] **Step 4: Migrate + commit**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
git add egrm/egrm/doctype/grm_project_role_duty/
git commit -m "feat(schema): Add GRM Project Role Duty child table"
```

---

### Task 1.4: Create `GRM Project Role`

**Files:**
- Create: `egrm/egrm/doctype/grm_project_role/`

- [ ] **Step 1: Scaffold**

```bash
mkdir -p egrm/egrm/doctype/grm_project_role
touch egrm/egrm/doctype/grm_project_role/__init__.py
```

- [ ] **Step 2: JSON**

`egrm/egrm/doctype/grm_project_role/grm_project_role.json`:

```json
{
  "actions": [],
  "allow_rename": 1,
  "autoname": "format:{project}-{role_name}",
  "creation": "2026-04-25 00:00:00",
  "doctype": "DocType",
  "engine": "InnoDB",
  "field_order": [
    "role_name", "project", "admin_level",
    "section_break_duties", "duties",
    "section_break_meta", "description", "is_active"
  ],
  "fields": [
    { "fieldname": "role_name", "fieldtype": "Data", "label": "Role Name", "reqd": 1, "in_list_view": 1 },
    { "fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "GRM Project", "reqd": 1, "in_list_view": 1 },
    { "fieldname": "admin_level", "fieldtype": "Link", "label": "Administrative Level", "options": "GRM Administrative Level Type", "in_list_view": 1 },
    { "fieldname": "section_break_duties", "fieldtype": "Section Break", "label": "Duties" },
    { "fieldname": "duties", "fieldtype": "Table", "label": "Duties", "options": "GRM Project Role Duty", "reqd": 1 },
    { "fieldname": "section_break_meta", "fieldtype": "Section Break" },
    { "fieldname": "description", "fieldtype": "Small Text", "label": "Description" },
    { "fieldname": "is_active", "fieldtype": "Check", "label": "Is Active", "default": "1", "in_list_view": 1 }
  ],
  "module": "EGRM",
  "name": "GRM Project Role",
  "owner": "Administrator",
  "permissions": [
    { "create": 1, "delete": 1, "read": 1, "role": "System Manager", "write": 1 },
    { "create": 1, "read": 1, "role": "GRM Administrator", "write": 1 }
  ],
  "sort_field": "modified",
  "sort_order": "DESC",
  "track_changes": 1
}
```

- [ ] **Step 3: Controller**

`egrm/egrm/doctype/grm_project_role/grm_project_role.py`:

```python
import frappe
from frappe.model.document import Document


class GRMProjectRole(Document):
    def validate(self) -> None:
        self._validate_project_role_unique()
        self._validate_at_least_one_duty()

    def _validate_project_role_unique(self) -> None:
        existing = frappe.db.exists(
            "GRM Project Role",
            {"project": self.project, "role_name": self.role_name, "name": ["!=", self.name]},
        )
        if existing:
            frappe.throw(
                frappe._("A role named {0} already exists in project {1}").format(self.role_name, self.project)
            )

    def _validate_at_least_one_duty(self) -> None:
        if not self.duties:
            frappe.throw(frappe._("A Project Role must have at least one duty assigned."))


def get_role_duties(role: str) -> list[str]:
    """Return duty_name list for a Project Role; empty list for missing roles."""
    if not role or not frappe.db.exists("GRM Project Role", role):
        return []
    return frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": role},
        pluck="duty",
    )
```

- [ ] **Step 4: Migrate + smoke-test**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
bench --site egrm.local execute "frappe.db.exists('DocType','GRM Project Role')"
```

Expected: `'GRM Project Role'`.

- [ ] **Step 5: Commit**

```bash
git add egrm/egrm/doctype/grm_project_role/
git commit -m "feat(schema): Add GRM Project Role DocType"
```

---

### Task 1.5: Add 2 fields to `GRM Project` for wizard state

**Files:**
- Modify: `egrm/egrm/doctype/grm_project/grm_project.json`

- [ ] **Step 1: Append two fields**

Read the current `field_order` and `fields` arrays. Append:

```json
{ "fieldname": "section_setup_state", "fieldtype": "Section Break", "label": "Setup State", "collapsible": 1 },
{ "fieldname": "is_setup_complete", "fieldtype": "Check", "label": "Is Setup Complete", "default": "0", "read_only": 1, "in_list_view": 1 },
{ "fieldname": "current_setup_step", "fieldtype": "Int", "label": "Current Setup Step", "default": "1", "read_only": 1 }
```

Add their fieldnames to the end of `field_order`.

- [ ] **Step 2: Migrate**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

- [ ] **Step 3: Smoke-test**

```bash
bench --site egrm.local execute "import frappe; m = frappe.get_meta('GRM Project'); print('is_setup_complete:', any(f.fieldname == 'is_setup_complete' for f in m.fields))"
```

Expected: `is_setup_complete: True`.

- [ ] **Step 4: Commit**

```bash
git add egrm/egrm/doctype/grm_project/grm_project.json
git commit -m "feat(schema): Add wizard state fields to GRM Project"
```

---

### Task 1.6: Backfill default `GRM Project Role` rows for existing projects

**Files:**
- Create: `egrm/patches/v16_0/backfill_default_project_roles.py`
- Modify: `egrm/patches.txt`

- [ ] **Step 1: Patch**

`egrm/patches/v16_0/backfill_default_project_roles.py`:

```python
"""Create the 4 default Project Roles per existing project, mirroring the
canonical WB roles (GRM Administrator / Project Manager / Department Head /
Field Officer) with their default duty composition."""

import frappe


DEFAULT_ROLES = [
    {
        "role_name": "GRM Administrator",
        "duties": ["Intake", "Review", "Assignment", "Investigate & Resolve", "Feedback", "Supervise"],
        "description": "Full GRM authority within the project.",
    },
    {
        "role_name": "GRM Project Manager",
        "duties": ["Review", "Assignment", "Investigate & Resolve", "Feedback", "Supervise"],
        "description": "Manages the project's GRM operations, team, and configuration.",
    },
    {
        "role_name": "GRM Department Head",
        "duties": ["Review", "Assignment", "Investigate & Resolve", "Feedback"],
        "description": "Oversees the assigned department; routes and tracks issues.",
    },
    {
        "role_name": "GRM Field Officer",
        "duties": ["Intake", "Investigate & Resolve", "Feedback"],
        "description": "Logs and resolves grievances on the ground in their assigned region.",
    },
]


def execute() -> None:
    projects = frappe.get_all("GRM Project", pluck="name")
    print(f"Backfilling default Project Roles for {len(projects)} project(s)...")
    for project in projects:
        for spec in DEFAULT_ROLES:
            full_name = f"{project}-{spec['role_name']}"
            if frappe.db.exists("GRM Project Role", full_name):
                continue
            doc = frappe.new_doc("GRM Project Role")
            doc.role_name = spec["role_name"]
            doc.project = project
            doc.description = spec["description"]
            doc.is_active = 1
            for duty in spec["duties"]:
                if frappe.db.exists("GRM Duty", duty):
                    doc.append("duties", {"duty": duty})
            doc.flags.ignore_permissions = True
            doc.insert()
    frappe.db.commit()
```

- [ ] **Step 2: Register, migrate, verify**

Append to `egrm/patches.txt`:

```
egrm.patches.v16_0.backfill_default_project_roles
```

```bash
bench --site egrm.local migrate 2>&1 | grep "Backfilling default" | tail -1
bench --site egrm.local execute "import frappe; rows = frappe.db.sql('SELECT project, COUNT(*) c FROM \`tabGRM Project Role\` GROUP BY project', as_dict=True); print(rows)"
```

Expected: each project shows `c = 4`.

- [ ] **Step 3: Commit**

```bash
git add egrm/patches/v16_0/backfill_default_project_roles.py egrm/patches.txt
git commit -m "chore: Backfill default Project Roles per existing project"
```

---

### Task 1.7: Migrate `GRM User Project Assignment.role` to point at Project Role

**Files:**
- Modify: `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json`
- Modify: `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`
- Create: `egrm/patches/v16_0/migrate_assignments_to_project_roles.py`

- [ ] **Step 1: Update JSON role field**

Find the `role` field (currently `"options": "Role"` with a get_query for `GRM%` filter) and change to:

```json
{ "fieldname": "role", "fieldtype": "Link", "label": "Project Role",
  "options": "GRM Project Role", "reqd": 1,
  "get_query": "egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment.role_query" }
```

- [ ] **Step 2: Replace `get_query` helper in the controller**

In `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`, replace the existing `get_grm_roles` (or add alongside) a new project-aware role_query:

```python
@frappe.whitelist()
def role_query(doctype, txt, searchfield, start, page_len, filters):
    project = filters.get("project") if isinstance(filters, dict) else None
    if not project:
        return []
    return frappe.db.sql(
        f"""SELECT name, role_name FROM `tabGRM Project Role`
            WHERE project = %s AND is_active = 1 AND ({searchfield} LIKE %s OR role_name LIKE %s)
            ORDER BY role_name LIMIT %s, %s""",
        (project, f"%{txt}%", f"%{txt}%", start, page_len),
    )
```

- [ ] **Step 3: Migration patch**

`egrm/patches/v16_0/migrate_assignments_to_project_roles.py`:

```python
"""Repoint each GRM User Project Assignment.role from a Frappe Role string
(`GRM Field Officer`) to the matching Project Role (`<project>-GRM Field Officer`).
Run AFTER backfill_default_project_roles."""

import frappe


LEGACY = {
    "GRM Administrator", "GRM Project Manager", "GRM Department Head", "GRM Field Officer",
}


def execute() -> None:
    rows = frappe.db.sql(
        "SELECT name, project, role FROM `tabGRM User Project Assignment`",
        as_dict=True,
    )
    print(f"Migrating role values on {len(rows)} assignment(s)...")
    for r in rows:
        legacy = r.get("role") or ""
        if legacy not in LEGACY:
            continue  # already migrated or unrecognised — skip
        target = f"{r['project']}-{legacy}"
        if not frappe.db.exists("GRM Project Role", target):
            frappe.log_error(
                title="Project Role missing during migration",
                message=f"Assignment {r['name']}: expected {target}",
            )
            continue
        frappe.db.set_value("GRM User Project Assignment", r["name"], "role", target)
    frappe.db.commit()
```

- [ ] **Step 4: Register + migrate + verify**

Append to `egrm/patches.txt`:

```
egrm.patches.v16_0.migrate_assignments_to_project_roles
```

```bash
bench --site egrm.local migrate 2>&1 | grep "Migrating role" | tail -1
bench --site egrm.local execute "import frappe; print(frappe.db.sql('SELECT DISTINCT role FROM \`tabGRM User Project Assignment\` LIMIT 10'))"
```

Expected: roles look like `<project>-GRM Field Officer`.

- [ ] **Step 5: Commit**

```bash
git add egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py egrm/patches/v16_0/migrate_assignments_to_project_roles.py egrm/patches.txt
git commit -m "feat(schema): Migrate assignment.role to GRM Project Role"
```

---

### Task 1.7a: Seed the 6 duty-Frappe-Roles + Platform Administrator

**Files:**
- Create: `egrm/patches/v16_0/seed_grm_role_catalog.py`
- Modify: `egrm/patches.txt`

- [ ] **Step 1: Patch**

`egrm/patches/v16_0/seed_grm_role_catalog.py`:

```python
"""Create the 6 duty-named Frappe Roles + the GRM Platform Administrator role.
Idempotent. Safe to re-run."""

import frappe

NEW_ROLES = [
    "GRM Intake",
    "GRM Review",
    "GRM Assignment",
    "GRM Investigate & Resolve",
    "GRM Feedback",
    "GRM Supervise",
    "GRM Platform Administrator",
]


def execute() -> None:
    print(f"Seeding {len(NEW_ROLES)} GRM duty/platform roles...")
    for role_name in NEW_ROLES:
        if frappe.db.exists("Role", role_name):
            continue
        doc = frappe.new_doc("Role")
        doc.role_name = role_name
        doc.desk_access = 1
        doc.disabled = 0
        doc.flags.ignore_permissions = True
        doc.insert()
    frappe.db.commit()
```

- [ ] **Step 2: Register, run, verify**

Append to `egrm/patches.txt`:

```
egrm.patches.v16_0.seed_grm_role_catalog
```

```bash
bench --site egrm.local migrate 2>&1 | grep "Seeding 7 GRM" | tail -1
bench --site egrm.local execute "import frappe; print(sorted(r for r in frappe.get_all('Role', pluck='name') if r.startswith('GRM ')))"
```

Expected: list contains the 7 new roles.

- [ ] **Step 3: Commit**

```bash
git add egrm/patches/v16_0/seed_grm_role_catalog.py egrm/patches.txt
git commit -m "feat(roles): Create 6 duty-Frappe-Roles + GRM Platform Administrator"
```

---

### Task 1.7b: Rewrite doctype `permissions[]` to use duty-roles

The existing four legacy roles (`GRM Administrator/Project Manager/Department Head/Field Officer`) are referenced in every GRM doctype JSON. We rewrite each so each duty-role unlocks the actions defined in `ARCHITECTURE.md` § 6.1.

**Doctypes by category and permission template they receive:**

#### A. Transaction — `GRM Issue` (the only one in this category)

Edit-rights split per duty (full template in Step 1 below).

#### B. Setup lookups (Supervise can write/create; Platform Admin & System Manager full; everyone else read-only)

| Doctype | File path |
|---|---|
| `GRM Issue Category` | `egrm/egrm/doctype/grm_issue_category/grm_issue_category.json` |
| `GRM Issue Type` | `egrm/egrm/doctype/grm_issue_type/grm_issue_type.json` |
| `GRM Issue Status` | `egrm/egrm/doctype/grm_issue_status/grm_issue_status.json` |
| `GRM Issue Department` | `egrm/egrm/doctype/grm_issue_department/grm_issue_department.json` |
| `GRM Issue Age Group` | `egrm/egrm/doctype/grm_issue_age_group/grm_issue_age_group.json` |
| `GRM Issue Citizen Group` | `egrm/egrm/doctype/grm_issue_citizen_group/grm_issue_citizen_group.json` |
| `GRM Issue Escalation Reason` | `egrm/egrm/doctype/grm_issue_escalation_reason/grm_issue_escalation_reason.json` |
| `GRM Administrative Region` | `egrm/egrm/doctype/grm_administrative_region/grm_administrative_region.json` |
| `GRM Administrative Level Type` | `egrm/egrm/doctype/grm_administrative_level_type/grm_administrative_level_type.json` |
| `GRM Notification Template` | `egrm/egrm/doctype/grm_notification_template/grm_notification_template.json` |

#### C. Project + role configuration (Supervise read+write; Platform Admin & System Manager full; others read)

| Doctype | File path |
|---|---|
| `GRM Project` | `egrm/egrm/doctype/grm_project/grm_project.json` |
| `GRM Project Role` | `egrm/egrm/doctype/grm_project_role/grm_project_role.json` |

#### D. User + access management (Supervise create+read+write within scope; Platform Admin full)

| Doctype | File path |
|---|---|
| `GRM User Project Assignment` | `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json` |

#### E. Platform-only catalogs (System Manager + Platform Admin only — no project staff write)

| Doctype | File path |
|---|---|
| `GRM Duty` | `egrm/egrm/doctype/grm_duty/grm_duty.json` (Task 1.1 created with the right perms — verify and skip if already correct) |
| `GRM Administrative Level Type` (template list at platform-admin level too) | already in B; kept here as a note that PM-level Supervise can also edit since Admin Levels are project-scoped |
| `Android App Version` | `egrm/egrm/doctype/android_app_version/android_app_version.json` |
| `EGRM Settings` (Single) | `egrm/egrm/doctype/egrm_settings/egrm_settings.json` |

#### F. Child tables (no permissions of their own — inherit from parent)

`GRM Project Link`, `GRM Issue Attachment`, `GRM Issue Comment`, `GRM Issue Log`, `GRM Project Role Duty` — leave their `permissions[]` arrays empty as they are today.

#### Capability matrix (write-action perspective)

| Doctype | Intake | Review | Assignment | Investigate&Resolve | Feedback | Supervise | Platform Admin | System Manager |
|---|---|---|---|---|---|---|---|---|
| `GRM Issue` | Create | Write | Write | Write+Submit | Write | Write+Delete+Cancel+Amend | Write+Create+Delete | Full |
| Setup lookups (B) | – | – | – | – | – | Create+Write | Create+Write+Delete | Full |
| `GRM Project` (C) | – | – | – | – | – | Write | Write+Create+Delete | Full |
| `GRM Project Role` (C) | – | – | – | – | – | Write | Write+Create+Delete | Full |
| `GRM User Project Assignment` (D) | – | – | – | – | – | Create+Write (scoped) | Create+Write+Delete | Full |
| `GRM Duty` (E) | – | – | – | – | – | – | – | Full |
| `Android App Version` (E) | – | – | – | – | – | – | Create+Write+Delete | Full |
| `EGRM Settings` (E) | – | – | – | – | – | – | Write | Full |

Read access: every duty-role gets `read` on every doctype it interacts with (Categories etc. are needed for issue dropdowns even by Intake users). The Supervise role + Platform Admin get read on everything; System Manager bypasses.

- [ ] **Step 1: Update `GRM Issue` permissions**

Replace the `permissions[]` array in `egrm/egrm/doctype/grm_issue/grm_issue.json` with:

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "print": 1, "email": 1, "export": 1, "report": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "email": 1, "export": 1, "report": 1, "share": 1 },
  { "role": "GRM Intake", "read": 1, "create": 1, "print": 1, "report": 1 },
  { "role": "GRM Review", "read": 1, "write": 1, "print": 1, "report": 1 },
  { "role": "GRM Assignment", "read": 1, "write": 1, "print": 1, "report": 1 },
  { "role": "GRM Investigate & Resolve", "read": 1, "write": 1, "submit": 1, "print": 1, "report": 1 },
  { "role": "GRM Feedback", "read": 1, "write": 1, "print": 1, "report": 1 },
  { "role": "GRM Supervise", "read": 1, "write": 1, "delete": 1, "cancel": 1, "amend": 1, "print": 1, "email": 1, "export": 1, "report": 1, "share": 1 }
]
```

- [ ] **Step 2: Update lookup-doctype permissions (Category, Type, Status, Department, Age Group, Citizen Group)**

For each of these 6 lookup doctypes, replace `permissions[]` with the same template:

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Supervise", "read": 1, "write": 1, "create": 1, "print": 1, "report": 1, "export": 1 },
  { "role": "GRM Intake", "read": 1, "report": 1 },
  { "role": "GRM Review", "read": 1, "report": 1 },
  { "role": "GRM Assignment", "read": 1, "report": 1 },
  { "role": "GRM Investigate & Resolve", "read": 1, "report": 1 },
  { "role": "GRM Feedback", "read": 1, "report": 1 }
]
```

- [ ] **Step 3: Update `GRM Administrative Level Type`, `GRM Administrative Region`**

Same template as Step 2 (Supervise can write/create; everyone else read-only).

- [ ] **Step 4: Update `GRM User Project Assignment` permissions**

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Supervise", "read": 1, "write": 1, "create": 1, "print": 1, "report": 1 },
  { "role": "GRM Intake", "read": 1, "if_owner": 1 },
  { "role": "GRM Review", "read": 1, "if_owner": 1 },
  { "role": "GRM Assignment", "read": 1, "if_owner": 1 },
  { "role": "GRM Investigate & Resolve", "read": 1, "if_owner": 1 },
  { "role": "GRM Feedback", "read": 1, "if_owner": 1 }
]
```

- [ ] **Step 5: Update `GRM Project`, `GRM Notification Template`, `GRM Project Role` permissions**

For all three: System Manager + Platform Admin = full; Supervise = read+write; everyone else = read.

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Supervise", "read": 1, "write": 1, "print": 1, "report": 1 },
  { "role": "GRM Intake", "read": 1 },
  { "role": "GRM Review", "read": 1 },
  { "role": "GRM Assignment", "read": 1 },
  { "role": "GRM Investigate & Resolve", "read": 1 },
  { "role": "GRM Feedback", "read": 1 }
]
```

- [ ] **Step 5b: Update `GRM Issue Escalation Reason`**

Same template as Step 2 (lookup; Supervise create+write; everyone else read).

- [ ] **Step 5c: Update platform-only catalog permissions**

`GRM Duty` (`egrm/egrm/doctype/grm_duty/grm_duty.json` — already created in Task 1.1, but tighten to platform-only):

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "print": 1, "report": 1 },
  { "role": "GRM Intake", "read": 1 },
  { "role": "GRM Review", "read": 1 },
  { "role": "GRM Assignment", "read": 1 },
  { "role": "GRM Investigate & Resolve", "read": 1 },
  { "role": "GRM Feedback", "read": 1 },
  { "role": "GRM Supervise", "read": 1 }
]
```

(All staff need read access since the duty catalog is referenced by Project Role child rows; only System Manager edits the catalog.)

`Android App Version` (`egrm/egrm/doctype/android_app_version/android_app_version.json`):

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "report": 1, "export": 1, "share": 1 },
  { "role": "GRM Supervise", "read": 1 }
]
```

`EGRM Settings` (`egrm/egrm/doctype/egrm_settings/egrm_settings.json`):

```json
"permissions": [
  { "role": "System Manager", "read": 1, "write": 1, "print": 1 },
  { "role": "GRM Platform Administrator", "read": 1, "write": 1, "print": 1 }
]
```

- [ ] **Step 6: Migrate to apply the new permissions**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

- [ ] **Step 7: Sanity check the new permissions**

```bash
bench --site egrm.local execute "import frappe; m = frappe.get_meta('GRM Issue'); print(sorted(set(p.role for p in m.permissions)))"
```

Expected: includes the 6 duty-roles + Platform Administrator + System Manager. Should NOT include `GRM Field Officer` etc.

- [ ] **Step 8: Commit**

```bash
git add \
  egrm/egrm/doctype/grm_issue/grm_issue.json \
  egrm/egrm/doctype/grm_issue_category/grm_issue_category.json \
  egrm/egrm/doctype/grm_issue_type/grm_issue_type.json \
  egrm/egrm/doctype/grm_issue_status/grm_issue_status.json \
  egrm/egrm/doctype/grm_issue_department/grm_issue_department.json \
  egrm/egrm/doctype/grm_issue_age_group/grm_issue_age_group.json \
  egrm/egrm/doctype/grm_issue_citizen_group/grm_issue_citizen_group.json \
  egrm/egrm/doctype/grm_issue_escalation_reason/grm_issue_escalation_reason.json \
  egrm/egrm/doctype/grm_administrative_level_type/grm_administrative_level_type.json \
  egrm/egrm/doctype/grm_administrative_region/grm_administrative_region.json \
  egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json \
  egrm/egrm/doctype/grm_project/grm_project.json \
  egrm/egrm/doctype/grm_notification_template/grm_notification_template.json \
  egrm/egrm/doctype/grm_project_role/grm_project_role.json \
  egrm/egrm/doctype/grm_duty/grm_duty.json \
  egrm/egrm/doctype/android_app_version/android_app_version.json \
  egrm/egrm/doctype/egrm_settings/egrm_settings.json
git commit -m "feat(roles): Rewrite GRM doctype permissions[] to duty-keyed L1"
```

---

### Task 1.7c: Migrate users from legacy roles → duty-roles + drop legacy

**Files:**
- Modify: `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py` — replace `assign_role_to_user()` / `remove_role_from_user()` with duty-walking versions
- Create: `egrm/patches/v16_0/migrate_users_to_duty_roles.py`
- Create: `egrm/patches/v16_0/delete_legacy_grm_roles.py`
- Modify: `egrm/patches.txt`

- [ ] **Step 1: Replace role-sync helpers in the assignment controller**

In `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`, replace the existing `assign_role_to_user`, `remove_role_from_user`, `is_government_worker_role` (and any helpers that reference the four legacy role names) with:

```python
LEGACY_ROLES = {
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
}

GOVERNMENT_WORKER_DUTIES = {"Intake", "Investigate & Resolve"}


def _project_role_duties(project_role: str) -> list[str]:
    if not project_role or not frappe.db.exists("GRM Project Role", project_role):
        return []
    return frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": project_role},
        pluck="duty",
    )


def _frappe_role_for_duty(duty_name: str) -> str:
    """Convention: the Frappe Role is named exactly 'GRM <duty_name>'."""
    return f"GRM {duty_name}"


def _other_active_assignments_for_duty(user: str, duty: str, exclude_assignment: str | None = None) -> bool:
    """Does the user hold this duty via ANY other active assignment?"""
    role_target = _frappe_role_for_duty(duty)
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user,
            "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
            **({"name": ["!=", exclude_assignment]} if exclude_assignment else {}),
        },
        pluck="role",
    )
    for project_role in rows:
        if duty in _project_role_duties(project_role):
            return True
    return False


def is_government_worker_assignment(self) -> bool:
    """An assignment is gov-worker (needing activation) if any duty is in
    the activation-required set."""
    duties = set(_project_role_duties(self.role))
    return bool(duties & GOVERNMENT_WORKER_DUTIES) and bool(self.administrative_region or self.department)


def assign_role_to_user(self) -> None:
    """Grant each duty's matching Frappe Role on the user (idempotent)."""
    duties = _project_role_duties(self.role)
    if not duties:
        return
    user = frappe.get_doc("User", self.user)
    existing = {r.role for r in user.roles}
    changed = False
    for duty in duties:
        target = _frappe_role_for_duty(duty)
        if target not in existing and frappe.db.exists("Role", target):
            user.append("roles", {"role": target})
            changed = True
    if changed:
        user.flags.ignore_permissions = True
        user.save()


def remove_role_from_user(self) -> None:
    """Strip duty-roles from the user, but only those no other active
    assignment of theirs still requires."""
    duties = _project_role_duties(self.role)
    if not duties:
        return
    user = frappe.get_doc("User", self.user)
    keep = []
    removed = False
    for r in user.roles:
        if r.role in {_frappe_role_for_duty(d) for d in duties}:
            duty_name = r.role.removeprefix("GRM ")
            if _other_active_assignments_for_duty(self.user, duty_name, exclude_assignment=self.name):
                keep.append(r)
            else:
                removed = True
        else:
            keep.append(r)
    if removed:
        user.set("roles", [{"role": k.role} for k in keep])
        user.flags.ignore_permissions = True
        user.save()
```

Wire `assign_role_to_user` / `remove_role_from_user` into the existing `after_insert` / `on_update` / `on_trash` (replacing the legacy single-role logic). Also update `is_government_worker_role()` callsites to use `is_government_worker_assignment(self)`.

- [ ] **Step 2: Migration patch — backfill duty-roles for existing users, drop legacy roles**

`egrm/patches/v16_0/migrate_users_to_duty_roles.py`:

```python
"""For each active GRM User Project Assignment, grant the duty-Frappe-Roles
matching its (now-migrated) Project Role. Then strip the four legacy
Frappe Roles from every user. Idempotent."""

import frappe


LEGACY_ROLES = [
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
]


def execute() -> None:
    names = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        pluck="name",
    )
    print(f"Granting duty-roles for {len(names)} active assignment(s)...")
    for name in names:
        try:
            doc = frappe.get_doc("GRM User Project Assignment", name)
            doc.assign_role_to_user()
        except Exception as exc:
            frappe.log_error(title="duty-role migration failed", message=f"{name}: {exc}")

    print(f"Stripping {len(LEGACY_ROLES)} legacy roles from all users...")
    for legacy in LEGACY_ROLES:
        rows = frappe.get_all(
            "Has Role",
            filters={"role": legacy},
            fields=["name", "parent", "parenttype"],
        )
        for row in rows:
            if row.parenttype != "User":
                continue
            frappe.db.delete("Has Role", {"name": row.name})

    frappe.db.commit()
```

- [ ] **Step 3: Patch to drop the legacy Role records**

`egrm/patches/v16_0/delete_legacy_grm_roles.py`:

```python
"""Once no user references the four legacy GRM roles, delete the Role records."""

import frappe


LEGACY = [
    "GRM Administrator",
    "GRM Project Manager",
    "GRM Department Head",
    "GRM Field Officer",
]


def execute() -> None:
    for legacy in LEGACY:
        if not frappe.db.exists("Role", legacy):
            continue
        ref = frappe.db.exists("Has Role", {"role": legacy})
        if ref:
            frappe.log_error(
                title="Cannot drop legacy GRM role",
                message=f"{legacy} still referenced by Has Role row {ref}",
            )
            continue
        # Also check no doctype permissions still reference it (Task 1.7b should have removed them)
        perm = frappe.db.exists("DocPerm", {"role": legacy})
        if perm:
            frappe.log_error(
                title="Cannot drop legacy GRM role",
                message=f"{legacy} still referenced by DocPerm row {perm}",
            )
            continue
        frappe.delete_doc("Role", legacy, ignore_permissions=True, force=True)
        print(f"Deleted legacy role: {legacy}")
    frappe.db.commit()
```

- [ ] **Step 4: Register both patches and run**

Append to `egrm/patches.txt` (in order — migrate first, delete after):

```
egrm.patches.v16_0.migrate_users_to_duty_roles
egrm.patches.v16_0.delete_legacy_grm_roles
```

```bash
bench --site egrm.local migrate 2>&1 | grep -E "Granting duty|Stripping|Deleted legacy" | tail -10
```

- [ ] **Step 5: Verify**

```bash
bench --site egrm.local execute "import frappe; print('legacy roles still exist:', [r for r in ['GRM Administrator','GRM Project Manager','GRM Department Head','GRM Field Officer'] if frappe.db.exists('Role', r)])"
```

Expected: `[]` (empty list).

```bash
bench --site egrm.local execute "import frappe; print('admin user roles:', sorted(r.role for r in frappe.get_doc('User','grm-admin@egrm.test').roles if r.role.startswith('GRM ')))"
```

Expected: list of duty-roles (e.g. `['GRM Assignment', 'GRM Feedback', 'GRM Intake', 'GRM Investigate & Resolve', 'GRM Review', 'GRM Supervise']`).

- [ ] **Step 6: Commit**

```bash
git add egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py egrm/patches/v16_0/migrate_users_to_duty_roles.py egrm/patches/v16_0/delete_legacy_grm_roles.py egrm/patches.txt
git commit -m "feat(roles): Migrate users to duty-roles, drop 4 legacy roles"
```

---

### Task 1.7d: Add field-level enforcement to `GRM Issue.validate()`

L1 doctype permissions are doctype-wide. To enforce per-field rules ("only `GRM Review` can change `status`; only `GRM Assignment` can change `assignee`"), add a guard in the `GRM Issue` controller's `validate()`.

**Files:**
- Modify: `egrm/egrm/doctype/grm_issue/grm_issue.py`

- [ ] **Step 1: Add the helper + guard inside the `GRMIssue` class**

Insert (preferably near the top of the class, before `validate`):

```python
# Field → required duty mapping. A user changing the field must hold the
# duty for the issue's project (or be Supervise / Platform Admin / SM).
FIELD_DUTY_REQUIREMENTS = {
    "status": "Review",
    "category": "Review",
    "issue_type": "Review",
    "assignee": "Assignment",
    "resolution_text": "Investigate & Resolve",
    "resolved_by": "Investigate & Resolve",
    "resolution_date": "Investigate & Resolve",
    "resolution_days": "Investigate & Resolve",
    "resolution_agreement": "Investigate & Resolve",
    "rating": "Feedback",
    "appeal_submitted": "Feedback",
    "appeal_date": "Feedback",
}


def _user_has_duty(user: str, duty: str, project: str) -> bool:
    """True if the user has the named duty for this project (or bypass)."""
    if user in ("Administrator", "Guest"):
        return user == "Administrator"
    user_roles = set(frappe.get_roles(user))
    if user_roles & {"System Manager", "GRM Platform Administrator", "GRM Supervise"}:
        return True
    role_names = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user, "project": project, "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        pluck="role",
    )
    if not role_names:
        return False
    duty_rows = frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": ["in", role_names], "duty": duty},
        pluck="duty",
    )
    return bool(duty_rows)
```

Then in the `validate(self)` method, append a guard block early (after the existing `tracking_code` generation and `validate_project_entities`, but before status/date checks):

```python
def validate(self):
    # ... existing logic up through validate_project_entities() ...
    self._enforce_duty_field_constraints()
    # ... existing validate_dates() etc ...


def _enforce_duty_field_constraints(self) -> None:
    """For each restricted field, if it changed, verify the user holds the
    required duty for this issue's project."""
    if self.is_new():
        # Intake creates issues; field-level rules apply only to updates.
        # We still gate creation via L1 doctype permission (GRM Intake → create).
        return
    user = frappe.session.user
    for field, duty in FIELD_DUTY_REQUIREMENTS.items():
        if not self.has_value_changed(field):
            continue
        if _user_has_duty(user, duty, self.project):
            continue
        frappe.throw(
            frappe._("You need the {0} duty to change {1}.").format(duty, field),
            frappe.PermissionError,
        )
```

- [ ] **Step 2: Restart + smoke-test**

```bash
bench --site egrm.local clear-cache
bench --site egrm.local execute "from egrm.egrm.doctype.grm_issue.grm_issue import _user_has_duty; print('helper importable')"
```

Expected: `helper importable`.

- [ ] **Step 3: Commit**

```bash
git add egrm/egrm/doctype/grm_issue/grm_issue.py
git commit -m "feat(perms): Field-level duty enforcement in GRM Issue.validate()"
```

---

### Task 1.7e: Update default Project Roles to use duty names directly

The default 4 Project Roles seeded in Task 1.6 already define `duties: [<list of duty_name>]`. After the legacy roles are gone, the names of the default Project Roles can stay as-is (`GRM Administrator/PM/DH/FO`) — they're now just labels for opinionated bundles of duties, not Frappe Roles. No code change needed; this task only verifies and documents.

- [ ] **Step 1: Verify default Project Roles still exist with duties**

```bash
bench --site egrm.local execute "import frappe; rows = frappe.get_all('GRM Project Role', fields=['name','project','role_name'], order_by='project, role_name'); print('\\n'.join(f\"  {r.project}: {r.role_name}\" for r in rows[:20]))"
```

Expected: 4 roles per project.

- [ ] **Step 2: Verify duty composition**

```bash
bench --site egrm.local execute "import frappe; sample = frappe.get_all('GRM Project Role', limit_page_length=1, pluck='name')[0]; print(sample, '→', frappe.get_all('GRM Project Role Duty', filters={'parent': sample}, pluck='duty'))"
```

Expected: a list of duty names.

- [ ] **Step 3: Commit (docs only — README note)**

If desired, append a paragraph to README explaining the role rename. Otherwise skip.

```bash
# (no code change — verification only)
```

---

### Task 1.8: Add `User Permission` auto-sync helpers

**Files:**
- Create: `egrm/utils/user_permissions.py`
- Modify: `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`

- [ ] **Step 1: Helper module**

`egrm/utils/user_permissions.py`:

```python
"""Keep User Permission rows in sync with GRM User Project Assignment.

Frappe's User Permission doctype scopes record-level access natively: a row
(user, allow="GRM Project", for_value=<project>, apply_to_all_doctypes=1)
auto-filters every doctype that links to GRM Project — including GRM Issue,
Issue Category, Administrative Region, Issue Department.
"""

import frappe


PROJECT_DOCTYPE = "GRM Project"


def _is_active(assignment) -> bool:
    if not getattr(assignment, "is_active", 0):
        return False
    status = getattr(assignment, "activation_status", None)
    return status in (None, "", "Activated")


def grant_project_access(user: str, project: str) -> None:
    if not user or user in ("Administrator", "Guest") or not project:
        return
    if frappe.db.exists(
        "User Permission",
        {"user": user, "allow": PROJECT_DOCTYPE, "for_value": project},
    ):
        return
    doc = frappe.new_doc("User Permission")
    doc.user = user
    doc.allow = PROJECT_DOCTYPE
    doc.for_value = project
    doc.apply_to_all_doctypes = 1
    doc.flags.ignore_permissions = True
    doc.insert()


def revoke_project_access(user: str, project: str, exclude_assignment: str | None = None) -> None:
    if not user or not project:
        return
    filters = {
        "user": user, "project": project, "is_active": 1,
        "activation_status": ["in", ("Activated", "")],
    }
    if exclude_assignment:
        filters["name"] = ["!=", exclude_assignment]
    if frappe.db.exists("GRM User Project Assignment", filters):
        return
    rows = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": PROJECT_DOCTYPE, "for_value": project},
        pluck="name",
    )
    for name in rows:
        frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)


def sync_assignment(assignment) -> None:
    if _is_active(assignment):
        grant_project_access(assignment.user, assignment.project)
    else:
        revoke_project_access(
            assignment.user, assignment.project, exclude_assignment=assignment.name,
        )
```

- [ ] **Step 2: Wire into the assignment doctype**

In `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py` add the import:

```python
from egrm.utils.user_permissions import revoke_project_access, sync_assignment
```

Append to `after_insert`, `on_update`, and `on_trash`:

```python
def after_insert(self):
    # ... existing logic ...
    sync_assignment(self)


def on_update(self):
    # ... existing logic ...
    sync_assignment(self)


def on_trash(self):
    # ... existing logic ...
    revoke_project_access(self.user, self.project, exclude_assignment=self.name)
```

- [ ] **Step 3: Smoke-test imports**

```bash
bench --site egrm.local clear-cache
bench --site egrm.local execute "from egrm.utils.user_permissions import grant_project_access, revoke_project_access, sync_assignment; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add egrm/utils/user_permissions.py egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py
git commit -m "feat(perms): Auto-sync User Permission with GRM User Project Assignment"
```

---

### Task 1.9: Backfill `User Permission` for existing assignments

**Files:**
- Create: `egrm/patches/v16_0/backfill_project_user_permissions.py`

- [ ] **Step 1: Patch**

`egrm/patches/v16_0/backfill_project_user_permissions.py`:

```python
"""Backfill User Permission rows for active GRM User Project Assignments. Idempotent."""

import frappe

from egrm.utils.user_permissions import sync_assignment


def execute() -> None:
    names = frappe.get_all(
        "GRM User Project Assignment",
        filters={"is_active": 1},
        pluck="name",
    )
    print(f"Backfilling User Permission for {len(names)} assignment(s)...")
    for name in names:
        try:
            sync_assignment(frappe.get_doc("GRM User Project Assignment", name))
        except Exception as exc:
            frappe.log_error(title="UP backfill failed", message=f"{name}: {exc}")
    frappe.db.commit()
```

- [ ] **Step 2: Register + migrate + commit**

Append to `egrm/patches.txt`:

```
egrm.patches.v16_0.backfill_project_user_permissions
```

```bash
bench --site egrm.local migrate 2>&1 | grep "Backfilling User Permission" | tail -1
git add egrm/patches/v16_0/backfill_project_user_permissions.py egrm/patches.txt
git commit -m "chore: Backfill User Permission rows for existing assignments"
```

---

### Task 1.10: `validate_creator_permissions` guard

**Files:**
- Modify: `egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`

- [ ] **Step 1: Add the method**

Inside the `GRMUserProjectAssignment` class:

```python
def validate_creator_permissions(self):
    """Block PM-tier users from assigning users to projects they don't manage.

    System Manager, GRM Administrator (Frappe role), and the Administrator user
    bypass this check. Anyone else creating or modifying an assignment must
    already hold an active Project Manager-tier role for the same project.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    creator_roles = set(frappe.get_roles(user))
    if creator_roles & {"System Manager", "GRM Administrator"}:
        return
    has_pm = frappe.db.exists(
        "GRM User Project Assignment",
        {
            "user": user, "project": self.project, "is_active": 1,
            "role": ["like", f"{self.project}-GRM Project Manager%"],
        },
    )
    if not has_pm:
        frappe.throw(
            frappe._("You can only assign users to projects where you are an active Project Manager."),
            frappe.PermissionError,
        )
```

In `validate()`, add as the first call:

```python
def validate(self):
    self.validate_creator_permissions()
    # ... existing validations ...
```

- [ ] **Step 2: Commit**

```bash
git add egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py
git commit -m "feat(perms): PM can only create assignments in projects they manage"
```

---

### Task 1.11: `boot_session` hook injecting `frappe.boot.egrm`

**Files:**
- Create: `egrm/utils/boot.py`
- Modify: `egrm/hooks.py`

- [ ] **Step 1: Helper**

`egrm/utils/boot.py`:

```python
"""boot_session hook — populate frappe.boot.egrm with per-user duty data so
the Workspace JSON's `display_depends_on` predicates can evaluate them
client-side without a round-trip."""

import frappe


PLATFORM_ROLES = {"System Manager", "GRM Platform Administrator"}


def boot_session(bootinfo) -> None:
    user = frappe.session.user
    if user in ("Guest", "", None):
        bootinfo.egrm = {
            "active_project": None,
            "duties": [],
            "is_platform_admin": False,
            "available_projects": [],
        }
        return

    available = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "is_active": 1, "activation_status": ["in", ("Activated", "")]},
        fields=["project"],
        distinct=True,
    )
    available_projects = sorted({a.project for a in available})

    # Active project = user.default_project if set and accessible, else first available.
    user_default = frappe.db.get_value("User", user, "default_project") if frappe.get_meta("User").has_field("default_project") else None
    active = user_default if user_default in available_projects else (available_projects[0] if available_projects else None)

    duties = _get_duties(user, active) if active else []

    bootinfo.egrm = {
        "active_project": active,
        "duties": duties,
        "is_platform_admin": bool(set(frappe.get_roles(user)) & PLATFORM_ROLES),
        "available_projects": available_projects,
    }


def _get_duties(user: str, project: str) -> list[str]:
    role_names = frappe.get_all(
        "GRM User Project Assignment",
        filters={
            "user": user, "project": project, "is_active": 1,
            "activation_status": ["in", ("Activated", "")],
        },
        pluck="role",
    )
    if not role_names:
        return []
    return sorted(set(frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": ["in", role_names]},
        pluck="duty",
    )))
```

- [ ] **Step 2: Register**

In `egrm/hooks.py`, add:

```python
boot_session = "egrm.utils.boot.boot_session"
```

- [ ] **Step 3: Restart bench + verify**

```bash
PATH="/Users/victor/.nvm/versions/node/v24.14.0/bin:$PATH" pkill -f "honcho start" 2>/dev/null; sleep 2
PATH="/Users/victor/.nvm/versions/node/v24.14.0/bin:$PATH" nohup bench start > /tmp/egrm-bench/bench-v16.log 2>&1 &
sleep 12
curl -s -c /tmp/c.txt -b /tmp/c.txt -X POST http://egrm.local:8000/api/method/login -d "usr=Administrator&pwd=frappe" > /dev/null
curl -s -b /tmp/c.txt "http://egrm.local:8000/api/method/frappe.boot.get_bootinfo" | python3 -c "import sys, json; b = json.load(sys.stdin)['message']; print(json.dumps(b.get('egrm'), indent=2))"
```

Expected: a JSON object with the four egrm keys.

- [ ] **Step 4: Commit + tag**

```bash
git add egrm/utils/boot.py egrm/hooks.py
git commit -m "feat(boot): Inject frappe.boot.egrm with per-user duty payload"
git tag phase-1-schema
```

---

# Phase 2 — Workspace consolidation

### Task 2.1: Author the unified `egrm` workspace

**Files:**
- Create: `egrm/egrm/workspace/egrm/__init__.py`
- Create: `egrm/egrm/workspace/egrm/egrm.json`

- [ ] **Step 1: Scaffold**

```bash
mkdir -p egrm/egrm/workspace/egrm
touch egrm/egrm/workspace/egrm/__init__.py
```

- [ ] **Step 2: JSON**

`egrm/egrm/workspace/egrm/egrm.json`:

```json
{
  "app": "egrm",
  "charts": [],
  "content": "[{\"id\":\"sec-intake\",\"type\":\"card\",\"data\":{\"card_name\":\"Intake\",\"col\":4}},{\"id\":\"sec-triage\",\"type\":\"card\",\"data\":{\"card_name\":\"Triage\",\"col\":4}},{\"id\":\"sec-resolution\",\"type\":\"card\",\"data\":{\"card_name\":\"Resolution\",\"col\":4}},{\"id\":\"sec-feedback\",\"type\":\"card\",\"data\":{\"card_name\":\"Feedback\",\"col\":4}},{\"id\":\"sec-oversight\",\"type\":\"card\",\"data\":{\"card_name\":\"Oversight\",\"col\":4}}]",
  "creation": "2026-04-25 00:00:00",
  "doctype": "Workspace",
  "for_user": "",
  "icon": "grievance",
  "is_hidden": 0,
  "label": "eGRM",
  "links": [
    { "label": "Intake", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "Log a Grievance", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Intake')" },
    { "label": "Drafts", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "filters": "[[\"GRM Issue\",\"docstatus\",\"=\",0]]",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Intake')" },

    { "label": "Triage", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "Pending Review", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Review')" },
    { "label": "Ready to Assign", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Assignment')" },

    { "label": "Resolution", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "My Cases", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "filters": "[[\"GRM Issue\",\"assignee\",\"=\",\"current_user\"]]",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Investigate & Resolve')" },
    { "label": "All Cases in Scope", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Investigate & Resolve')" },

    { "label": "Feedback", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "Awaiting Feedback", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Feedback')" },
    { "label": "Appeals", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "filters": "[[\"GRM Issue\",\"appeal_submitted\",\"=\",1]]",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Feedback')" },

    { "label": "Oversight", "link_count": 3, "link_type": "DocType", "type": "Card Break" },
    { "label": "Project Health", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Supervise')" },
    { "label": "Escalations", "link_to": "GRM Issue", "link_type": "DocType", "type": "Link",
      "filters": "[[\"GRM Issue\",\"escalate_flag\",\"=\",1]]",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Supervise')" },
    { "label": "Team", "link_to": "/desk/grm-users", "link_type": "URL", "type": "Link",
      "display_depends_on": "eval:frappe.boot.egrm && frappe.boot.egrm.duties.includes('Supervise')" }
  ],
  "modified": "2026-04-25 00:00:00",
  "modified_by": "Administrator",
  "module": "EGRM",
  "name": "eGRM",
  "owner": "Administrator",
  "public": 1,
  "roles": [
    { "role": "GRM Administrator" }, { "role": "GRM Project Manager" },
    { "role": "GRM Department Head" }, { "role": "GRM Field Officer" },
    { "role": "System Manager" }
  ],
  "sequence_id": 1.0,
  "title": "eGRM",
  "type": "Workspace"
}
```

- [ ] **Step 3: Migrate + visual diff against XD prototype's eGRM workspace screen**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

Visit `/desk/egrm` as Administrator. Compare against the XD prototype.

- [ ] **Step 4: Commit**

```bash
git add egrm/egrm/workspace/egrm/
git commit -m "feat(workspace): Single duty-driven eGRM workspace"
```

---

### Task 2.2: Author the Platform workspace

**Files:**
- Create: `egrm/egrm/workspace/egrm_platform/__init__.py`
- Create: `egrm/egrm/workspace/egrm_platform/egrm_platform.json`

- [ ] **Step 1: Scaffold + JSON**

```bash
mkdir -p egrm/egrm/workspace/egrm_platform
touch egrm/egrm/workspace/egrm_platform/__init__.py
```

`egrm/egrm/workspace/egrm_platform/egrm_platform.json`:

```json
{
  "app": "egrm",
  "charts": [],
  "content": "[{\"id\":\"sec-projects\",\"type\":\"card\",\"data\":{\"card_name\":\"Projects\",\"col\":4}},{\"id\":\"sec-users\",\"type\":\"card\",\"data\":{\"card_name\":\"Users & Access\",\"col\":4}},{\"id\":\"sec-system\",\"type\":\"card\",\"data\":{\"card_name\":\"System\",\"col\":4}}]",
  "creation": "2026-04-25 00:00:00",
  "doctype": "Workspace",
  "icon": "shield",
  "is_hidden": 0,
  "label": "Platform",
  "links": [
    { "label": "Projects", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "All Projects", "link_to": "GRM Project", "link_type": "DocType", "type": "Link" },
    { "label": "Onboard New Project", "link_to": "/desk/grm-project-wizard", "link_type": "URL", "type": "Link" },
    { "label": "Users & Access", "link_count": 2, "link_type": "DocType", "type": "Card Break" },
    { "label": "Users by Project", "link_to": "/desk/grm-users", "link_type": "URL", "type": "Link" },
    { "label": "Frappe Users (raw)", "link_to": "User", "link_type": "DocType", "type": "Link" },
    { "label": "System", "link_count": 3, "link_type": "DocType", "type": "Card Break" },
    { "label": "Administrative Level Types", "link_to": "GRM Administrative Level Type", "link_type": "DocType", "type": "Link" },
    { "label": "Android App Versions", "link_to": "Android App Version", "link_type": "DocType", "type": "Link" },
    { "label": "Duties Catalog", "link_to": "GRM Duty", "link_type": "DocType", "type": "Link" }
  ],
  "modified": "2026-04-25 00:00:00",
  "modified_by": "Administrator",
  "module": "EGRM",
  "name": "Platform",
  "owner": "Administrator",
  "public": 1,
  "roles": [
    { "role": "System Manager" }, { "role": "GRM Platform Administrator" }
  ],
  "sequence_id": 2.0,
  "title": "Platform",
  "type": "Workspace"
}
```

- [ ] **Step 2: Migrate + visual diff against XD admin/platform screens**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

Visit `/desk/platform` as Administrator. Compare against XD.

- [ ] **Step 3: Commit**

```bash
git add egrm/egrm/workspace/egrm_platform/
git commit -m "feat(workspace): Add Platform workspace for system admins"
```

---

### Task 2.3: Update `hooks.py` for unified routing

**Files:**
- Modify: `egrm/hooks.py`

- [ ] **Step 1: Update `app_home` and `role_home_page`**

```python
app_home = "/desk/egrm"

role_home_page = {
    "System Manager": "egrm",
    "GRM Platform Administrator": "platform",
    "GRM Administrator": "egrm",
    "GRM Project Manager": "egrm",
    "GRM Department Head": "egrm",
    "GRM Field Officer": "egrm",
}
```

- [ ] **Step 2: Update `add_to_apps_screen` route**

```python
add_to_apps_screen = [
    {
        "name": app_name, "title": app_title, "route": "/desk/egrm",
        "logo": "/assets/egrm/images/egrm-logo.svg",
        "has_permission": "egrm.api.app_permission.check_app_permission",
    }
]
```

- [ ] **Step 3: Restart + verify**

```bash
PATH="/Users/victor/.nvm/versions/node/v24.14.0/bin:$PATH" pkill -f "honcho start" 2>/dev/null; sleep 2
PATH="/Users/victor/.nvm/versions/node/v24.14.0/bin:$PATH" nohup bench start > /tmp/egrm-bench/bench-v16.log 2>&1 &
sleep 12
curl -sI http://egrm.local:8000/app | head -3
```

Expected: 301 redirect to `/desk/egrm` (or `/login?redirect-to=/desk/egrm`).

- [ ] **Step 4: Commit**

```bash
git add egrm/hooks.py
git commit -m "feat(workspace): Land all GRM staff on /desk/egrm by default"
```

---

### Task 2.4: Delete the four legacy workspaces

**Files:**
- Create: `egrm/patches/v16_0/delete_legacy_workspaces.py`
- Delete: 4 directories

- [ ] **Step 1: Patch**

`egrm/patches/v16_0/delete_legacy_workspaces.py`:

```python
import frappe

LEGACY = ["GRM Administrator", "GRM Project Manager", "GRM Department Head", "GRM Field Officer"]


def execute() -> None:
    for ws in LEGACY:
        if frappe.db.exists("Workspace", ws):
            frappe.delete_doc("Workspace", ws, ignore_permissions=True, force=True)
            print(f"Deleted legacy workspace: {ws}")
    frappe.db.commit()
```

- [ ] **Step 2: Register, delete folders, migrate, verify**

Append to `egrm/patches.txt`:

```
egrm.patches.v16_0.delete_legacy_workspaces
```

```bash
rm -rf egrm/egrm/workspace/grm_administrator egrm/egrm/workspace/grm_project_manager egrm/egrm/workspace/grm_department_head egrm/egrm/workspace/grm_field_officer
bench --site egrm.local migrate 2>&1 | grep -E "Deleted legacy|Removing orphan" | tail -10
bench --site egrm.local execute "import frappe; print(frappe.get_all('Workspace', filters={'module':'EGRM'}, pluck='name'))"
```

Expected: only `eGRM` and `Platform`.

- [ ] **Step 3: Commit + tag**

```bash
git add -A egrm/egrm/workspace egrm/patches/v16_0/delete_legacy_workspaces.py egrm/patches.txt
git commit -m "chore(workspace): Remove 4 legacy role-workspaces"
git tag phase-2-workspace
```

---

# Phase 3 — Project Setup wizard + Users page

### Task 3.1: Scaffold `grm-project-wizard` desk page

**Files:**
- Create: `egrm/page/grm_project_wizard/__init__.py` (empty)
- Create: `egrm/page/grm_project_wizard/grm_project_wizard.json`
- Create: `egrm/page/grm_project_wizard/grm_project_wizard.js`
- Create: `egrm/page/grm_project_wizard/grm_project_wizard.py`

- [ ] **Step 1: Scaffold**

```bash
mkdir -p egrm/page/grm_project_wizard
touch egrm/page/grm_project_wizard/__init__.py
```

- [ ] **Step 2: Page JSON**

`egrm/page/grm_project_wizard/grm_project_wizard.json`:

```json
{
  "creation": "2026-04-25 00:00:00",
  "doctype": "Page",
  "icon": "settings",
  "module": "EGRM",
  "name": "grm-project-wizard",
  "owner": "Administrator",
  "page_name": "grm-project-wizard",
  "roles": [
    { "role": "System Manager" },
    { "role": "GRM Platform Administrator" },
    { "role": "GRM Administrator" }
  ],
  "standard": "Yes",
  "title": "Project Setup Wizard"
}
```

- [ ] **Step 3: Server helper**

`egrm/page/grm_project_wizard/grm_project_wizard.py`:

```python
import frappe


@frappe.whitelist()
def activate_project(project: str) -> dict:
    """Validate setup completeness and mark the project active."""
    doc = frappe.get_doc("GRM Project", project)
    issues: list[str] = []

    if not frappe.db.exists("GRM Administrative Level Type", {"project": project}):
        issues.append("No administrative levels defined.")
    if not frappe.db.exists("GRM Project Role", {"project": project, "is_active": 1}):
        issues.append("No active Project Roles defined.")

    if issues:
        frappe.throw("\n".join(issues))

    doc.is_setup_complete = 1
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"ok": True, "project": project}
```

- [ ] **Step 4: Page entry script — shell only (steps in subsequent tasks)**

`egrm/page/grm_project_wizard/grm_project_wizard.js`:

```javascript
frappe.pages["grm-project-wizard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Setup Wizard"),
        single_column: true,
    });
    new GRMProjectWizard(page);
};

class GRMProjectWizard {
    constructor(page) {
        this.page = page;
        this.project_name = frappe.utils.get_url_arg("project");
        this.current_step = 1;
        this.total_steps = 12;
        this.render_shell();
        this.load_project();
    }

    render_shell() {
        $(this.page.body).html(`
          <div class="grm-wizard">
            <div class="grm-wizard-header">
              <div id="grm-stepper" class="grm-stepper"></div>
              <h2 id="grm-step-title"></h2>
            </div>
            <div id="grm-step-body" class="grm-wizard-body"></div>
            <div class="grm-wizard-footer">
              <button class="btn btn-default" id="grm-prev">${__("Back")}</button>
              <button class="btn btn-primary" id="grm-next">${__("Continue")}</button>
            </div>
          </div>`);
        $("#grm-prev").on("click", () => this.goto_step(this.current_step - 1));
        $("#grm-next").on("click", () => this.advance());
    }

    async load_project() {
        if (this.project_name) {
            this.project = await frappe.db.get_doc("GRM Project", this.project_name);
            this.current_step = this.project.current_setup_step || 1;
        } else {
            this.project = null;  // step 1 will create
        }
        this.render_step();
    }

    step_title(n) {
        const titles = ["",
            "Project Information", "Uptake Notes", "Administrative Levels",
            "Project Roles", "Issue Categories & Routing", "Issue Types",
            "Issue Statuses", "Departments", "SLAs", "Citizen Lookups",
            "Notification Templates", "Activate"];
        return `${n}. ${titles[n]}`;
    }

    render_step() {
        $("#grm-step-title").text(this.step_title(this.current_step));
        this._render_stepper();
        // Step components added in Tasks 3.2–3.13.
    }

    _render_stepper() {
        const $s = $("#grm-stepper").empty();
        for (let i = 1; i <= this.total_steps; i++) {
            const cls = i < this.current_step ? "done" : i === this.current_step ? "active" : "pending";
            $s.append(`<div class="grm-step ${cls}">${i}</div>`);
        }
    }

    async advance() { /* delegates to step's save() — wired by step tasks */ }
    goto_step(n) { /* persists current_setup_step + re-renders — wired in step tasks */ }
}
```

- [ ] **Step 5: Migrate + visit**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

Visit `/desk/grm-project-wizard`. Expected: shell renders.

- [ ] **Step 6: Visual diff against the XD wizard's first screen**

- [ ] **Step 7: Commit**

```bash
git add egrm/page/grm_project_wizard/
git commit -m "feat(wizard): Scaffold Project Setup Wizard custom page"
```

---

### Tasks 3.2 — 3.13: Implement the 12 wizard steps

Each step is a separate task, ~3 hours each, following the pattern below. **Every step writes to existing doctypes** — no new schema.

For each step:
- [ ] **Sub-step a**: Open the WB Customization Questionnaire to the matching section. List the fields and validation hints.
- [ ] **Sub-step b**: Open the XD prototype to the matching screen. Record field order, labels, primary action.
- [ ] **Sub-step c**: Implement the step's component class in the wizard JS. Pattern:

```javascript
class GRMWizardStepN<Name> {
    constructor($body, project, wizard) { this.$body = $body; this.project = project; this.wizard = wizard; this.render(); }
    render() { /* form HTML targeting existing doctype rows */ }
    async save() { /* persist via frappe.db.set_value or db.insert; return true on success */ }
}
```

- [ ] **Sub-step d**: Wire it into the wizard's `step_class()` map.
- [ ] **Sub-step e**: `bench build --app egrm`.
- [ ] **Sub-step f**: Walk through the step end-to-end. Save persists. Reload resumes.
- [ ] **Sub-step g**: Visual diff against XD.
- [ ] **Sub-step h**: Commit `feat(wizard): Step N — <title>`.

| # | Step | What it writes to (existing doctypes) |
|---|---|---|
| 1 | Project Information | `GRM Project` direct fields (creates a new project if `project` URL arg is missing) |
| 2 | Uptake Notes | `GRM Project.description` (free text — uptake is operational, not schema) |
| 3 | Administrative Levels | Creates/edits `GRM Administrative Level Type` rows (`level_name`, `level_order`, `acknowledgment_days`, `resolution_days`, `auto_escalate`) |
| 4 | Project Roles | Creates `GRM Project Role` rows + `GRM Project Role Duty` children (the only NEW schema in the wizard, scaffolded in Phase 1) |
| 5 | Issue Categories & Routing | Creates `GRM Issue Category` rows; sets `assigned_department`, `assigned_appeal_department`, `assigned_escalation_department`; adds `grm_project_link` rows |
| 6 | Issue Types | Creates `GRM Issue Type` rows + `grm_project_link` |
| 7 | Issue Statuses | Creates `GRM Issue Status` rows with `initial_status`/`final_status`/`open_status`/`rejected_status` flags + `grm_project_link` |
| 8 | Departments | Creates `GRM Issue Department` rows with `head` (Link → User) + `grm_project_link` |
| 9 | SLAs | Edits `GRM Administrative Level Type.acknowledgment_days/resolution_days/reminder_before_days/auto_escalate` for each level |
| 10 | Citizen Lookups | Creates `GRM Issue Age Group` and `GRM Issue Citizen Group` rows + `grm_project_link` |
| 11 | Notification Templates | Selects/creates `GRM Notification Template` rows; assigns to `GRM Project.{receipt,acknowledgment,...}_template` fields |
| 12 | Activate | Calls `egrm.page.grm_project_wizard.grm_project_wizard.activate_project(project)` which validates and flips `is_setup_complete=1` |

---

### Task 3.14: Phase 3 wizard verification

- [ ] **Step 1: Onboard a new project end-to-end**

Visit `/desk/grm-project-wizard` (no `?project=` arg). Walk through all 12 steps.

- [ ] **Step 2: Verify state**

```bash
bench --site egrm.local execute "import frappe; doc = frappe.get_doc('GRM Project', '<your-test-project>'); print({'levels': frappe.db.count('GRM Administrative Level Type', {'project': doc.name}), 'roles': frappe.db.count('GRM Project Role', {'project': doc.name}), 'is_setup_complete': doc.is_setup_complete})"
```

Expected: levels > 0, roles > 0, is_setup_complete = 1.

- [ ] **Step 3: Commit + tag**

```bash
git tag phase-3-wizard
```

---

### Task 3.15: Scaffold `grm-users` desk page

**Files:**
- Create: `egrm/page/grm_users/`

- [ ] **Step 1: Scaffold + page JSON**

```bash
mkdir -p egrm/page/grm_users
touch egrm/page/grm_users/__init__.py
```

`egrm/page/grm_users/grm_users.json`:

```json
{
  "creation": "2026-04-25 00:00:00",
  "doctype": "Page",
  "icon": "users",
  "module": "EGRM",
  "name": "grm-users",
  "owner": "Administrator",
  "page_name": "grm-users",
  "roles": [
    { "role": "System Manager" },
    { "role": "GRM Platform Administrator" },
    { "role": "GRM Administrator" },
    { "role": "GRM Project Manager" }
  ],
  "standard": "Yes",
  "title": "Users by Project"
}
```

- [ ] **Step 2: Server helper**

`egrm/page/grm_users/grm_users.py`:

```python
import frappe


@frappe.whitelist()
def list_users_with_assignments(project: str | None = None) -> list[dict]:
    """Return [{user, full_name, projects: [{project, role, region, dept, is_active}, ...]}].

    If project is given, filter to that project's users. Visibility is gated by
    User Permission (auto-synced from GRM User Project Assignment), so a PM
    only sees users in their projects naturally.
    """
    filters = {"is_active": 1}
    if project:
        filters["project"] = project
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters=filters,
        fields=["name", "user", "project", "role", "department", "administrative_region", "is_active", "activation_status"],
    )
    by_user: dict[str, dict] = {}
    for r in rows:
        u = by_user.setdefault(r.user, {
            "user": r.user,
            "full_name": frappe.db.get_value("User", r.user, "full_name") or r.user,
            "projects": [],
        })
        u["projects"].append({
            "assignment": r.name,
            "project": r.project,
            "role": r.role,
            "department": r.department,
            "administrative_region": r.administrative_region,
            "is_active": r.is_active,
            "activation_status": r.activation_status,
        })
    return list(by_user.values())


@frappe.whitelist()
def revoke_assignment(name: str) -> dict:
    """Soft-revoke (is_active=0)."""
    doc = frappe.get_doc("GRM User Project Assignment", name)
    doc.is_active = 0
    doc.save()
    return {"ok": True}
```

- [ ] **Step 3: JS shell + table render**

`egrm/page/grm_users/grm_users.js`:

```javascript
frappe.pages["grm-users"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper, title: __("Users by Project"), single_column: true,
    });
    new GRMUsersView(page);
};

class GRMUsersView {
    constructor(page) {
        this.page = page;
        this.render_shell();
        this.load();
    }

    render_shell() {
        $(this.page.body).html(`
          <div class="grm-users">
            <div class="grm-users-toolbar">
              <select id="grm-project-filter" class="form-control"><option value="">${__("All projects you can manage")}</option></select>
              <button class="btn btn-primary" id="grm-add-assignment">${__("Add Assignment")}</button>
            </div>
            <div id="grm-users-table"></div>
          </div>`);
        $("#grm-project-filter").on("change", () => this.load());
        $("#grm-add-assignment").on("click", () => this.open_add_dialog());
    }

    async load() {
        const project = $("#grm-project-filter").val() || null;
        const r = await frappe.call({
            method: "egrm.page.grm_users.grm_users.list_users_with_assignments",
            args: { project },
        });
        this.render_table(r.message || []);
    }

    render_table(rows) {
        const $t = $("#grm-users-table").empty();
        if (!rows.length) { $t.html(`<p>${__("No assignments visible.")}</p>`); return; }
        rows.forEach((u) => {
            const projects_html = u.projects.map((p) => `
              <tr>
                <td>${frappe.utils.escape_html(p.project)}</td>
                <td>${frappe.utils.escape_html(p.role || "")}</td>
                <td>${frappe.utils.escape_html(p.administrative_region || "")}</td>
                <td>${frappe.utils.escape_html(p.department || "")}</td>
                <td>${p.is_active ? __("Active") : __("Inactive")} (${p.activation_status || ""})</td>
                <td><button class="btn btn-xs btn-danger grm-revoke" data-name="${p.assignment}">${__("Revoke")}</button></td>
              </tr>`).join("");
            $t.append(`
              <details open>
                <summary><strong>${frappe.utils.escape_html(u.full_name)}</strong> (${u.user})</summary>
                <table class="table table-sm">
                  <thead><tr><th>${__("Project")}</th><th>${__("Role")}</th><th>${__("Region")}</th><th>${__("Department")}</th><th>${__("Status")}</th><th></th></tr></thead>
                  <tbody>${projects_html}</tbody>
                </table>
              </details>`);
        });
        $t.find(".grm-revoke").on("click", async (e) => {
            const name = $(e.currentTarget).data("name");
            await frappe.call({ method: "egrm.page.grm_users.grm_users.revoke_assignment", args: { name } });
            this.load();
        });
    }

    open_add_dialog() {
        new frappe.ui.Dialog({
            title: __("Add Assignment"),
            fields: [
                { fieldname: "user", label: __("User"), fieldtype: "Link", options: "User", reqd: 1 },
                { fieldname: "project", label: __("Project"), fieldtype: "Link", options: "GRM Project", reqd: 1 },
                { fieldname: "role", label: __("Role"), fieldtype: "Link", options: "GRM Project Role", reqd: 1,
                  get_query: function () { return { filters: { project: cur_dialog.get_value("project") } }; } },
                { fieldname: "department", label: __("Department"), fieldtype: "Link", options: "GRM Issue Department" },
                { fieldname: "administrative_region", label: __("Administrative Region"), fieldtype: "Link", options: "GRM Administrative Region" },
            ],
            primary_action_label: __("Create"),
            primary_action: async (values) => {
                await frappe.db.insert({ doctype: "GRM User Project Assignment", ...values });
                cur_dialog.hide();
                this.load();
            },
        }).show();
    }
}
```

- [ ] **Step 4: Migrate + visual diff against XD's user-management screens**

```bash
bench --site egrm.local migrate 2>&1 | grep -v "Updating DocTypes" | tail -3
```

Visit `/desk/grm-users`. Compare against XD.

- [ ] **Step 5: Commit + tag**

```bash
git add egrm/page/grm_users/
git commit -m "feat(users): Aggregated Users-by-project desk page"
git tag phase-3-users
```

---

### Task 3.16: Phase 3 final verification

- [ ] **Step 1: Test users + Playwright**

```bash
bench --site egrm.local execute egrm.scripts.dev.test_users.create_test_grm_users
python3 /tmp/egrm-qa/test_homepage.py 2>&1 | tail -5
python3 /tmp/egrm-qa/test_gating.py 2>&1 | tail -5
```

Expected: existing portal regressions still green.

- [ ] **Step 2: New duty-driven workspace test**

Author `/tmp/egrm-qa/test_duty_workspace.py` that for each test user logs in, visits `/desk/egrm`, and asserts which phase-cards appear based on the user's duties. (Use `frappe.boot.egrm.duties` from JS evaluation.)

- [ ] **Step 3: Push to both branches**

```bash
git push origin main
git push origin main:version-16
```

---

## Self-Review

**1. Spec coverage** (against `ARCHITECTURE.md`):
- § 2 Six duties → Tasks 1.1–1.4 ✓
- § 3 New schema (3 doctypes + 2 fields) → Tasks 1.1–1.5 ✓
- § 4 Existing schema reference → no code change required (consumed by wizard in Phase 3) ✓
- § 5 Authority layers (Platform vs Project) → Tasks 2.1, 2.2 ✓
- § 6 Three-layer permissions → Tasks 1.8, 1.9, 1.10 ✓
- § 7 Workspace + display_depends_on → Task 1.11 (boot) + 2.1 (workspace) ✓
- § 8 UI phase groups → Task 2.1 (5 cards in workspace) ✓
- § 9 Wizard orchestrates existing schema → Tasks 3.1–3.14 ✓
- § 11 Migration phases → mirrored 1:1 in plan structure ✓

**2. Placeholder scan**: None of "TBD", "fill in", "implement later". Phase 3 step components (Tasks 3.2–3.13) are described by pattern + per-step doctype mapping rather than 12 fully-detailed tasks — this is intentional for a 12-step wizard where each step is structurally identical and the per-step questionnaire fields are the source of truth. The implementer follows the pattern.

**3. Type consistency**:
- `GRM Duty.duty_name` → referenced uniformly in seeder, role-duty Link target, boot helper.
- `GRM Project Role` autoname `{project}-{role_name}` matches the migration patch's `target = f"{r['project']}-{legacy}"`.
- `frappe.boot.egrm.duties` → set in Task 1.11, read by Task 2.1's `display_depends_on`.

**4. What I cut from the previous plan**:
- All 9 child-table doctypes I had proposed under `GRM Project` — redundant with existing `GRM Administrative Level Type`, `GRM Issue Category` routing, `GRM Project Link` pattern, etc.
- "Per-project Categories/Types/Statuses" Phase 4 — they already are project-scoped via `grm_project_link`.
- Citizen attribute fields on GRM Project — already on `GRM Issue` (per-issue, not per-project).
- Privacy rules child table — already covered by `GRM Issue.citizen_type` + `GRM Issue Category.confidentiality_level`.
- Appeal config on GRM Project — already on `GRM Issue.appeal_submitted/appeal_date` + `GRM Issue Category.assigned_appeal_department`.
- Sub-projects/components child tables — `GRM Administrative Region` hierarchy covers structural subdivision; not needed.
- Custom routing rule doctype — `GRM Issue Category.assigned_department` already does this.
- Custom SLA rule doctype — `GRM Administrative Level Type.acknowledgment_days/resolution_days` already does this.

The plan shrank from ~5000 lines and ~15 days to ~1500 lines and ~7 days because most of the work was already done.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-25-egrm-per-project-architecture-implementation.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
**2. Inline Execution** — execute in this session with batch checkpoints

Which approach?
