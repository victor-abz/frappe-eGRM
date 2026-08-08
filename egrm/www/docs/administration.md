# Administration

Running a project after the wizard has finished: managing who has
access, configuring SLAs and notifications, and getting reports out.

For creating a project from scratch, see
[**Create a New Project**](/docs/project-wizard). For the role and duty
model, see [**Role Assignment**](/docs/role-assignment).

---

## User management

Access is never granted globally. Every permission a user has comes
from a **user–project assignment** that names three things: the
project, the role (a bundle of duties), and the region.

### Adding someone to a project

1. Create the assignment with the project, role, and region.
2. The system issues a 6-digit activation code to the user's email.
3. The user activates. The assignment's activation status becomes
   `Activated`.
4. Only now does the user have any access.

Activation codes are valid for **48 hours** and allow **5 attempts**.
Reissue if either runs out. Activation endpoints are rate limited to 20
attempts per IP address per hour.

### Changing or removing access

| To do this | Change this |
| --- | --- |
| Change what someone can do | The role on the assignment |
| Change what they can see | The region on the assignment |
| Suspend access | Mark the assignment inactive |
| Move someone between projects | A separate assignment per project |

Deactivating an assignment takes effect on the **next request**, and on
mobile at the next sync — there is no cached grace period.

> **A widened assignment triggers a full mobile re-download.** When you
> add someone to a new project or region, their app detects it is short
> on records and upgrades its next sync automatically. Tell them to
> sync once and let it finish rather than to press *Full resync*.

### Who can manage assignments

Holders of the **Supervise** duty, within their scope, plus
`GRM Platform Administrator` and `System Manager`.

---

## SLAs and escalation

SLAs are configured per **administrative level type**, not per project
— so every project using that hierarchy inherits them.

For each level you set:

| Setting | Meaning | Default |
| --- | --- | --- |
| Acknowledgment days | Business days to acknowledge | 7 |
| Resolution days | Business days to resolve | 30 |
| Reminder before | Days ahead of deadline to warn | 2 |
| Auto-escalate on breach | Escalate automatically when breached | — |

Tighter deadlines at lower levels and longer ones higher up is the
normal shape, since higher levels take the harder cases.

### How escalation runs

SLA monitoring is a **scheduled daily job**, not an instant trigger. An
issue that breaches its deadline escalates on the next run. When it
does, the issue moves to the parent region, its SLA is recalculated for
the new level, a notification goes out, and a comment records why.

Staff can also escalate manually from the issue. Manual and automatic
escalation behave identically.

To find breached work, filter the issue list on SLA resolution status.

The 4-level chain and what each escalation changes are documented in
[Role Assignment](/docs/role-assignment#the-4-level-escalation-chain).

---

## Notifications

Notifications are template-driven and configured per project.

1. **Create templates.** Each has a type — Receipt, Acknowledgment, In
   Progress, Resolved, Closed, Escalated, or SLA Reminder — and links
   to an email template, an SMS message, or both. Leave the project
   blank to share a template across projects.
2. **Enable them on the project** and map a template to each event.
3. **Test** by walking a complaint through the statuses and confirming
   each message arrives.

SMS templates can interpolate the tracking code, subject, status,
region, complainant name, and the SLA deadlines and days remaining.

Email requires a configured email account on the site; SMS requires an
SMS gateway. Without a gateway, phone verification on the public portal
is unavailable too.

---

## Reporting

Reports can be scheduled to email themselves to a recipient list on a
fixed frequency, with filters for project, date range, and status.

Published reports can also be surfaced on the public portal, where
citizens can read them without a tracking code.

---

## Public portal configuration

The portal's sections are individually switchable per site, so you
control whether statistics, published reports, and the app download
page appear.

Two site-level settings change citizen-facing behaviour:

| Setting | Effect when absent |
| --- | --- |
| Cloudflare Turnstile keys | No bot challenge on the submission form |
| SMS gateway | No phone verification; citizens submit without it |

Rate limits on the public endpoints are 5 submissions per IP per day
and 3 verification codes per IP per hour. Both can be overridden in
site config where a deployment needs different numbers.

---

## Detailed runbooks

Four step-by-step guides live in the repository rather than on this
site, because they involve server access and site configuration:

| Guide | Covers |
| --- | --- |
| `docs/admin-guides/sla-configuration.md` | Full SLA setup, dashboard queries, manual job runs |
| `docs/admin-guides/notification-configuration.md` | Template creation and every available variable |
| `docs/admin-guides/auto-email-report-setup.md` | Scheduling monthly and quarterly report emails |
| `docs/admin-guides/report-archive-upload.md` | Naming and uploading archived reports |

---

## Where to look next

- [**Create a New Project**](/docs/project-wizard)
- [**Role Assignment**](/docs/role-assignment)
- [**What Each Duty Can Do**](/docs/duties)
- [**Troubleshooting**](/docs/troubleshooting)
- [**eGRM User Documentation home**](/docs)
