# Issue Lifecycle: Create → Resolve → Confirm

This page walks through the full **duty-driven** flow that a single
issue goes through, from the moment an Intake officer files a draft
until a Reviewer confirms the resolution and closes it.

We illustrate every step with screenshots from a live RCH (Royal Care
Hospital) project. The four sample users are:

| User | Email | Duty |
| --- | --- | --- |
| **Linda Okonkwo** | linda.okonkwo@yopmail.com | Intake |
| **Margaret Mwangi** | margaret.mwangi@yopmail.com | Review |
| **Aisha Ndlovu** | aisha.ndlovu@yopmail.com | Investigate & Resolve |
| **Bridget Mensah** | bridget.mensah@yopmail.com | Review (Director) |

Each stage of the lifecycle is gated by the user's **duties**.
A user without the right duty does not see the button on the form,
and a direct API call (e.g. `egrm.api.issue.assign`) is rejected
with `Permission denied`. Both checks share the same canonical
logic in `egrm/permissions/issue_permission.py`.

---

## Stage 1 — Intake creates a draft

### 1a. Open the blank form

Linda logs in and clicks **+ New** on the GRM Issue list. The form
opens in **draft** mode (`docstatus = 0`). Linda is the **owner**
of this draft and, until she submits it, no one else on the project
will see it — not on the desk, not in `issue.list`, not in
`sync.pull_changes`. See the [Draft visibility](#draft-visibility)
section below for the exact rule.

![A blank GRM Issue form just opened by Linda](/assets/egrm/images/docs/lifecycle/10-create-blank-form.png)

### 1b. Fill in the issue details

Linda picks the **project**, **category**, **issue type**,
**administrative region**, citizen information, and the free-text
**description**. The form auto-fills the tracking code preview
based on the project code and current date.

![The same form, fully filled in](/assets/egrm/images/docs/lifecycle/11-create-form-filled.png)

### 1c. Save the draft

Hitting **Save** persists the draft (still `docstatus = 0`). The
issue now has a real ID and a tracking code, and the **Submit**
action appears in the page header.

![Form saved, tracking code generated, Submit available](/assets/egrm/images/docs/lifecycle/12-create-saved.png)

Linda can edit the draft as many times as she wants. Other
duty-holders on the project — even other Intake officers — cannot
see it yet.

### 1d. Submit for review

When Linda is satisfied, she clicks **Submit**. `docstatus` flips to
`1` and the issue lands in the Reviewer queue with status **New**.
On the GRM Issue list it shows up with a coloured status pill:

![GRM Issue list showing status pills for New, In Progress, Resolved, Closed, Rejected](/assets/egrm/images/docs/lifecycle/13-issue-list-status-pills.png)

---

## Stage 2 — Reviewer triages and assigns

Margaret has the **Review** duty on RCH. She logs in, sees Linda's
issue in the list (now visible because it has been submitted), and
opens it.

![Reviewer Margaret opens the freshly submitted issue](/assets/egrm/images/docs/lifecycle/20-reviewer-opens-issue.png)

The form shows three Review-duty actions in the header:

- **Assign** — pick an Investigate & Resolve user
- **Accept** — keep the assignment and move to **In Progress**
- **Reject** — close the issue as **Rejected** with a reason

Margaret clicks **Assign**, picks **Aisha** (an Investigate &
Resolve user), and confirms. The status moves to **In Progress**
and the assignee block updates:

![After assigning Aisha, status In Progress, assignee Aisha](/assets/egrm/images/docs/lifecycle/21-reviewer-after-assign.png)

A notification email is sent to Aisha using the template configured
on **Step 8 — Notification Templates** of the wizard.

---

## Stage 3 — Resolver investigates and submits a resolution

Aisha logs in. Because the issue is now assigned to her, she sees
it on her **My Issues** tab. She opens it.

![Aisha opens the issue assigned to her](/assets/egrm/images/docs/lifecycle/30-resolver-opens-issue.png)

The Investigate & Resolve duty exposes:

- **Add comment / attachment** — record investigation notes
- **Propose Resolution** — write the resolution text and submit it

Aisha investigates (which might involve multiple comments and
file uploads), then clicks **Propose Resolution**. The issue moves
to status **Resolved** and waits for a Reviewer to confirm.

![Aisha after proposing the resolution, status Resolved](/assets/egrm/images/docs/lifecycle/31-resolver-after-resolve.png)

Aisha cannot close the issue herself — Resolve only proposes a
resolution, never finalises it. Final closure is reserved for the
Review duty.

---

## Stage 4 — Reviewer confirms closure

Bridget, the Project Director, also has the Review duty. She opens
the resolved issue:

![Bridget opens the resolved issue for final review](/assets/egrm/images/docs/lifecycle/40-director-opens-issue.png)

Two Review-duty actions are available on a resolved issue:

- **Confirm Resolution** — closes the issue as **Closed**
- **Reopen** — sends it back to **In Progress** with a note

Bridget is satisfied with Aisha's resolution and clicks **Confirm
Resolution**. The issue moves to terminal status **Closed**:

![Bridget after confirming, status Closed, final timestamp populated](/assets/egrm/images/docs/lifecycle/41-director-after-confirm.png)

The citizen receives a final notification (template configured on
Step 8 of the wizard), and the issue is locked from further
mutation by anyone without the Administer duty.

---

## Draft visibility

A frequently-asked question: **who can see a draft?**

The rule is uniform across desk, mobile sync, and API:

> An issue with `docstatus = 0` is visible **only** to its
> **owner**, plus any user with one of the bypass roles
> (`System Manager`, `GRM Platform Administrator`, or
> `GRM Supervise`). Once submitted (`docstatus = 1`), the normal
> project/region/duty visibility rules apply.

This is enforced at three layers:

1. **`permission_query_conditions`** on GRM Issue
   (`egrm/permissions/issue_permission.py`) — adds the
   `(docstatus > 0 OR owner = me)` clause to every desk list query.
2. **`has_permission` hook** — guards `frappe.has_permission()`
   calls used by individual form loads.
3. **Custom API endpoints**
   (`egrm.api.issue.list`, `egrm.api.issue.get`,
   `egrm.api.issue.get_latest_issues`, `egrm.api.sync.pull_changes`)
   — apply the same filter explicitly with `or_filters` and
   post-query draft stripping, so the rule holds even when
   `permission_query_conditions` is bypassed.

This belt-and-braces approach is verified by an automated walker
(`/tmp/step9-walk/walk_api_drafts.py`) that logs in as the owner
and as another duty-holder, then asserts the non-owner cannot see
the owner's drafts via any surface.

---

## State machine summary

```
                       Submit               Assign               Propose
                       ────────►            ────────►            ─────────►
Draft (private)        New                  In Progress          Resolved
                  ▲    │                    │                    │
       Edit/Save  │    │ Reject             │ Reopen             │ Confirm
                  │    ▼                    │                    ▼
                  └──  Rejected ◄───────────┘                    Closed
                       (final)              (Review-duty only)   (final)
```

| Transition | Required duty |
| --- | --- |
| Save draft | Intake (and owner) |
| Submit | Intake (and owner) |
| Assign | Review |
| Accept | Review |
| Reject | Review |
| Reassign within open issue | Assignment |
| Add comment / attachment | Investigate & Resolve, Feedback, Review |
| Propose Resolution | Investigate & Resolve |
| Confirm Resolution | Review |
| Reopen from Resolved | Review |

A user can hold multiple duties — for example, a small project
might give a single Project Officer both Review and Investigate &
Resolve. The state machine doesn't change; the same person just
sees more buttons.

---

## Where to look next

- [**Create a New Project (Wizard)**](/docs/project-wizard) — set up
  the project, roles, and routing rules that this lifecycle depends
  on.
- [**Role Assignment, Onboarding & Escalation**](/docs/role-assignment)
  — how the assignee for a freshly raised issue is picked, how to
  onboard staff so they become eligible, and how an unresolved issue
  walks up the 4-level administrative chain (Sector → District →
  Province → Country).
- [**eGRM User Documentation home**](/docs) — the full index.
