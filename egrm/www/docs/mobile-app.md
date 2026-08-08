# Mobile App: Install, Work Offline, Sync

The eGRM Android app is for field officers who collect issues away from
a desk — often with no signal at all. It keeps a full local copy of the
data you are entitled to, lets you work against that copy offline, and
reconciles with the server when you next have a connection.

This page covers installing the app, what works offline, and what the
Sync button actually does. If you handle cases from a computer instead,
see [**Issue Lifecycle**](/docs/issue-lifecycle).

---

## Install the app

The app is **not** on the Play Store. You download it once from the
public portal, and after that it updates itself.

1. On the Android device, open the portal and go to the app download
   page.
2. Tap the download link to fetch the `.apk`.
3. Android will warn you that the file came from outside the Play
   Store. Approve installation from this source when prompted.
4. Open the app and sign in with your eGRM account — the same email and
   password you would use on the web.

After the first launch the app checks for updates on its own and
installs them over the air. You do not need to re-download the `.apk`
to get a newer version.

> **Your account must be activated before you can sign in.** A user
> assignment only grants access once its activation status is
> `Activated`. If sign-in refuses your credentials but you know they are
> right, ask your project administrator to confirm your assignment is
> active — see [Role Assignment](/docs/role-assignment).

---

## What you can do offline

The app holds a local copy of your data, so the following work with no
connection:

| Works offline | Notes |
| --- | --- |
| Browse issues already on the device | Only issues your duties and region entitle you to |
| Create a new issue | Stored locally, uploaded on the next sync |
| Edit an issue you can already see | Same duty rules as the web |
| Add comments | Uploaded with the issue on the next sync |
| Attach photos, documents, and audio files | Held on the device until sync |
| Record the GPS location of an issue | Uses the device's own location services |

What does **not** work offline: anything that needs the server to
answer in the moment. You cannot sign in for the first time, download a
project you have just been added to, or see work that a colleague did
while you were disconnected until you sync.

Attachment types are classified server-side by file extension —
images, documents, and audio are all accepted. The app does not have a
built-in voice recorder or offline map; attach an audio file recorded
with the device's own recorder if you need one.

---

## What Sync does

One tap on **Sync** is not one request. Understand these four
behaviours and almost every "my data looks wrong" question answers
itself.

### It pages through large downloads

The server sends at most **1,000 issues per response**. When more is
waiting it says so, and the app immediately asks for the next batch.
A large first sync is therefore many round trips, and the progress
indicator stays up until the last batch lands.

This is deliberate. An unpaged replay of a district-sized account is a
single ~100 MB response that the phone has to parse on its UI thread,
and a dropped connection loses all of it. Paging keeps each request
around 2 MB and makes progress durable.

### It resumes instead of restarting

If a large download is interrupted, the next sync continues from the
last acknowledged page. Nothing already on the device is fetched twice.

### It repairs itself

The app tells the server how many records it already holds. If the
server sees the device is entitled to records it never received, it
upgrades that sync to a **full download automatically**.

The usual cause is being added to a new project or region after the app
was installed. You do not need to do anything — sync once on a stable
connection and let it finish.

### Reference data arrives last

Projects, categories, issue types, and statuses refresh at the **end**
of a large download, not the beginning. A sync that is still running
can briefly show issues before their category names have caught up.
This resolves itself when the sync completes.

---

## When data looks missing

**Sync once, on a stable connection, and let it finish.** The app
detects that it is short on records and repairs itself.

A first sync after a reinstall, or the first sync after being added to
a large project, downloads in several batches and takes noticeably
longer than a routine sync. Leave the screen open until it reports it
is done.

**Full resync** still exists and is still safe, but it is now a
fallback rather than part of normal operation. If data is still missing
*after* a sync has completed, that is a bug worth reporting — not
something to work around with Full resync.

When you report it, include:

- your account email,
- the project or region you expect to see,
- roughly when you were added to it,
- and whether the sync reported completion.

---

## Habits that avoid trouble

- **Sync before you leave signal.** The app can only give you what it
  has already downloaded.
- **Sync again when you get back.** Work sitting on the device is not
  visible to anyone else — and is not backed up — until it uploads.
- **Let a long sync finish.** Closing the app mid-sync is safe (it
  resumes), but you will not have complete data until it completes.
- **Charge before field work.** A long first sync and GPS both cost
  battery.

---

## Drafts are private, on mobile too

An issue you have created but not yet submitted is a **draft**, and a
draft is visible only to you. It does not appear for other duty-holders
on the project, on the web, or in anyone else's sync — not until you
submit it.

This is the same rule the web enforces; see
[Draft visibility](/docs/issue-lifecycle#draft-visibility).

---

## Where to look next

- [**Issue Lifecycle**](/docs/issue-lifecycle) — what happens to an
  issue after you submit it.
- [**What Each Duty Can Do**](/docs/duties) — why you can see some
  buttons and not others.
- [**Troubleshooting**](/docs/troubleshooting) — sync, sign-in, and
  permission problems.
- [**eGRM User Documentation home**](/docs)
