# Role Assignment, Onboarding & Escalation

This page explains how eGRM decides **who owns a freshly raised issue**,
how staff are onboarded into those roles via the
[Project Wizard](/docs/project-wizard), and how the **4-level
escalation chain** re-routes an unresolved issue up the administrative
hierarchy.

For the day-to-day worker view of an issue moving from draft to closed,
see the companion guide
[Issue Lifecycle: Create → Resolve → Confirm](/docs/issue-lifecycle).

---

## The duty model in one minute

eGRM is **duty-driven**. Every Project Role is a bundle of one or more
of six canonical duties:

| Duty | Lets the user… | Where it gates an action |
| --- | --- | --- |
| **Intake** | File a new issue (own a draft) | "+ New Issue" button, Save, Submit |
| **Review** | Triage drafts, assign, accept/reject, confirm resolution | Review-duty action buttons; status, category, and issue type fields |
| **Assignment** | Manage the assignee within an open issue | Reassign on an in-progress issue; the assignee field |
| **Investigate & Resolve** | Work the issue, accept, escalate, propose a resolution | Accept / Escalate / Record Resolution actions; the resolution fields |
| **Feedback** | Handle the citizen rating and the appeal flow | The rating and appeal fields |
| **Supervise** | Read everything in scope, force reassignment or closure, manage user assignments | Backed by the `GRM Supervise` bypass role |

Separately, three Frappe roles bypass the duty model entirely:
**System Manager**, **GRM Platform Administrator**, and
**GRM Supervise**.

A single person can hold any combination — a small project might give
one Project Officer both Review and Investigate & Resolve. The duty
checks are uniform on the server
(`egrm/server_scripts/grm_issue_permissions.py`, with field-level rules
in `egrm/egrm/doctype/grm_issue/grm_issue.py`) and on the desk client
(`egrm/egrm/doctype/grm_issue/grm_issue.js`).
**If the action button isn't on screen, the logged-in user lacks the
duty or isn't currently the assignee** — never patch the client to make
the button appear.

