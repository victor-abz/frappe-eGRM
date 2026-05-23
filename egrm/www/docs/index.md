# eGRM User Documentation

Operational guides for running an eGRM project end-to-end. These pages
cover the two journeys most administrators and project staff will use:

| Guide | Audience | What it covers |
| --- | --- | --- |
| [**Create a New Project (Wizard)**](/docs/project-wizard) | Project administrators | Onboard a project from a blank slate in 13 steps — administrative geography, roles, departments, categories, issue types, users, routing, SLAs, statuses, and final activation. |
| [**Role Assignment, Onboarding & Escalation**](/docs/role-assignment) | Project administrators · operators | How the role + region + duty model decides who owns a new issue, how to onboard staff into roles, how to activate them, and how a stalled issue escalates up the 4-level administrative chain. |
| [**Issue Lifecycle: Create → Resolve → Confirm**](/docs/issue-lifecycle) | Government workers handling cases | The full duty-driven flow: an Intake user files a draft, a Reviewer assigns it, an Investigate & Resolve user resolves it, and a Reviewer confirms closure. |

## Glossary

The eGRM data model is **duty-driven**. Each project defines its own
Project Roles, and each Project Role is composed of one or more of the
seven canonical **duties**:

- **Intake** — file a new issue (create + own a draft).
- **Review** — triage drafts, assign, accept/reject, submit, confirm resolution.
- **Assignment** — manage assignee within an open issue.
- **Investigate & Resolve** — work the issue and submit a proposed resolution.
- **Feedback** — leave comments and feedback without mutating the issue.
- **Supervise** — read-only audit access across all projects (bypass role).
- **Administer** — full project administration (bypass role).

Every page in this site enforces duty checks both server-side (controller
+ permission hook) and client-side (form rendering). A user who lacks the
required duty for a given action will not see the button, and a direct
API call will be rejected with `Permission denied`.

## Conventions in these guides

- All screenshots are real captures from a live eGRM site, taken during
  the automated walker that exercises the same flow.
- Wherever a step references **Royal Care Hospital** (project code
  `RCH`), it is using a sample healthcare project — the same procedure
  applies to any new project, you'll just substitute your own names.
- Linda, Margaret, Aisha, and Bridget are sample users with the
  Intake / Review / Investigate & Resolve / Administer duties
  respectively.
