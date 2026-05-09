"""SUITE: Project onboarding (wizard-driven, no pre-seed).

This is the FIRST suite that must run after a clean
`bench --site egrm.local reinstall`. It exercises the actual project
wizard endpoints — the same `frappe.db.insert` / `frappe.client.save`
RPCs the wizard JS issues — to provision THREE projects whose
admin-level structures span the realistic deployment matrix:

  P1  RW-WB     Rwanda (6-level): Country/Province/District/Sector/Cell/Village
                — World-Bank long hierarchy.
  P2  KE-EAC    Kenya (5-level alt names): Country/County/Sub-County/Ward/Village
                — different label set, same depth → catches hardcoded
                "Province"/"District" assumptions.
  P3  STJ-HOSP  St. John Hospital (private, 4-level): Hospital/Department/Unit/Ward
                — completely non-geographic hierarchy → catches assumptions
                that levels map to administrative regions.

(Multi-language label coverage is out of scope here — handled by the
platform's translations feature in a separate suite.)

Payload shapes match the wizard JS verbatim and the DocType JSONs:
  - All catalog DocTypes (Category/Type/Status/Department/AgeGroup/CitizenGroup)
    link to their project via the `grm_project_link` child Table, NOT a
    direct `project` field.
  - GRM Issue Category requires: category_name, label, abbreviation,
    assigned_department, confidentiality_level, redirection_protocol,
    grm_project_link.
  - GRM Issue Citizen Group `group_type` is a Select with options "1"|"2"
    (per the wizard form default).
  - GRM Project Role has a direct `project` Link field and a `duties` Table
    of GRM Project Role Duty rows ({duty: <duty_name>}); the 6 canonical
    duties are seeded by the `seed_duty_catalog` patch (Intake, Review,
    Assignment, Investigate & Resolve, Feedback, Supervise).
  - `activate_project` requires ≥1 GRM Administrative Level Type AND
    ≥1 ACTIVE GRM Project Role for the target project.
  - `is_active` and `current_setup_step` on GRM Project are server-
    managed; the wizard does not send them on insert.

If any wizard step fails, this suite ABORTS the whole run — every
subsequent suite depends on at least one of these projects existing.

Output: writes `/Users/victor/egrm/aqe-screenshots/aqe-full-suite/wizard_state.json`
listing the named records created so downstream suites can pick them
up without re-querying.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

from _common import (
    ACTOR_PROJECT_ADMIN, ART, SuiteRun, get, login, logout, msg, post,
    run, summary, SITE,
)


# ----------------------------------------------------------------- layouts
#
# Tuple shapes:
#   levels:   (level_name, level_order, ack_days, res_days, reminder_days, auto_escalate)
#   regions:  (region_name, level_index, parent_region_name_or_None)
#   statuses: (status_name, open_status, final_status, rejected_status, initial_status)
#   citizen_groups: (group_name, group_type)  where group_type ∈ {"1","2"}.

LAYOUTS = [
    # ---- P1: Rwanda (World Bank canonical 6-level) -------------------
    {
        "code": "RW-WB",
        "title": "Rwanda — World Bank GRM (Country → Village)",
        "description": "Rwandan administrative hierarchy: Country/Province/District/Sector/Cell/Village.",
        "auto_escalation_days": 15,
        "levels": [
            ("Country",  0, 2, 15, 2, 0),
            ("Province", 1, 2, 15, 2, 1),
            ("District", 2, 2, 12, 2, 1),
            ("Sector",   3, 2,  8, 1, 1),
            ("Cell",     4, 1,  5, 1, 1),
            ("Village",  5, 1,  3, 1, 1),
        ],
        "regions": [
            ("Rwanda",            0, None),
            ("Eastern Province",  1, "Rwanda"),
            ("Kayonza District",  2, "Eastern Province"),
            ("Mukarange Sector",  3, "Kayonza District"),
            ("Murama Cell",       4, "Mukarange Sector"),
            ("Nyamatete Village", 5, "Murama Cell"),
        ],
        # Categories use the FIRST department by default (set in onboard_one()).
        "categories": ["General Complaint", "Information Request",
                       "Suggestion", "Appreciation"],
        "issue_types": ["Complaint", "Inquiry", "Suggestion", "Feedback"],
        "statuses": [
            ("Open",                       1, 0, 0, 1),
            ("In Progress",                1, 0, 0, 0),
            ("Awaiting Citizen Feedback",  1, 0, 0, 0),
            ("Resolved",                   0, 1, 0, 0),
            ("Closed",                     0, 1, 0, 0),
            ("Rejected",                   0, 0, 1, 0),
        ],
        "departments": ["Project Coordination", "Local Government"],
        "age_groups": ["0-18", "19-35", "36-65", "65+"],
        "citizen_groups": [("Female", "1"), ("Male", "1")],
    },
    # ---- P2: Kenya (alt-naming, same depth: Country/County/Sub-County/Ward/Village) -----
    {
        "code": "KE-EAC",
        "title": "Kenya — Devolution-era GRM (Country → Village)",
        "description": "Kenyan devolved hierarchy: Country/County/Sub-County/Ward/Village.",
        "auto_escalation_days": 12,
        "levels": [
            ("Country",     0, 2, 12, 2, 0),
            ("County",      1, 2, 10, 2, 1),
            ("Sub-County",  2, 2,  8, 1, 1),
            ("Ward",        3, 1,  6, 1, 1),
            ("Village",     4, 1,  4, 1, 1),
        ],
        "regions": [
            ("Kenya",           0, None),
            ("Nairobi County",  1, "Kenya"),
            ("Westlands",       2, "Nairobi County"),
            ("Kitisuru Ward",   3, "Westlands"),
            ("Loresho Village", 4, "Kitisuru Ward"),
        ],
        "categories": ["Service Delivery", "Devolved Funds", "Land",
                       "Health", "Education"],
        "issue_types": ["Complaint", "Inquiry", "Suggestion", "Appeal"],
        "statuses": [
            ("Open",        1, 0, 0, 1),
            ("Triaged",     1, 0, 0, 0),
            ("Assigned",    1, 0, 0, 0),
            ("In Progress", 1, 0, 0, 0),
            ("Resolved",    0, 1, 0, 0),
            ("Closed",      0, 1, 0, 0),
            ("Rejected",    0, 0, 1, 0),
        ],
        "departments": ["Office of the Governor", "County Public Service"],
        "age_groups": ["0-17", "18-34", "35-59", "60+"],
        "citizen_groups": [("Female", "1"), ("Male", "1"), ("PWD", "2")],
    },
    # ---- P3: Private hospital (departments-as-levels, non-geographic) ----
    {
        "code": "STJ-HOSP",
        "title": "St. John Hospital — Patient & Staff Grievance System",
        "description": (
            "Private-sector layout where 'admin levels' are organisational "
            "tiers, not geographic regions: Hospital/Department/Unit/Ward. "
            "Tests that the platform makes no geographic assumptions."
        ),
        "auto_escalation_days": 3,
        "levels": [
            ("Hospital",    0, 1, 7, 1, 0),
            ("Department",  1, 1, 5, 1, 1),
            ("Unit",        2, 1, 3, 1, 1),
            ("Ward",        3, 1, 2, 1, 1),
        ],
        "regions": [
            ("St. John Hospital",   0, None),
            ("Surgery",             1, "St. John Hospital"),
            ("Cardiothoracic Unit", 2, "Surgery"),
            ("Ward 4B",             3, "Cardiothoracic Unit"),
            ("Internal Medicine",   1, "St. John Hospital"),
            ("Diabetes Clinic",     2, "Internal Medicine"),
            ("Ward 2A",             3, "Diabetes Clinic"),
        ],
        "categories": ["Patient Care", "Billing", "Staff Conduct",
                       "Facilities", "Privacy / HIPAA-equivalent"],
        "issue_types": ["Complaint", "Compliment", "Incident Report",
                        "Safety Concern"],
        "statuses": [
            ("New",                      1, 0, 0, 1),
            ("Under Review",             1, 0, 0, 0),
            ("Awaiting Patient Reply",   1, 0, 0, 0),
            ("Resolved",                 0, 1, 0, 0),
            ("Closed - No Action",       0, 1, 0, 0),
            ("Escalated to Compliance",  1, 0, 0, 0),
            ("Rejected - Out of Scope",  0, 0, 1, 0),
        ],
        "departments": ["Patient Relations", "Quality & Safety",
                        "Compliance Office"],
        "age_groups": ["Pediatric (0-17)", "Adult (18-64)", "Senior (65+)"],
        "citizen_groups": [("Inpatient", "1"), ("Outpatient", "1"),
                           ("Emergency", "2")],
    },
]


# Canonical duty IDs seeded by `egrm.patches.v16_0.seed_duty_catalog`.
# Used to populate the GRM Project Role `duties` child rows.
DEFAULT_ROLE_DUTIES = [
    "Intake", "Review", "Assignment",
    "Investigate & Resolve", "Feedback", "Supervise",
]


# ---------------------------------------------------------------- XD design refs
#
# DESIGN FIDELITY — Adobe XD reference designs (BODY ONLY).
#
# The wizard BODY is expected to match these XD screens 1:1 (layout,
# spacing, branding, palette, copy). The Frappe sidebar and top header
# are stock Frappe chrome and are EXPLICITLY OUT OF SCOPE — do not
# flag them as fidelity diffs.
#
# Workflow:
#   1. UI-SCREENSHOTS captures one body-only PNG per wizard step at
#      MacBook 13" Retina (1440×900 @ 2x) — Playwright targets the
#      `.grm-project-wizard` element so the sidebar/header are cropped.
#   2. This module persists the XD URL ↔ step mapping into
#      `design_refs.json`.
#   3. UI-SCREENSHOTS writes `XD_FIDELITY_REPORT.md` with the captured
#      body PNG path next to the canonical XD URL — a reviewer compares
#      them side-by-side.
#
# Branding root (palette source-of-truth):
XD_PROJECT_ROOT = (
    "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/"
)

# Per-step screen URLs. Indexed by wizard step number (1-based) which
# matches the page-controller's `current_setup_step`.
#
# NOTE on Step 12 (`98ed62c7-…`): the oui/non yes/no toggles in the XD
# mock can be implemented as Frappe Check fields rendered as
# checkboxes (the same UX Frappe uses for permission rows). This is an
# implementation hint, not a hard assertion.
XD_SCREEN_URLS: dict[int, str] = {
    1:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/bf83ebcc-48f6-4189-bc2e-7a194b52cac9",
    2:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000002",
    3:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000003",
    4:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000004",
    5:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000005",
    6:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000006",
    7:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000007",
    8:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000008",
    9:  "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000009",
    10: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000010",
    11: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000011",
    12: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/98ed62c7-7782-41f6-b613-a933580e1794",
    13: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000013",
    14: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000014",
    15: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000015",
    16: "https://xd.adobe.com/view/34ddae20-54d5-4846-8d50-5249252b79e2-618e/screen/00000000-0000-0000-0000-000000000016",
}

# Implementation notes captured from the XD mocks for downstream
# checks. Keys are wizard step numbers; values are short bullet lists
# the UI-SCREENSHOTS report surfaces alongside each comparison.
XD_STEP_NOTES: dict[int, list[str]] = {
    12: [
        "Yes/No toggles can be Frappe `Check` fields rendered as checkboxes "
        "(same UX as Frappe permission rows).",
    ],
}


# ----------------------------------------------------------------- helpers

def insert_doc(s: requests.Session, payload: dict) -> tuple[int, dict]:
    """Mirror frappe.db.insert via the REST resource endpoint."""
    doctype = payload["doctype"]
    body = {k: v for k, v in payload.items() if k != "doctype"}
    return post(
        s,
        f"/api/resource/{doctype.replace(' ', '%20')}",
        data=body,
        timeout=30,
    )


def doc_name(body: dict) -> str | None:
    """Extract `name` from a /api/resource/<DocType> POST response."""
    if not isinstance(body, dict):
        return None
    rec = msg(body)
    if isinstance(rec, dict):
        # Frappe's REST POST wraps under {"data": {...record...}}.
        return rec.get("data", rec).get("name") if isinstance(
            rec.get("data", rec), dict) else None
    if isinstance(rec, list) and rec and isinstance(rec[0], dict):
        return rec[0].get("name")
    return None


# Phrases the egrm DocType validators raise when an "already exists"
# state is hit. The corresponding HTTP statuses are 409 (DuplicateEntry)
# or 417 (ValidationError). We treat these as idempotent successes.
_ALREADY_EXISTS_RX = re.compile(
    r"(DuplicateEntryError|already exists|already has an initial status|"
    r"A role named .+ already exists)",
    re.IGNORECASE,
)


def _resource_url(doctype: str) -> str:
    return f"/api/resource/{doctype.replace(' ', '%20')}"


def _find_existing_name(
    s: requests.Session,
    doctype: str,
    filters: list,
) -> str | None:
    """Fetch the `name` of an existing record matching ``filters``.

    The ``/api/resource/<DocType>`` GET returns ``{"data": [{"name": ...}, …]}``
    (no `message` envelope). After ``msg()`` we still have a dict with
    `data` as the inner list, so we descend explicitly.
    """
    try:
        c, b = get(
            s,
            _resource_url(doctype),
            params={
                "filters": json.dumps(filters),
                "limit_page_length": 1,
                # Pick the OLDEST matching record so re-runs converge on
                # the same record set as user/region seeders (which fired
                # before any onboarding pass). Picking the most-recent
                # match would race against seed users assigned to older
                # records.
                "order_by": "creation asc",
            },
        )
    except Exception:
        return None
    if c != 200 or not isinstance(b, dict):
        return None
    rec = msg(b)
    # /api/resource/* shape: {"data": [{"name": ...}]}
    if isinstance(rec, dict) and isinstance(rec.get("data"), list) and rec["data"]:
        first = rec["data"][0]
        if isinstance(first, dict):
            return first.get("name")
    if isinstance(rec, list) and rec and isinstance(rec[0], dict):
        return rec[0].get("name")
    return None


def upsert_doc(
    s: requests.Session,
    payload: dict,
    *,
    lookup_filters: list | None = None,
) -> tuple[int, dict, str | None, bool]:
    """Insert ``payload`` only when no row matches ``lookup_filters``.

    Most of the GRM catalog DocTypes (region, level type, role, …) do
    NOT carry a database unique index over their natural key
    ``(project, <name>, …)``. That means a plain POST to
    ``/api/resource/<DocType>`` will happily create a duplicate row
    when one already exists, and Frappe never raises 409. The end
    result is fan-out: every ``run_full_suite.py`` execution creates
    yet another parallel Rwanda chain etc. Existing assignments that
    target the original chain then become orphan, and downstream
    suites (IL, MOBILE-DUTY) push under regions the user can't reach.

    Solution: when ``lookup_filters`` are supplied, look up FIRST.
    Only POST if no record matches. If POST still fails with a
    duplicate (e.g. autoname collision), fall back to the lookup.

    Returns ``(http_code, body, name_or_None, was_already_present)``.
    """
    if lookup_filters:
        existing = _find_existing_name(s, payload["doctype"], lookup_filters)
        if existing:
            synthetic = {"data": {"name": existing}}
            return 200, synthetic, existing, True

    code, body = insert_doc(s, payload)
    if code in (200, 201):
        return code, body, doc_name(body), False

    # Defensive recovery path: if Frappe DID detect a duplicate after we
    # missed it (e.g. concurrent run), recover the existing name.
    body_str = str(body)
    if (code in (409, 417) or _ALREADY_EXISTS_RX.search(body_str)):
        existing = (
            _find_existing_name(s, payload["doctype"], lookup_filters)
            if lookup_filters else None
        )
        if existing:
            synthetic = {"data": {"name": existing}}
            return 200, synthetic, existing, True

    return code, body, None, False


# ----------------------------------------------------------------- onboarding

def onboard_one(s: requests.Session, suite: SuiteRun, layout: dict) -> dict:
    """Run the wizard's 12 steps for a single project layout.

    Order is dictated by hard data dependencies, NOT the wizard step
    numbers (the wizard doesn't enforce this order; we do):

       Step 1   create project              (autoname=field:project_code)
       Step 5   admin level types           (project Link field)
       Step 6   admin regions               (project Link + level Link)
       Step 8   departments                 (grm_project_link only)
       Step 7   categories                  (depends on department)
       Step 7   types
       Step 7   statuses
       Step 10  age groups
       Step 11  citizen groups
       Step 4   project role (active)       (REQUIRED for activate_project)
       Step 12  activate_project RPC        (gates is_active=1)
    """
    code = layout["code"]
    state: dict = {
        "code": code, "levels": {}, "regions": {},
        "departments": {}, "categories": {}, "issue_types": {},
        "statuses": {}, "age_groups": {}, "citizen_groups": {},
        "roles": {},
    }

    # ---- step 1: create project --------------------------------------
    # `is_active` and `current_setup_step` are server-managed: the
    # wizard does NOT send them on insert. activate_project flips them
    # to (1, 12) at the end.
    #
    # Idempotency note: if a previous run already created this project,
    # the resource POST returns 409 DuplicateEntry. `upsert_doc` then
    # falls back to a filtered GET so we recover the existing `name` and
    # keep the suite re-runnable without `bench reinstall`.
    pcode, pbody, project_name, _ = upsert_doc(
        s,
        {
            "doctype": "GRM Project",
            "project_code": code,
            "title": layout["title"],
            "description": layout["description"],
            "start_date": "2026-01-01",
            "end_date": "2030-12-31",
            "default_language": "en",
            "auto_escalation_days": layout["auto_escalation_days"],
        },
        lookup_filters=[["project_code", "=", code]],
    )
    suite.ok(f"OB-{code}.step1_create_project",
             pcode in (200, 201), f"http={pcode} body={str(pbody)[:200]}")
    project_name = project_name or code
    state["project_name"] = project_name

    # ---- step 5: admin level types -----------------------------------
    for (name, order, ack, res, rem, esc) in layout["levels"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Administrative Level Type",
                "project": project_name,
                "level_name": name,
                "level_order": order,
                "acknowledgment_days": ack,
                "resolution_days": res,
                "reminder_before_days": rem,
                "auto_escalate": esc,
            },
            lookup_filters=[
                ["project", "=", project_name],
                ["level_name", "=", name],
            ],
        )
        suite.ok(f"OB-{code}.level.{name}_created",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["levels"][name] = rec_name

    # ---- step 6: admin regions ---------------------------------------
    for (region_name, lvl_idx, parent_name) in layout["regions"]:
        level_label = layout["levels"][lvl_idx][0]
        level_doc = state["levels"].get(level_label)
        if not level_doc:
            suite.ok(f"OB-{code}.region.{region_name}",
                     False, f"missing level doc for {level_label}")
            continue
        parent_doc = state["regions"].get(parent_name) if parent_name else None
        payload = {
            "doctype": "GRM Administrative Region",
            "project": project_name,
            "region_name": region_name,
            "administrative_level": level_doc,
        }
        if parent_doc:
            payload["parent_region"] = parent_doc
        c, b, rec_name, _ = upsert_doc(
            s,
            payload,
            lookup_filters=[
                ["project", "=", project_name],
                ["region_name", "=", region_name],
                ["administrative_level", "=", level_doc],
            ],
        )
        suite.ok(f"OB-{code}.region.{region_name}_created",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["regions"][region_name] = rec_name

    # ---- step 8: departments (must precede categories) ---------------
    for dept in layout["departments"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Department",
                "department_name": dept,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["department_name", "=", dept]],
        )
        suite.ok(f"OB-{code}.dept.{dept}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["departments"][dept] = rec_name

    default_dept = next(iter(state["departments"].values()), None)
    if not default_dept:
        suite.ok(f"OB-{code}.default_department_available", False,
                 "no department was created → categories will fail")

    # ---- step 7a: categories (require label + assigned_department) ----
    for cat_name in layout["categories"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Category",
                "category_name": cat_name,
                "label": cat_name,
                "abbreviation": "".join(w[0] for w in cat_name.split())[:6].upper() or "GEN",
                "assigned_department": default_dept,
                "confidentiality_level": "Public",
                "redirection_protocol": 0,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["category_name", "=", cat_name]],
        )
        suite.ok(f"OB-{code}.cat.{cat_name}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["categories"][cat_name] = rec_name

    # ---- step 7b: issue types ----------------------------------------
    for itype in layout["issue_types"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Type",
                "type_name": itype,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["type_name", "=", itype]],
        )
        suite.ok(f"OB-{code}.type.{itype}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["issue_types"][itype] = rec_name

    # ---- step 7c: statuses -------------------------------------------
    for (sname, op, fin, rej, init) in layout["statuses"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Status",
                "status_name": sname,
                "open_status": op,
                "final_status": fin,
                "rejected_status": rej,
                "initial_status": init,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["status_name", "=", sname]],
        )
        suite.ok(f"OB-{code}.status.{sname}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["statuses"][sname] = rec_name

    # ---- step 10: age groups -----------------------------------------
    for ag in layout["age_groups"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Age Group",
                "age_group": ag,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["age_group", "=", ag]],
        )
        suite.ok(f"OB-{code}.age.{ag}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["age_groups"][ag] = rec_name

    # ---- step 11: citizen groups -------------------------------------
    for (gname, gtype) in layout["citizen_groups"]:
        c, b, rec_name, _ = upsert_doc(
            s,
            {
                "doctype": "GRM Issue Citizen Group",
                "group_name": gname,
                "group_type": gtype,
                "grm_project_link": [{"project": project_name}],
            },
            lookup_filters=[["group_name", "=", gname]],
        )
        suite.ok(f"OB-{code}.citizen_group.{gtype}.{gname}",
                 c in (200, 201), str(b)[:200])
        if rec_name:
            state["citizen_groups"][gname] = rec_name

    # ---- step 4: project role (REQUIRED — activate_project gates on
    #             ≥1 active role per project) ----------------------------
    c, b, role_name, _ = upsert_doc(
        s,
        {
            "doctype": "GRM Project Role",
            "project": project_name,
            "role_name": "Administrator",
            "is_active": 1,
            "description": "Default admin role provisioned by AQE onboarding suite.",
            "duties": [{"duty": d} for d in DEFAULT_ROLE_DUTIES],
        },
        lookup_filters=[
            ["project", "=", project_name],
            ["role_name", "=", "Administrator"],
        ],
    )
    suite.ok(f"OB-{code}.step4_create_project_role",
             c in (200, 201), str(b)[:200])
    if role_name:
        state["roles"]["Administrator"] = role_name

    # ---- step 12: activate -------------------------------------------
    c, b = post(
        s,
        "/api/method/egrm.egrm.page.grm_project_wizard.grm_project_wizard.activate_project",
        data={"project": project_name},
    )
    suite.ok(f"OB-{code}.step12_activate",
             c == 200 and isinstance(msg(b), (dict, str)),
             f"http={c} body={str(b)[:200]}")

    # ---- verify activation -------------------------------------------
    c, b = get(s, f"/api/resource/GRM%20Project/{project_name}")
    pdoc = msg(b) or {}
    if isinstance(pdoc, dict):
        pdoc = pdoc.get("data", pdoc)
    suite.ok(f"OB-{code}.is_active=1",
             isinstance(pdoc, dict) and pdoc.get("is_active") == 1,
             f"is_active={pdoc.get('is_active') if isinstance(pdoc, dict) else pdoc}")
    suite.ok(f"OB-{code}.is_setup_complete=1",
             isinstance(pdoc, dict) and pdoc.get("is_setup_complete") == 1,
             f"is_setup_complete={pdoc.get('is_setup_complete') if isinstance(pdoc, dict) else pdoc}")

    return state


# ----------------------------------------------------------------- main

def main() -> int:
    suite = SuiteRun("ONBOARDING")
    s = requests.Session()

    # Login as platform admin (only role permitted to call activate_project).
    code, body = login(s, *ACTOR_PROJECT_ADMIN)
    suite.ok("OB-0.admin_login",
             code == 200 and msg(body) == "Logged In", str(body)[:200])
    if not suite.results[-1].passed:
        return summary(suite)

    states = []
    for layout in LAYOUTS:
        print(f"\n--- onboarding {layout['code']} ---")
        states.append(onboard_one(s, suite, layout))

    # Persist onboarding state for downstream suites. Shape stays a
    # plain list (every downstream loader expects this).
    state_path = ART / "wizard_state.json"
    state_path.write_text(json.dumps(states, indent=2, default=str))
    print(f"\n[ONBOARDING] state -> {state_path}")

    # Persist XD design references in a SIBLING file so the
    # UI-SCREENSHOTS suite can emit XD_FIDELITY_REPORT.md.
    design_refs_path = ART / "design_refs.json"
    design_refs_path.write_text(json.dumps({
        "xd_project_root": XD_PROJECT_ROOT,
        "screens": XD_SCREEN_URLS,
        "notes": XD_STEP_NOTES,
        "_doc": (
            "Manual fidelity check (BODY ONLY): open each screen URL "
            "alongside the matching wizard_steps/wizard_step_NN.png "
            "produced by UI-SCREENSHOTS and compare layout, copy, "
            "spacing, and palette of the wizard body. The Frappe "
            "sidebar and top header are stock chrome and OUT OF "
            "SCOPE — do NOT flag them as fidelity diffs."
        ),
    }, indent=2, default=str))
    print(f"[ONBOARDING] design refs -> {design_refs_path}")

    logout(s)
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
