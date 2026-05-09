# RDAP E2E — AQE Queen Orchestration Prompt

> Drop the block below as the **first message** of a fresh Claude Code session.
> It hands the AQE Queen a complete brief to run a real user-journey E2E
> test of eGRM, using the RISA Customization Questionnaire as the
> project blueprint. No API shortcuts, no admin-as-resolver, no skipped
> wizard steps.

---

```
You are the AQE Queen orchestrating a full end-to-end test of eGRM.

================================================================
CONTEXT — READ FIRST
================================================================
- Working dir:     /Users/victor/egrm/apps/egrm             (start your session here)
                   This is where AQE v3 was initialised and where
                   .agentic-qe/, CLAUDE.md, and the project-memory live.
                   The bench root /Users/victor/egrm has unrelated apps;
                   running from the bench root would pollute context.
- Bench root:      /Users/victor/egrm                       (only bench commands need this)
                   For ANY `bench …` invocation, prefix with a cd so the
                   shell uses the bench root for that one command and
                   your session cwd stays clean. Pattern:
                       cd /Users/victor/egrm && bench --site egrm.local execute "..."
                   All file edits and Playwright drivers continue to use
                   absolute paths and do NOT need to change cwd.
- Codebase:        /Users/victor/egrm                       (Frappe v16 monorepo, app: apps/egrm)
- Site:            http://egrm.local:8000
- Mobile app:      /Users/victor/Documents/dev/grm-mobile-app   (read-only reference, NO changes)
- Plan (roles, duties, architecture — source of truth):
    /Users/victor/egrm/apps/egrm/docs/superpowers/plans/2026-04-25-egrm-per-project-architecture-implementation.md
- Project blueprint (use as scenario data, do NOT invent):
    /Users/victor/Library/CloudStorage/Dropbox/WorldBank/RISA/RISA - eGRM Customization Questionnairre.docx
    Project = RDAP (Rwanda Digital Acceleration Project)
- Wizard page:           /app/grm-project-wizard
- User assignment page:  /app/grm-users
- Region admin page:     /app/grm-administrative-region
- Artifacts root (NOT git-tracked): /Users/victor/egrm/aqe-screenshots/e2e-flow/
  Subfolders to create:
    wizard/ users/ regions/ intake/ triage/ resolve/ feedback/
    negative/ mobile-api/ manifest/

================================================================
HARD RULES (DO NOT VIOLATE)
================================================================
1. NO API SHORTCUTS for the user-facing journey. Project, regions, users,
   assignments, issues, status changes — all must go through the actual UI
   (Frappe desk for admin work; mobile API only where mobile is the real
   client). Do NOT seed via `bench execute` / `frappe.new_doc` to bypass
   any UI flow.
2. ONLY the cleanup script may use `bench execute`. Cleanup:
       cd /Users/victor/egrm && bench --site egrm.local execute \
         "frappe.get_attr('egrm.cli.cleanup_rdap.purge')()"
   (run the `cd` and `bench` together in one shell; do not change your
   session cwd away from /Users/victor/egrm/apps/egrm)
3. NO admin-as-resolver. Admin (Pria) only runs onboarding + supervises.
   Issue resolution is performed by non-admin users.
4. Viewport: every Playwright page MUST be 1920x720. Every screenshot is
   full-step + clipped to {x:0, y:0, width:1920, height:720}.
5. If a wizard step is wrongly ordered (e.g. Categories needs Departments
   first), FIX THE WIZARD. Do not back-jump, do not skip, do not seed
   prerequisites via API. A real user goes 1→2→3→…→12 linearly.
6. Conventional Commits + 6-duty plan roles ONLY:
       GRM Platform Administrator, GRM Supervise, GRM Intake, GRM Review,
       GRM Assignment, GRM Investigate & Resolve, GRM Feedback
7. Every claim of "passed" must have a screenshot or HTTP-response file
   on disk. No claim without artifact.
8. Use TodoWrite throughout. Mark each Act complete the moment its
   artifacts are written.

================================================================
TEST USERS — TWO PROVISIONING SCENARIOS
================================================================
Real-world reality: some duty users already exist as Frappe users
(transferred from another project, were seeded by IT, etc.); others
are brand-new emails the project-admin types into the assignment UI for
the first time. The wizard/assignment flow MUST handle both. This brief
tests BOTH paths.

  Scenario A — pre-existing Frappe user
  ------------------------------------------------------------------
  User record already exists at platform level (no project link).
  Project-admin enters their email in /app/grm-users → system finds
  the existing record → adds the project assignment → done.

  Scenario B — brand-new user (created inline by the assignment flow)
  ------------------------------------------------------------------
  No User doctype record for the email. Project-admin enters the email
  in /app/grm-users → system MUST create the User record inline
  (first/last name, set roles per duty, set initial password or trigger
  welcome email) → add the project assignment → done.
  If the assignment UI cannot do this, that is a P0 gap. STOP, file the
  bug with file:line, fix the wizard/assignment code, then continue.

Test-user matrix:

  project-admin@egrm.test  / ProjectAdmin@2026
    Scenario:  Scenario A (must exist before wizard runs — he RUNS the wizard)
    Roles:     GRM Platform Administrator + GRM Supervise
    Duty:      onboarding + oversight (NEVER resolves issues)

  triage-officer@egrm.test / TriageOfficer@2026
    Scenario:  Scenario A (pre-existing, no project link yet)
    Roles:     GRM Review + GRM Assignment
    Duty:      reviews classification, assigns to resolvers

  field-officer@egrm.test  / FieldOfficer@2026
    Scenario:  Scenario B (does NOT exist — created via assignment UI)
    Roles:     GRM Intake (set by assignment flow)
    Duty:      raises issues from the field

  resolver@egrm.test       / Resolver@2026
    Scenario:  Scenario B (does NOT exist — created via assignment UI)
    Roles:     GRM Investigate & Resolve + GRM Feedback (set by assignment flow)
    Duty:      works the issue, closes loop with citizen

Pre-flight (admin-only, see ACT 0):
    cd /Users/victor/egrm && bench --site egrm.local execute \
      "frappe.get_attr('egrm.cli.sync_test_users.sync_subset')(['project-admin@egrm.test','triage-officer@egrm.test'])"

If sync_subset does not yet exist, write it (or extend sync.py) so the
script ONLY provisions the two Scenario-A users. The other two emails
must remain unknown to Frappe at that point.

================================================================
RDAP SCENARIO DATA (from RISA questionnaire) "/Users/victor/Library/CloudStorage/Dropbox/WorldBank/RISA/RISA\ -\ eGRM\ Customization\ Questionnairre.docx"
================================================================
Project:
  code:                 RDAP
  title:                Rwanda Digital Acceleration Project
  description:          broadband / digital public services / digital innovation
  hotline:              0783349090, 0788569697
  start:                2026-01-01
  end:                  2031-12-31
  default_language:     en
  auto_escalation_days: 15

Admin Levels (in order):
  1. PIU       (ack 2d, res 15d, remind 2d, no auto-escalate)
  2. Province  (ack 2d, res 15d, remind 2d, auto-escalate ON)

Regions:
  PIU:                Rwanda PIU
  Province (parent = Rwanda PIU):
    Kigali City, Northern Province, Southern Province,
    Eastern Province, Western Province

Departments (5):
  PIU - Project Coordination
  PIU - Legal
  PIU - Environmental Safeguards
  PIU - Social Safeguards
  Provincial GRC

Issue Categories (7):
  Others, Appreciation, Question, Suggestion or Feedback,
  Bursary Related complaint, Grant Related complaint,
  Digital Literacy complaints

Issue Types (4):
  Complaint, Suggestion, Question, Appreciation

Issue Statuses:
  Open (initial),
  In Progress,
  Awaiting Citizen Feedback,
  Resolved (final),
  Rejected (final + rejected),
  Appealed

Age Groups:    0-18, 19-35, 36-65, 65+
Citizen Groups: Gender = Female, Male

================================================================
TEST FLOW (14 ACTS, 0..13 — execute in strict order)
================================================================

ACT 0 — RESET  (admin only — non-admin users are NOT yet bound to any project)
  - Run cleanup_rdap.purge (the only allowed bench execute) to wipe any
    prior RDAP. Also delete any pre-existing User records for
    field-officer@egrm.test and resolver@egrm.test (Scenario-B emails
    must be unknown to Frappe at this point).
  - Run sync_test_users.sync_subset to provision ONLY the two Scenario-A
    users at the platform level: project-admin + triage-officer. They
    have roles + passwords but NO project access yet.
  - Confirm via desk that the User doctype contains:
      project-admin@egrm.test         (exists)
      triage-officer@egrm.test        (exists)
      field-officer@egrm.test         (must NOT exist)
      resolver@egrm.test              (must NOT exist)
    Save the User-list screenshot to users/act0-user-list.png.
  - Verify ONLY project-admin can POST /api/method/login → HTTP 200, save
    response to mobile-api/login-project-admin.json. Do NOT attempt the
    other three; the Scenario-B users do not exist and the Scenario-A
    triage-officer is not yet linked to RDAP.

ACT 1 — WIZARD SANITY  (admin, 1920x720)
  - Login as project-admin via desk UI.
  - Navigate /app/grm-project-wizard (NEW project flow).
  - Confirm step order is strictly linear (no step depends on data created
    in a later step).
  - If any prerequisite is out of order → STOP, fix the wizard at:
        apps/egrm/egrm/egrm/page/grm_project_wizard/grm_project_wizard.js
    (STEP_TITLES array + step_class() map). Restart bench, reload, retry.
  - Screenshot: wizard/step00-empty.png

ACT 2 — ONBOARDING WIZARD  (admin)
  Drive Playwright through ALL 12 steps with the RDAP scenario data.
  After each step:
    - wait_for_selector on the saved-row table
    - screenshot wizard/stepNN-<name>.png
    - click Continue (no back-jumping)
  Step 12 = Activate. Confirm `is_active = 1` by opening the project in
  desk (NOT via bench).
  Final shot: wizard/step12-activated.png

ACT 3 — REGIONS via UI  (admin)
  Open /app/grm-administrative-region and create the 6 regions in
  parent→child order. Screenshot each form. Save list view to
  regions/list.png.

ACT 4 — USER ASSIGNMENT via UI  (admin) — covers BOTH provisioning scenarios
  Open /app/grm-users (or GRM User Project Assignment list). Create one
  assignment row per user, in this order, capturing the BEFORE state of
  each user record from the User list view first.

  4a. project-admin   → Rwanda PIU   (Scenario A, supervisory)
        Pre-state: User exists. Just add assignment.
        Screenshot: users/act4a-form.png  +  users/act4a-saved.png

  4b. triage-officer  → Rwanda PIU   (Scenario A — pre-existing user)
        Pre-state: User exists, no RDAP link.
        Action: enter email → form should match existing user (autocomplete
                or "user found" indicator). Add assignment.
        Verify: no duplicate User record was created. Roles unchanged.
        Screenshot: users/act4b-existing-match.png + users/act4b-saved.png

  4c. field-officer   → Kigali City  (Scenario B — NEW user, must be created inline)
        Pre-state: User does NOT exist (verified in Act 0).
        Action: enter email → assignment form recognises the email is new
                → asks for first/last name + duty role(s) → creates User
                record + assignment in one flow.
        Required behaviour:
          - User record created with role: GRM Intake
          - Initial password set OR welcome email triggered (record which)
          - Assignment row links new user to RDAP / Kigali City
        Verify in /app/user that the new User record exists with the
        expected roles.
        Screenshot:  users/act4c-new-form.png
                     users/act4c-new-user-created.png
                     users/act4c-saved.png
        If the UI cannot create a new user inline, this is a P0 GAP.
        STOP, file bug with file:line for the assignment form code,
        implement the inline-create flow, restart bench, retry from 4c.

  4d. resolver        → Kigali City  (Scenario B — second new user)
        Same as 4c but roles: GRM Investigate & Resolve + GRM Feedback.
        Screenshot:  users/act4d-new-form.png
                     users/act4d-new-user-created.png
                     users/act4d-saved.png

  Final assignment list screenshot → users/act4-final-list.png.
  Final User-list screenshot       → users/act4-user-list.png  (confirms
  all 4 emails now exist as User records).

ACT 5 — POST-SETUP USER VERIFICATION  (gate before any duty flow)
  Now that RDAP exists, regions exist, and assignments exist (some users
  pre-existing, some created inline by Act 4), verify the three non-admin
  users can each login AND see RDAP scoped to their assignment. This is
  the gate before Acts 6–9; if any of these fail the problem is in
  setup, not in the duty flow.

  Scenario A users (triage-officer):
    - Login uses pre-set password from sync_subset.

  Scenario B users (field-officer, resolver — created inline in Act 4):
    - Login uses whatever credential path the inline-create flow chose:
        (a) admin-set initial password → use it directly
        (b) welcome-email + reset link → simulate email reception, follow
            link, set password, then login
    - Whichever path, document it in mobile-api/login-flow-<user>.txt.

  For each of triage-officer, field-officer, resolver:
    - POST /api/method/login → HTTP 200. Save response to
      mobile-api/login-<user>.json.
    - GET /api/method/grm.api.mobile.list_my_projects (or desk equivalent)
      → must return RDAP and ONLY RDAP. Save JSON to
      mobile-api/projects-<user>.json.
    - Login via desk UI, screenshot the landing page (must show RDAP-
      scoped workspace, must NOT show admin-only menus).
        users/post-setup-<user>-desk.png
    - Verify region scoping:
        field-officer + resolver → see Kigali City only
        triage-officer            → see Rwanda PIU (and children) only
      Save list-view screenshots to users/post-setup-<user>-regions.png.
    - Verify role correctness: assignment-time roles still attached, no
      drift, no extra grants. Screenshot the User → Roles tab to
      users/post-setup-<user>-roles.png.
    - Logout cleanly before moving to next user.

  If any user fails this gate, STOP. Diagnose at the assignment / role /
  permission layer (NOT by granting more roles). For Scenario-B failures
  also check the inline-create code path (was the user actually created?
  was the password actually set? did the welcome email actually fire?).
  Fix the underlying bug, re-run from the relevant Act 4 sub-step, and
  retry Act 5.

ACT 6 — INTAKE  (field-officer)
  Logout admin → login field-officer.
  Through the desk UI (or mobile API endpoints if that is the real client
  path), raise THREE issues against RDAP / Kigali City:
    I1: Complaint   / Bursary Related complaint     ("delayed bursary disbursement")
    I2: Suggestion  / Suggestion or Feedback        ("more digital-literacy sessions")
    I3: Question    / Digital Literacy complaints   ("how to enroll in DLP")
  Capture initial Open status. Screenshots → intake/.

ACT 7 — TRIAGE  (triage-officer)
  Logout → login triage-officer.
  For each of I1, I2, I3:
    - Review classification (correct category/type if needed).
    - Assign to resolver@egrm.test.
    - Move to In Progress.
  Screenshots → triage/.

ACT 8 — RESOLVE  (resolver)
  Logout → login resolver.
  For each issue:
    - Add an investigation log entry.
    - Move I1 → Resolved with resolution note.
    - Move I2 → Awaiting Citizen Feedback (request more detail).
    - Move I3 → Rejected (out of scope) with reason.
  Screenshots → resolve/.

ACT 9 — FEEDBACK / CLOSE-LOOP  (resolver)
  Still as resolver:
    - On I2, simulate citizen response then move to Resolved.
    - On I1, post citizen-facing feedback message.
  Screenshots → feedback/.

ACT 10 — NEGATIVE PERMISSION TESTS
  As field-officer:    attempt to change status of I1   → must be denied.
  As resolver:         attempt to raise a NEW issue     → must be denied.
  As triage-officer:   attempt to access /app/grm-project-wizard
                       → must be denied / not visible.
  As field-officer:    attempt to view another region's issues
                       → must return empty / 403.
  Save HTTP responses + screenshots → negative/.

ACT 11 — MOBILE API SPOT-CHECK  (no app changes)
  Using cURL/requests, NOT the desk:
    - Login as field-officer → token.
    - GET /api/method/grm.api.mobile.list_my_issues → only Kigali-scoped.
    - Login as resolver → token.
    - GET same endpoint → only assigned issues visible.
    - Attempt cross-user fetch of project-admin issue ID → 403.
  Save raw JSON responses → mobile-api/.

ACT 12 — MANIFEST + CREDENTIAL SHEET
  Generate manifest/E2E-MANIFEST.md containing:
    - One row per Act with: status, artifact paths, key assertion result.
    - Test-user credential block (4 users, plain creds — local only).
    - Wizard step order finalised after any reorder fix.
    - Any wizard / permission bugs found, with file:line references.

ACT 13 — REPORT BACK
  Post a single summary message to the user with:
    - PASS/FAIL count per Act.
    - Path to manifest.
    - Path to credentials block.
    - List of bugs filed (with file:line).
    - Recommended next steps.

================================================================
EXECUTION NOTES
================================================================
- Use Playwright sync API. Always launch chromium headless. Always
  wait_for_load_state('networkidle') before DOM inspection.
- Driver scripts live at /tmp/aqe-e2e/  (run_<act>.py).
- Use TodoWrite to track all 14 Acts (0..13).
- If a step blocks, do NOT bypass — diagnose the root cause, fix the
  app code if needed, commit with Conventional Commits, retry.
- Spawn parallel sub-agents only for INDEPENDENT acts (e.g. Act 10
  negative tests can fan out). Sequential where state depends.
- Final commit message format:
      test(e2e): RDAP full-flow E2E with 14 acts + manifest

Begin with ACT 0. Report back at the end of each Act.

REMEMBER: at ACT 0 only the admin exists for this project context. The
other three users are not validated until ACT 5, AFTER the project,
regions, and assignments are in place. Logging them in earlier proves
nothing about RDAP.
```

---

## Notes for the operator (you)

- Drop the fenced block above into a new Claude Code session as the very first message — it is fully self-contained.
- The block points at the **already-existing** plan-aligned scripts (`sync_test_users.py`, `cleanup_rdap.py`); do not regenerate them.
- The Queen is **expected to fix the wizard step order in code** (not work around it) when the linear-flow check in Act 1 fails. That is the only architecturally invasive change permitted by this brief.
- All artifacts land under `/Users/victor/egrm/aqe-screenshots/e2e-flow/` and stay out of git.
