# Create a New Project (Wizard)

This page walks through the **GRM Project Wizard** — the 13-step
flow that turns an empty eGRM site into a fully configured project
with administrative geography, user roles, departments, issue
categories, routing, SLAs, and statuses.

Throughout this guide we use the sample project **Royal Care
Hospital** (project code `RCH`). Substitute your own project name
and code as you go.

---

## Entry points

The wizard can be reached two ways:

### 1. From the project list — "New Project"

Project administrators (System Manager, GRM Platform Administrator,
or any user with the Administer duty) can click **+ New** on the GRM
Project list and choose **Project Wizard**, which lands them on Step 1
with a blank form.

### 2. From an existing project — "Edit in Wizard"

Opening any existing GRM Project document shows an **Edit in Wizard**
primary action in the page header. Clicking it routes to the wizard
pre-loaded with that project, so the same flow can be used to revise
configuration after launch.

![Edit in Wizard button on the GRM Project detail page](/assets/egrm/images/docs/wizard/00-project-detail-edit-button.png)

After clicking the action, the wizard opens at the project's current
step with every field pre-populated:

![Wizard opened from the project detail page, with RDAP fields pre-filled](/assets/egrm/images/docs/wizard/00-edit-in-wizard-landed.png)

---

## Step 1 — Project Information

The first step captures the basic metadata: **title**, **code**,
**description**, optional start/end dates, and which **app
modules** the project uses (Public Citizen, Mobile, Web Desk).

Validation rules:

- **Title** is required and must be unique site-wide.
- **Code** is required, uppercase, 2–10 characters. It becomes part
  of every issue's tracking code (e.g. `RCH-2026-000123`).
- Dates are optional but if both are set, end must be after start.

![Step 1 — Project Information](/assets/egrm/images/docs/wizard/01-project-info.png)

Once the project record is saved, the remaining steps unlock and the
wizard remembers the project ID so you can leave and resume later.

---

## Step 2 — Administrative Levels & Regions

eGRM is geographically aware: every issue belongs to an
**administrative region** at some level (country → province →
district → sector → cell → village, or whatever hierarchy fits the
project).

### 2a. Define the levels

The first sub-tab is **Administrative Levels**. You list the levels
top-down and set how deep the tree should go.

![Step 2 — Administrative Levels](/assets/egrm/images/docs/wizard/02-admin-levels.png)

### 2b. Import the regions

The second sub-tab is **Administrative Regions**, which lets you
upload a CSV or paste a tree of regions matching the levels above.

![Step 2 — Administrative Regions tab](/assets/egrm/images/docs/wizard/02-admin-regions-tab.png)

A preview confirms the tree shape before commit:

![Step 2 — Administrative Regions preview](/assets/egrm/images/docs/wizard/02-admin-regions-preview.png)

After import, the full tree is visible and searchable:

![Step 2 — Administrative Regions imported](/assets/egrm/images/docs/wizard/02-admin-regions-imported.png)

---

## Step 3 — User Types (Project Roles)

This is the most important conceptual step. eGRM is **duty-driven**:
every Project Role is a named bundle of one or more of the seven
canonical duties.

The seven duties are:

| Duty | What it allows |
| --- | --- |
| Intake | File a new issue (own a draft) |
| Review | Triage drafts, assign, accept/reject, submit, confirm resolution |
| Assignment | Manage assignee within an open issue |
| Investigate & Resolve | Work the issue and submit a proposed resolution |
| Feedback | Leave comments without mutating the issue |
| Supervise | Read-only audit access (bypass role) |
| Administer | Full project administration (bypass role) |

On this step you create roles like **Intake Officer**, **Project
Director**, **Field Investigator**, etc., and tick the duties each
role gets.

![Step 3 — User Types (Project Roles + Duties)](/assets/egrm/images/docs/wizard/03-user-types.png)

These roles are reused on Step 9 (Users) and Step 10 (Routing) — get
them right here and everything else flows naturally.

---

## Step 4 — Departments

Departments group issue categories under organisational owners
(e.g. "Clinical Services", "Facilities", "Billing"). Each
department later gets a default head for routing.

![Step 4 — Departments](/assets/egrm/images/docs/wizard/04-departments.png)

---

## Step 5 — Issue Categories

Categories are the top-level taxonomy citizens and staff use to
classify an issue (e.g. "Patient Care", "Waiting Time",
"Cleanliness", "Staff Conduct"). Each category is owned by a
department from Step 4.

Categories can be marked **redirect** if they should jump to a
specific department head rather than the normal routing chain.

![Step 5 — Issue Categories](/assets/egrm/images/docs/wizard/05-categories.png)

---

## Step 6 — Issue Types