Roles are created on
[**Step 3 — User Types** of the wizard](/docs/project-wizard#step-3--user-types-project-roles).

---

## How an issue gets its first assignee

The resolver lives at `egrm/services/assignee_routing.py` and runs as
`before_insert` on every GRM Issue (mobile push, public submit, and
desk-created). Routing is **role + region + duty**. Departments are a
labeling concern; they do not influence routing.

Resolution order — first match wins:

1. **Explicit override.** If the incoming payload already names an
   `assignee`, honor it verbatim. The mobile sync path uses this so
   field workers can keep manual choices on round-trip.
2. **Staff self-submission (Case A).** A logged-in reporter who holds
   the **Investigate & Resolve** duty for this project AND has an
   active assignment in the issue's region — or any ancestor of it —
   becomes the assignee. "Issue is in my location → I own it until I
   reassign."
3. **Category → Role routing (Case B).** Each category is configured
   to route to a Project Role (see
   [Step 10 — Issue Routing](/docs/project-wizard#step-10--issue-routing)).
   The resolver walks the region chain closest-first (exact region,
   then parents). At each level it picks users who:
   - have an active assignment to (project, role, that region), **and**
   - hold the Investigate & Resolve duty via that role.

   The first level with at least one candidate wins — an ancestor never
   outranks an exact-region match. Among candidates at the winning
   level, the resolver picks the one with the lowest current open-issue
   count (tie-break: earliest assignment, then user ID ASC).
4. **No eligible user.** Returns `(None, <reason code>)`. The reason
   code is logged on the issue (e.g.
   `NO_RESOLVER_FOR_ROLE:Sector Officer`) and the issue is left
   unassigned for an operator to handle from the desk.

Categories whose `routing_target_type` is not `Role` (legacy
`Department` rows or NULL) return `CATEGORY_HAS_NO_ROUTING_TARGET:<cat>`
— fix them on
[Step 10 — Issue Routing](/docs/project-wizard#step-10--issue-routing).

---

## Onboarding a worker — wizard to logged-in

The successful path runs end-to-end through the wizard and ends with
the user holding their own password.

### 1. Define the role on Step 3

Open the wizard (either entry point on
[Project Wizard](/docs/project-wizard#entry-points)) and on
[Step 3 — User Types](/docs/project-wizard#step-3--user-types-project-roles)
create one Project Role per real-world function — for example **Sector
Officer**, **District Coordinator**, **Province Director**, **Country
Administrator**. Tick the duties that role needs (most field roles need
**Investigate & Resolve**; supervisors also need **Review**).

### 2. Add the user on Step 9

There are two ways, both documented on
[Step 9 — Users](/docs/project-wizard#step-9--users):

- **Single add:** search for an existing Frappe user (or invite a new
  one by email), pick one or more Project Roles, and bind them to an
  administrative region.
- **Bulk upload:** drop a CSV with `email, name, role, region` columns
  and confirm the mapping. Every row becomes a Frappe User with an
  active `GRM User Project Assignment` row.

### 3. Activate the assignment

Brand-new assignments land in `activation_status = "Pending Activation"`
until either:

- the user logs in (via desk or mobile) and completes activation, or
- an admin bulk-activates them through the wizard's
  Step 9 → **Change status → Activated** action.

For large rosters the wizard UI is hard to drive at scale; bypass it
with the same code path the UI uses:

```bash
bench --site egrm.local execute egrm.cli.activate_pending_users.main \
    --kwargs '{"project": "RGRP26", "role_label": "Digital Ambassador"}'
```

This calls
`egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_assignments.bulk_update_assignments`
internally — no DB hacks, no side channels.

### 4. Verify the user appears in the routing pool

Once activated, the user is eligible for new assignments. Confirm in
the desk:

1. Open the GRM Project for that project.
2. Open any GRM Issue in the user's region (or raise a fresh one).
3. The user should appear in the candidate pool returned by
   `assignee_routing.resolve_assignee` for any category that routes to
   their role.

If they don't, the most common causes are:

- the assignment is still **Pending Activation** (run the CLI above),
- the role lacks the **Investigate & Resolve** duty (fix on Step 3),
- the category isn't routing to that role (fix on Step 10),
- the user's region doesn't cover the issue's region (region chain
  works upward — an exact-region match wins, an ancestor does not
  outrank it).

---

## The 4-level escalation chain

When an Investigate & Resolve worker can't close an issue at their
level, they **Escalate**. The issue jumps to the parent region in the
admin hierarchy, the status resets to the project's initial status, and
a fresh assignee is picked at the new level using the same routing
rules above.

The reference project (`RGRP26`) uses four levels:

```
Sector  →  District  →  Province  →  Country
```

A real run looks like this:

| Step | Persona | Region | Action | Result |
| --- | --- | --- | --- | --- |
| 1 | Sector officer | Gatenga | Accept then Escalate | Region → Kicukiro · assignee → kicukiro.d1 · `escalation_count = 1` |
| 2 | District coordinator | Kicukiro | Accept then Escalate | Region → Kigali city · assignee → kigali.prov1 · `escalation_count = 2` |
| 3 | Province director | Kigali city | Accept then Escalate | Region → Rwanda · assignee → country.admin · `escalation_count = 3` |
| 4 | Country admin | Rwanda | Accept then Record Resolution | Status → Resolved |

The escalate action runs at
`egrm/server_scripts/issue_actions.py::escalate_issue`. The same shape
is mirrored by SLA-driven auto-escalation in
`egrm/egrm/utils/sla_manager.py::escalate_to_parent_level` so manual
and automatic escalations behave identically.

### What an Escalate actually changes

For each escalation, the server:

1. **Guards** that the caller is the current assignee and holds the
   Investigate & Resolve duty.
2. **Guards** that the current region has a `parent_region`.
3. **Records** the reason on the `grm_issue_escalation_reason` child
   table.
4. **Moves** `administrative_region` → `parent_region`.
5. **Resets** `status` to the project's initial status (usually `New`).
6. **Re-routes** by clearing `assignee` and calling
   `assignee_routing.resolve_assignee` at the new region. Whoever the
   resolver returns becomes the new owner.
7. **Increments** `escalation_count`, sets `last_escalated_date`, and
   resets `escalate_flag = 0` (this flag is transient — only used to
   gate the desk button).
8. **Saves** with `ignore_permissions = True` (the duty check above is
   what makes the action safe), then notifies the new assignee.

If routing returns no candidate at the parent level, the issue is left
unassigned with a logged reason code, and an operator at that level
takes it from the desk.

### When the chain runs out

If the issue is already at the top of the admin tree (`parent_region`
is empty) the server refuses with `Cannot escalate: already at the top
of the region chain.` The Country-level Investigate & Resolve user must
either resolve the issue or formally Reject it.

---

## Internal references

For maintainers — code, schema, and the reusable patterns:

- **Resolver:** `egrm/services/assignee_routing.py`
- **Permission hook:** `egrm/server_scripts/grm_issue_permissions.py`
- **Issue actions (accept / escalate / resolve / reject / reopen):**
  `egrm/server_scripts/issue_actions.py`
- **Auto-escalate (SLA Manager):** `egrm/egrm/utils/sla_manager.py`
- **Issue schema (allow_on_submit lives here):**
  `egrm/egrm/doctype/grm_issue/grm_issue.json`
- **Desk-side action button gating:**
  `egrm/egrm/doctype/grm_issue/grm_issue.js`
- **Activation CLI:** `egrm/cli/activate_pending_users.py`
- **Lifecycle reset fixture (test-only):**
  `egrm/cli/reset_issue_for_lifecycle.py`
- **Developer debugging skill:**
  `.claude/skills/frappe-submittable-actions-debug/` — captures the
  patterns used to diagnose action-button silent failures,
  `UpdateAfterSubmitError` on submittable doctypes, and the Playwright
  per-persona recipe.

---

## Where to look next

- [**Create a New Project (Wizard)**](/docs/project-wizard) — the
  end-to-end setup that produces the roles, regions, and routing rules
  this page depends on.
- [**Issue Lifecycle: Create → Resolve → Confirm**](/docs/issue-lifecycle)
  — the worker-facing view of how a single issue moves through draft,
  triage, resolve, and confirm.
- [**eGRM User Documentation home**](/docs) — the full index.
