# eGRM User Documentation

Operational guides for running an eGRM project end-to-end. Start with
the section for who you are.

## Citizens

| Guide | What it covers |
| --- | --- |
| [**Citizen Portal**](/docs/citizen-portal) | Submitting a grievance, tracking it with a code, appealing a resolution, and rating how it was handled — all without an account. |

## Government staff working cases

| Guide | What it covers |
| --- | --- |
| [**Issue Lifecycle**](/docs/issue-lifecycle) | The full flow: an Intake user files a draft, a Reviewer assigns it, an Investigate & Resolve user resolves it, and a Reviewer confirms closure. |
| [**What Each Duty Can Do**](/docs/duties) | Exactly which actions each duty permits, the field-level rules, and why a button might be missing. |

## Field officers on the mobile app

| Guide | What it covers |
| --- | --- |
| [**Mobile App**](/docs/mobile-app) | Installing the Android app, what works offline, what Sync actually does, and what to do when data looks missing. |

## Administrators

| Guide | What it covers |
| --- | --- |
| [**Create a New Project (Wizard)**](/docs/project-wizard) | Onboard a project from a blank slate in 13 steps — geography, roles, departments, categories, issue types, users, routing, SLAs, statuses, and activation. |
| [**Role Assignment, Onboarding & Escalation**](/docs/role-assignment) | How the role + region + duty model decides who owns a new issue, how to onboard staff, and how a stalled issue escalates up the 4-level chain. |
| [**Administration**](/docs/administration) | Day-to-day running: user management, SLAs, notifications, reporting, and portal configuration. |

## Everyone

| Guide | What it covers |
| --- | --- |
| [**Troubleshooting**](/docs/troubleshooting) | Sign-in and activation, missing buttons, mobile sync, portal errors, and what to include in a support request. |

---

## Glossary

The eGRM data model is **duty-driven**. Each project defines its own
Project Roles, and each Project Role is composed of one or more of the
six canonical **duties**:

- **Intake** — create new issues.
- **Review** — validate categorisation, eligibility, and severity; move
  issues on or reject them.
- **Assignment** — set or change the assignee; route to a department or
  administrative level.
- **Investigate & Resolve** — add comments and evidence, propose a
  resolution, submit the issue.
- **Feedback** — handle the citizen rating and the appeal flow.
- **Supervise** — read everything in scope, force reassignment or
  closure, view dashboards, and manage user assignments.

Separately, three Frappe roles bypass the duty model entirely:
**System Manager**, **GRM Platform Administrator**, and
**GRM Supervise**.

Duty checks are enforced both server-side and in form rendering. A user
who lacks the required duty will not see the button, and a direct API
call is rejected with `Permission denied`. Holding a duty is necessary
but not sufficient — the assignment must be activated and the issue
must fall in the user's region. See
[**What Each Duty Can Do**](/docs/duties) for the full rules.

## Conventions in these guides

- Screenshots are real captures from a live eGRM site, taken during the
  automated walker that exercises the same flow.
- Wherever a step references **Royal Care Hospital** (project code
  `RCH`), it is using a sample healthcare project — the same procedure
  applies to any project, substituting your own names.
- Linda, Margaret, and Aisha are sample users holding the Intake,
  Review, and Investigate & Resolve duties respectively. Bridget is a
  Project Director who also holds the Review duty.