Issue Types describe the **mode** of an issue, independent of its
category — for example **Complaint**, **Suggestion**, **Question**,
**Compliment**. They are project-scoped so each project can adjust
the wording.

![Step 6 — Issue Types](/assets/egrm/images/docs/wizard/06-issue-types.png)

---

## Step 7 — Citizen Groups & Lookups

This step seeds the reference lookups used on the public citizen
intake forms: **Citizen Groups**, **Genders**, **Age Groups**, and
the optional **Vulnerability** flags.

![Step 7 — Citizen Groups & Lookups](/assets/egrm/images/docs/wizard/07-citizen-groups.png)

---

## Step 8 — Notification Templates

Each duty transition can send a templated email or SMS — for
example "Your issue has been received", "Your issue has been
assigned to Aisha", "Your issue has been resolved". Step 8 lets
you customise the subject and body of each template and toggle them
on/off per channel.

![Step 8 — Notification Templates](/assets/egrm/images/docs/wizard/08-notification-templates.png)

---

## Step 9 — Users

Step 9 binds real Frappe users to the Project Roles defined on Step
3. There are two ways to add users:

### 9a. One at a time

The landing view of Step 9 lets you search for an existing Frappe
user (or invite a new one by email) and assign one or more Project
Roles plus an administrative region scope.

![Step 9 — Users landing](/assets/egrm/images/docs/wizard/09-users-landing.png)

### 9b. Bulk upload (CSV)

For projects with many staff there is a **Bulk Upload** panel.

![Step 9 — Bulk upload panel](/assets/egrm/images/docs/wizard/09-users-bulk-panel.png)

Upload a CSV with email, name, role, and region columns:

![Step 9 — Bulk upload, file selected](/assets/egrm/images/docs/wizard/09-users-bulk-upload.png)

Map the columns to eGRM fields:

![Step 9 — Bulk upload column mapping](/assets/egrm/images/docs/wizard/09-users-bulk-mapping.png)

Preview the rows that will be created:

![Step 9 — Bulk upload preview](/assets/egrm/images/docs/wizard/09-users-bulk-preview.png)

After commit, every row is materialised as a Frappe **User** with
the right project role assignment and region scope:

![Step 9 — Bulk upload done](/assets/egrm/images/docs/wizard/09-users-bulk-done.png)

> **Tip** — passwords are not in the CSV. New users are invited by
> email and set their own password on first login. The bulk-upload
> flow also supports setting a temporary password via the API for
> automated test seeding.

---

## Step 10 — Issue Routing

Routing tells eGRM which Project Role receives a freshly submitted
issue based on its **category** and **administrative region**. You
build a small decision table here, one row per rule.

![Step 10 — Issue Routing](/assets/egrm/images/docs/wizard/10-issue-routing.png)

If no rule matches an incoming issue, eGRM falls back to the
department's default head from Step 4.

---

## Step 11 — Service Level Agreements (SLAs)

Step 11 defines, per category, how long an issue can sit in each
status before it is flagged overdue. The clock is paused while the
issue is waiting on the citizen and resumes once the worker has
the ball.

![Step 11 — SLAs](/assets/egrm/images/docs/wizard/11-slas.png)

---

## Step 12 — Issue Statuses

Every project comes pre-seeded with the canonical status set so the
state machine works out of the box:

| Status | Open? | Initial? | Final? | Rejected? |
| --- | --- | --- | --- | --- |
| New | ✓ | ✓ |  |  |
| In Progress | ✓ |  |  |  |
| Resolved | ✓ |  |  |  |
| Closed |  |  | ✓ |  |
| Rejected |  |  |  | ✓ |

You can add project-specific statuses (e.g. "Awaiting Lab Results")
and adjust the booleans, but the five canonical statuses must
remain in place.

![Step 12 — Issue Statuses](/assets/egrm/images/docs/wizard/12-issue-statuses.png)

> **Re-running the wizard on an existing project is safe.** The
> seeder is idempotent — existing statuses are matched by name and
> only missing rows are inserted.

---

## Step 13 — Activate

The final step is a confirmation page that summarises what was
configured and flips the project's **status** from `Draft` to
`Active`.

![Step 13 — Activate, landing state](/assets/egrm/images/docs/wizard/13-activate-landing.png)

After confirmation, the wizard shows a green check and the project
is officially live — users assigned on Step 9 can now log in and
start filing issues:

![Step 13 — Activate confirmed](/assets/egrm/images/docs/wizard/13-activate-confirmed.png)

![Step 13 — Project activated, redirect to project home](/assets/egrm/images/docs/wizard/13-activate-done.png)

---

## What's next?

Once a project is active, government workers can start working
cases. See the companion guide:

[**Issue Lifecycle: Create → Resolve → Confirm →**](/docs/issue-lifecycle)
