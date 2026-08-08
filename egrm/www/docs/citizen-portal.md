# Citizen Portal: Submit, Track, Appeal, Rate

The public portal is the only eGRM surface open to the general public.
Citizens use it without an account, at `/grm-portal`, to file a
grievance, follow it with a tracking code, appeal a resolution they
disagree with, and rate how it was handled.

This page describes what a citizen can do. Staff handling the resulting
cases should read [**Issue Lifecycle**](/docs/issue-lifecycle) instead.

---

## Submit a grievance

No sign-in is required. The form asks for:

| Field | Required | Notes |
| --- | --- | --- |
| Project | Yes | Only projects marked active are listed |
| Category | Yes | Must belong to the chosen project |
| Issue type | Yes | Must belong to the chosen project |
| Administrative region | Yes | Chosen by drilling down the region hierarchy |
| Description | Yes | What happened |
| Date the issue occurred | No | May differ from the submission date |
| Name, gender, contact details | No | See *Staying anonymous* below |

Categories, issue types, and regions are filtered by the project you
pick, so choose the project first — the other lists populate from it.

### Verification

Two checks may apply, depending on how the site is configured:

- **Bot check.** If the site has Cloudflare Turnstile configured, you
  must pass its challenge before the form will submit.
- **Phone verification.** If the site has an SMS gateway configured
  *and* you supply a phone number, the portal sends a 6-digit code by
  SMS. The code is valid for **5 minutes** and is consumed once used.

If neither is configured on your site, neither step appears.

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

You choose how much to reveal, and the choice has consequences later.

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

The portal also publishes aggregate information that needs no tracking
code: totals and status breakdowns, issues by category and region, and
trends over time, alongside any reports the administrators have
published. These are aggregates only — no individual complaint or
citizen is identifiable from them.

Which of these sections appear is controlled per site by the
administrator.

---

## Languages

The portal serves translated text and picks a default language for the
project being viewed. Citizens can switch languages from the interface.

---

## Where to look next

- [**Issue Lifecycle**](/docs/issue-lifecycle) — what staff do with a
  complaint once it arrives.
- [**Troubleshooting**](/docs/troubleshooting) — tracking codes,
  verification codes, and rate limits.
- [**eGRM User Documentation home**](/docs)
