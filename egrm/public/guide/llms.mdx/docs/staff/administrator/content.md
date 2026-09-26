# Project Administrator (/docs/staff/administrator)















































A project is the container for everything else — its regions, its categories,
its staff, and its complaints. Setting one up is done through the **Project
Setup Wizard**, which walks through the steps in order and saves as it goes.

From the main screen, open **Imishinga → Tangiriza Umushinga Mushya**
(*Projects → Start New Project*). To change a project that already exists,
open it and choose **Edit in Wizard**.

<img alt="Opening an existing project in the wizard" src="__img0" />

## Step 1 — Name the project [#step-1--name-the-project]

<img alt="Project information" src="__img1" />

The title, an optional start and end date, and the locale — country, default
language, number and date format, time zone.

<Callout type="warn">
  **Default Language** here sets the labels that both citizens and staff see.
  Choose it deliberately: changing it later changes the interface for everyone
  on the project at once.
</Callout>

## Step 2 — Build the region structure [#step-2--build-the-region-structure]

This is the most important step in the whole setup, and the hardest to change
afterwards.

First define the **levels** — the tiers your administrative hierarchy has,
such as Province, District, Sector, Cell.

<img alt="Administrative levels" src="__img2" />

Then load the actual regions into those levels. They can be imported rather
than typed one by one.

<img alt="Regions being imported" src="__img3" />

<img alt="Regions after import" src="__img4" />

<Callout type="warn">
  Every complaint is routed by its region, and every officer sees complaints
  based on the region they are assigned to. If the structure is wrong or
  incomplete, complaints will reach the wrong office and officers will be unable
  to see work that belongs to them. Get this right before adding anyone.
</Callout>

## Steps 3 to 8 — Define the vocabulary [#steps-3-to-8--define-the-vocabulary]

These steps set the lists people will choose from. Each is a simple table you
add rows to.

| Step                   | What it defines                              |
| ---------------------- | -------------------------------------------- |
| User types             | The kinds of staff account the project has   |
| Departments            | The units that complaints can be assigned to |
| Categories             | What a complaint can be about                |
| Issue types            | The channels complaints arrive through       |
| Citizen groups         | How complainants are grouped for reporting   |
| Notification templates | The wording of the messages the system sends |

<img alt="User types" src="__img5" />

<img alt="Departments" src="__img6" />

<img alt="Categories" src="__img7" />

<img alt="Issue types" src="__img8" />

<img alt="Citizen groups" src="__img9" />

<img alt="Notification templates" src="__img10" />

Keep these lists short. A category list with thirty entries produces
inconsistent filing, because two officers will classify the same complaint
differently.

## Step 9 — Add the staff [#step-9--add-the-staff]

Users can be added one at a time, or loaded in bulk from a file.

<img alt="The users step" src="__img11" />

For a bulk load, upload the file, map its columns to the fields eGRM expects,
check the preview, and confirm.

<img alt="Uploading a user file" src="__img12" />

<img alt="Mapping the columns" src="__img13" />

<img alt="Previewing before import" src="__img14" />

<img alt="Import complete" src="__img15" />

<Callout type="warn">
  **An account by itself grants nothing.** What determines which complaints a
  person can see is the **region they are assigned to** — not their role. Staff
  in this system typically hold the same set of duties as each other and differ
  only by region. A new user with no region assignment signs in successfully and
  sees an empty system.
</Callout>

Check the preview before confirming a bulk import. Correcting a bad import is
considerably more work than reading the preview.

## Steps 10 to 12 — Routing, time limits and statuses [#steps-10-to-12--routing-time-limits-and-statuses]

<img alt="Issue routing" src="__img16" />

**Routing** decides which department or role receives a complaint, based on
its category and region.

<img alt="Service level agreements" src="__img17" />

**Time limits** set how long each stage may take before a complaint escalates
on its own.

<img alt="Issue statuses" src="__img18" />

**Statuses** are the stages a complaint passes through. Some are marked as
*final*, meaning the complaint is finished.

<Callout type="warn">
  Be careful with **final** statuses. Marking more than one status as final —
  for example both *Resolved* and *Closed* — makes the end state of a complaint
  ambiguous, and which one a resolved complaint lands in may not be the one you
  intended. Keep exactly one final status unless you have a firm reason
  otherwise, and check the result on a test complaint afterwards.
</Callout>

## Step 13 — Activate [#step-13--activate]

<img alt="Activating the project" src="__img19" />

<img alt="Confirming activation" src="__img20" />

Activation opens the project for real complaints.

<img alt="Activation complete" src="__img21" />

## Before you hand it over [#before-you-hand-it-over]

Check each of these yourself rather than assuming:

* Submit a test complaint through the public website and confirm it appears
  for the officer who should receive it.
* Sign in as one ordinary staff account and confirm they see the complaints
  they should — and not the ones they should not.
* Check the tracking page returns a sensible result for the test complaint's
  code.
* Delete the test complaint before real use begins.

## If you get stuck [#if-you-get-stuck]

* **A user sees nothing after signing in.** They have no region assignment.
  This is the most common report by a wide margin.
* **Complaints reach the wrong office.** Check the region structure first and
  the routing rules second — a misplaced region explains most of these.
* **A region is missing.** Add it at the right level; do not attach it to the
  wrong parent as a shortcut, because visibility for every officer above it
  follows that parent.
