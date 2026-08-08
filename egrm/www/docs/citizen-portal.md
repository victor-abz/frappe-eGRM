# Citizen Portal: Submit, Track, Appeal, Rate

The public portal is the only eGRM surface open to the general public.
Citizens use it without an account, at `/grm-portal`, to file a
grievance, follow it with a tracking code, appeal a resolution they
disagree with, and rate how it was handled.

This page describes what a citizen can do. Staff handling the resulting
cases should read [**Issue Lifecycle**](/docs/issue-lifecycle) instead.

### Where things are

| Page | Address |
| --- | --- |
| Home | `/grm-portal` |
| Submit a grievance | `/grm-portal/submit` |
| Track a complaint | `/grm-portal/track` |
| Download the mobile app | `/grm-portal/download` |

The **Login** link in the portal header goes to the staff desk at
`/login`. It is not a citizen account — see
[What the portal does not do](#what-the-portal-does-not-do).

![The portal home page, offering Raise Issue and Track Complaint](/assets/egrm/images/docs/portal/01-home.png)

---

## Submit a grievance

No sign-in is required. Submission is a **four-step form**, and you
cannot move on until the current step is complete.

| Step | Asks for | Required |
| --- | --- | --- |
| 1 | Project, category, issue type | Yes |
| 2 | Where it happened — drill down the region hierarchy | Yes, to the lowest level offered |
| 3 | When it happened, and a description | Yes, both |
| 4 | Whether you want to be contacted | Yes — one of the two choices |

Categories, issue types, and regions all come from the project you pick
on step 1, so the later lists only populate once that choice is made.
The wording of the category and issue-type lists is configured per
project: on the Rwanda Digital Acceleration Project, for instance,
*category* carries the nature of the grievance (Complaint, Question,
Service Issue, Other) and *issue type* records how it reached the
office (Web Form, Phone Call, SMS, In Person, and so on).

![Step 1 of the submission form — project, category, and issue type](/assets/egrm/images/docs/portal/02-submit-step1.png)

Two limits on step 3 are worth knowing before you start typing: the
description must be at least **10 characters** and is capped at
**5,000**, with a live counter. The date is required by the form even
though the server will accept a complaint without one.

### Verification

Two checks may apply, depending on how the site is configured:

- **Bot check.** If the site has Cloudflare Turnstile configured, you
  must pass its challenge before the form will submit.
- **Phone verification.** If the site has an SMS gateway configured
  *and* you supply a phone number, the portal sends a 6-digit code by
  SMS. The code is valid for **5 minutes** and is consumed once used.

If neither is configured on your site, neither step appears — and
neither is currently switched on at `egrm.risa.gov.rw`, where the form
submits without a bot challenge.

### Limits

Submissions are rate limited to **5 per IP address per day**, and
verification codes to **3 per IP address per hour**. A shared
connection — an office, an internet café — shares that budget.

### Save your tracking code

A successful submission returns a **tracking code**. It is the only way
to find the complaint again: the portal has no citizen login and no
"my complaints" list. Write it down before closing the page.

---

## Staying anonymous

Step 4 puts the choice plainly: **Stay anonymous**, or **I want
updates**.

Choosing *I want updates* requires a **phone number** — it stays
required even if you pick Email or WhatsApp as your preferred contact
method, in which case an email field is added alongside it. Your name
and gender are optional either way.

Underneath, this is recorded as a contact medium, and the choice has
consequences later.

| Contact medium | What staff see | Effect downstream |
| --- | --- | --- |
| **Anonymous** (default) | No contact details | Nobody can reach you; rating needs no code |
| **Facilitator** | Contact goes via the officer who filed it | Follow-up through that officer |
| **Contact** | Your phone or email | You get notifications, and rating/appeal require a code sent to you |

Giving a contact channel is what lets the system verify it is really
you when you later rate or appeal. Staying anonymous is fully
supported, and an anonymous complaint is tracked and worked the same
way — you simply cannot be contacted about it.

---

## Track a complaint

![The tracking page — a single box for the tracking code](/assets/egrm/images/docs/portal/03-track.png)

Enter the tracking code on the tracking page. The portal returns:

- current status,
- category,
- submission date,
- acknowledgement date, if it has been accepted,
- resolution date, if it has been resolved,
- whether an appeal has been submitted, and when,
- your rating, if you have given one.

**No personal information is returned by the tracking lookup** — not
yours, and not the name of any officer. Anyone holding the code sees
only the progress of the case, which is why the code should be treated
as private.

If the code is not recognised, check it for transcription errors before
assuming the complaint was lost.

---

## Appeal a resolution

If you disagree with how your complaint was resolved, you can appeal.

- Available **only when the complaint is Resolved or Closed**.
- **One appeal per complaint.** There is no second appeal.
- Your reason is required, and is stored with the complaint (first
  1,000 characters).
- If you gave a contact channel and have not already rated the
  complaint, you must confirm a 6-digit verification code first.

A successful appeal **reopens the complaint** — it returns to an open
status and goes back into the queue for staff to look at again.

---

## Rate the handling

Rating tells the project how well the complaint was handled.

- Available **only when the complaint is Resolved or Closed**.
- Ratings are **1 to 5**, with an optional comment (first 500
  characters).
- **One rating per complaint** — it cannot be changed afterwards.
- If you gave a contact channel, request a code first; it is sent to
  your phone or email and is valid for **5 minutes**. If you submitted
  anonymously, no code is needed.

---

## What the portal does not do

Worth stating plainly, because these are reasonable things to expect:

- **There is no citizen account or login.** Your tracking code is your
  only handle on the complaint.
- **You cannot add a comment to a complaint after submitting it.**
  Public commenting is not implemented; the only ways to add anything
  after the fact are the appeal reason and the rating comment.
- **You cannot edit or withdraw a submitted complaint.**
- **You cannot attach files through the portal.** Attachments are added
  by staff.

---

## Public statistics and reports

The portal can publish aggregate information that needs no tracking
code: totals and status breakdowns, issues by category and region, and
trends over time, alongside any reports the administrators have
published. These are aggregates only — no individual complaint or
citizen is identifiable from them.

**Both are off by default and are off on `egrm.risa.gov.rw` today.**
The dashboard and reports cards are shown only when an administrator
enables `show_dashboard` and `show_reports` in the portal
configuration; until then the home page offers Submit and Track only.
The introductory line on the home page mentions viewing statistics
regardless of the setting, so a citizen may go looking for a page that
is not switched on.

Administrators: see
[Administration](/docs/administration#public-portal-configuration).

---

## Languages

The portal is available in **English**, **Français**, and
**Kinyarwanda**, switchable from the header on every page. It picks a
default for the project being viewed — Kinyarwanda on
`egrm.risa.gov.rw` — and the choice does not carry across a reload, so
a citizen who switches language may need to switch again later.

---

## Where to look next

- [**Issue Lifecycle**](/docs/issue-lifecycle) — what staff do with a
  complaint once it arrives.
- [**Troubleshooting**](/docs/troubleshooting) — tracking codes,
  verification codes, and rate limits.
- [**eGRM User Documentation home**](/docs)
