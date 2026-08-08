# What Each Duty Can Do

If a button you expect is not on screen, this page explains why. eGRM
decides what you can do from the **duties** attached to your role on
that specific project — not from your job title, and not from a global
account setting.

This is the reference for day-to-day desk users. For how roles are
created and assigned, see
[**Role Assignment**](/docs/role-assignment).

---

## The six duties

A Project Role is a bundle of one or more of these:

| Duty | Lifecycle phase | What it is for |
| --- | --- | --- |
| **Intake** | Intake | Create new issues |
| **Review** | Triage | Validate categorisation, eligibility, and severity; move issues on or reject them |
| **Assignment** | Triage | Set or change the assignee; route to a department or administrative level |
| **Investigate & Resolve** | Resolution | Add comments and evidence, propose a resolution, submit the issue |
| **Feedback** | Feedback | Handle the citizen rating and the appeal flow |
| **Supervise** | Oversight | Read everything in scope, force reassignment or closure, view dashboards, manage user assignments |

One person can hold any combination. A small project might give a
single Project Officer both Review and Investigate & Resolve; the
workflow does not change, that person just sees more buttons.

---

## What each duty permits

This is the authoritative mapping, enforced server-side on every
request:

| Action | Duties that permit it |
| --- | --- |
| Create an issue | **Intake** |
| Read an issue | Intake · Review · Assignment · Investigate & Resolve · Feedback |
| Modify an issue | Review · Assignment · Investigate & Resolve · Feedback |
| Submit | Review · Assignment · Investigate & Resolve |
| Cancel | **Review** |
| Delete | Nobody — administrators only |
| Print / export a report | Intake · Review · Assignment · Investigate & Resolve · Feedback |
| Email from the issue | Review · Assignment · Investigate & Resolve · Feedback |

Note that **Intake creates but does not modify**. Filing new issues and
editing existing ones are deliberately separate permissions.

---

## Field-level rules

Some fields carry their own duty requirement on top of the table above.
Changing one of these without the matching duty fails with
`You need the <duty> duty to change <field>`:

| Field | Duty required |
| --- | --- |
| Status, category, issue type | **Review** |
| Assignee | **Assignment** |
| Resolution text, resolver, resolution date, resolution days, resolution agreement | **Investigate & Resolve** |
| Rating, appeal submitted, appeal date | **Feedback** |

So the Feedback duty is not a comment-only role — it is the duty that
owns the citizen's rating and the appeal flow.

---

## Duty alone is not enough

Three further conditions apply before you can act on an issue.

**Your assignment must be active and activated.** Access comes from a
user–project assignment that is marked active and has activation status
`Activated`. A pending assignment grants nothing.

**The issue must be in your region.** Holding a duty on the project
does not let you see the whole project. The issue must sit in your
assigned region or below it in the hierarchy — with one exception: an
issue you personally handled at some point stays visible to you even if
it moves out of your region.

**Drafts belong to their owner.** An unsubmitted issue is visible only
to the person who created it, no matter what duties anyone else holds.
See [Draft visibility](/docs/issue-lifecycle#draft-visibility).

---

## Roles that bypass all of this

Three Frappe roles are checked before the duty model and see
everything:

| Role | Scope |
| --- | --- |
| **System Manager** | Bypasses Frappe permission checks entirely |
| **GRM Platform Administrator** | Manages projects globally |
| **GRM Supervise** | Project-scoped supervision |

`GRM Supervise` is the role counterpart of the Supervise duty. It is
not a read-only auditor: within its scope it can force reassignment and
closure and manage user assignments.

---

## If a button is missing

Work through this in order:

1. **Are you on the right project?** Duties are per project.
2. **Is your assignment activated?** Ask your project administrator.
3. **Do you hold the duty?** Check the table above against your role.
4. **Is the issue in your region?**
5. **Are you the assignee?** Some actions need it, not just the duty.

The client and the server enforce the same rules, so a missing button
means the action would be refused anyway. Never work around it by
patching the interface — the API returns `Permission denied`
regardless.

---

## Where to look next

- [**Issue Lifecycle**](/docs/issue-lifecycle) — the flow these duties
  gate.
- [**Role Assignment**](/docs/role-assignment) — building roles from
  duties and onboarding staff.
- [**Troubleshooting**](/docs/troubleshooting)
- [**eGRM User Documentation home**](/docs)
