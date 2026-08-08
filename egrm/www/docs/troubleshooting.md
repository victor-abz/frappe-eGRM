# Troubleshooting

Real problems, with the actual cause. Grouped by who hits them.

---

## Signing in and account activation

### I cannot sign in, but my password is right

Your **assignment** is probably not activated. Access to a project
comes from a user–project assignment that must be both active and have
activation status `Activated`. Until then the account exists but grants
nothing.

Ask your project administrator to check the assignment, and to resend
your activation code if needed.

### My activation code does not work

| Symptom | Cause |
| --- | --- |
| "Expired" | Codes are valid for **48 hours** from when they are issued. Ask for a new one. |
| Rejected repeatedly | You get **5 attempts**. After that the code is locked and must be reissued. |
| Never arrived | Check spam, then confirm with your administrator that the email address on the assignment is the one you are checking. |

Codes are 6 digits. Requests are also rate limited to 20 per IP address
per hour, so a shared office connection can hit the limit even if you
personally have tried only a few times.

---

## Working cases on the web

### A button I need is missing

This is almost always the duty model working as designed, not a fault.
Work through the checklist in
[**What Each Duty Can Do**](/docs/duties#if-a-button-is-missing).

The short version: duties are per project, your assignment must be
activated, and the issue must be in your region.

### "Permission denied"

The server refused the action. The client hides buttons for actions you
cannot perform, so seeing this usually means the request came from a
direct API call, a stale browser tab, or an assignment that changed
after the page was loaded. Reload first.

### "You need the *X* duty to change *Y*"

Certain fields are individually gated. Status, category, and issue type
need **Review**; assignee needs **Assignment**; anything about the
resolution needs **Investigate & Resolve**; rating and appeal fields
need **Feedback**. See
[field-level rules](/docs/duties#field-level-rules).

### I cannot see an issue a colleague is discussing

Three likely reasons, in order:

1. **It is still a draft.** Unsubmitted issues are visible only to
   their creator. Nobody else sees them anywhere — not on the desk, not
   through the API, not in mobile sync.
2. **It is outside your region.** A duty on the project is not access
   to the whole project.
3. **Your assignment is inactive.**

### I cannot delete an issue

Nobody can, by duty. Deletion is reserved for administrators. Use
**Reject** or **Cancel** (Review duty) instead — both preserve the
audit trail, which deletion would destroy.

---

## Mobile app

### Data is missing after a sync

Sync once more on a stable connection and let it finish. Since version
1.2.3 the app reports what it holds, and the server upgrades the sync
to a full download automatically when the device is short — most often
because you were added to a project or region after installing.

If data is **still** missing after a sync that reported completion,
that is a bug. Report it with your account email, the project or region
you expect, roughly when you were added, and confirmation that the sync
finished. Do not treat *Full resync* as the fix.

### Sync is taking a long time

Expected in two cases: the first sync after a reinstall, and the first
sync after being added to a large project. Large downloads arrive in
batches of up to 1,000 issues, so a big account is many round trips.
Leave the screen open.

An interrupted sync resumes from the last completed batch, so you never
lose the whole download.

### Categories show as blank or wrong during a sync

Reference data — projects, categories, issue types, statuses — refreshes
at the **end** of a large download. A sync still in progress can show
issues before their category names catch up. It resolves on completion.

### My new issue has not reached the office

Issues created offline stay on the device until they upload. Sync while
you have a connection. Until then the work is neither visible to
colleagues nor backed up.

### The app version looks wrong after installing

The download and the running app can differ: a fresh install fetches
the published `.apk` and then updates itself over the air on first
launch. Check the version again after the first sign-in.

---

## Citizen portal

### "Complaint not found. Please check your tracking code."

The code did not match any complaint. Check for transcription errors —
confusing `0`/`O` and `1`/`I` is the common cause. There is no way to
recover a lost tracking code: the portal has no citizen login, so
nothing links a complaint back to a person. A citizen who has lost the
code must contact the project office.

### "Verification code expired. Please request a new one."

Verification codes last **5 minutes**. Request a fresh one.

### "Appeal is only available once the complaint is resolved."

Appeals and ratings both require the complaint to be **Resolved** or
**Closed**. Neither is available while it is still being worked.

### "An appeal has already been submitted" / "already been rated"

Both are once-only and cannot be changed or withdrawn.

### The form will not submit

| Message | Meaning |
| --- | --- |
| "Bot verification failed" | The Turnstile challenge did not pass. Reload and retry. |
| "Selected project is not active" | That project has been deactivated. Pick another. |
| "Selected category does not belong to this project" | Stale form state — reselect the project so the lists repopulate. |
| "SMS service is not configured" | Phone verification is unavailable on this site. Submit without a phone number. |
| Rate limit reached | **5 submissions per IP per day**, **3 verification codes per IP per hour**. Shared connections share the budget. |

### The home page mentions statistics, but there is no such page

The public dashboard and reports are switched off by default, while the
home page's introductory line mentions statistics regardless. If you
want citizens to have them, enable them — see
[Administration](/docs/administration#public-portal-configuration).

### A citizen wants to add information to their complaint

They cannot. Public commenting is not implemented. The only text a
citizen can add after submitting is an appeal reason or a rating
comment, and both require the complaint to be resolved first. Anything
else has to be relayed through staff.

---

## Administrators

### A user does not appear in the routing pool

Check, in order: the assignment exists, it is active, its activation
status is `Activated`, the role includes the duty the routing rule
expects, and the region matches. See
[Role Assignment](/docs/role-assignment#4-verify-the-user-appears-in-the-routing-pool).

### Notifications are not being sent

Templates are configured per project. Confirm the template exists for
the event, that the project references it, and that the email or SMS
transport is configured on the site. See
[Administration](/docs/administration#notifications).

### Issues are not escalating on time

SLA escalation runs on a schedule, not instantly — an issue past its
deadline escalates on the next scheduled run. Confirm the SLA is set
for the administrative level in question, and that the level has a
parent to escalate to. See
[Administration](/docs/administration#slas-and-escalation).

---

## Getting support

Before reporting anything, collect:

- what you were trying to do, and the exact error text,
- the tracking code or issue ID,
- the project,
- your account email,
- for mobile: the app version, and whether the sync reported completion.

Route it as: operational questions to your supervisor; access and
configuration to your project administrator; suspected faults to your
system administrator.

---

## Where to look next

- [**What Each Duty Can Do**](/docs/duties)
- [**Mobile App**](/docs/mobile-app)
- [**Citizen Portal**](/docs/citizen-portal)
- [**eGRM User Documentation home**](/docs)
