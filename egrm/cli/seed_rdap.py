"""Seed the RDAP (Rwanda Digital Acceleration Project) test project with
realistic data sourced from the RISA - eGRM Customization Questionnaire.

Run: bench --site egrm.local execute egrm.cli.seed_rdap.seed
"""
import frappe

PROJECT_CODE = "RDAP"

ADMIN_LEVELS = [
    {
        "level_name": "PIU",
        "level_order": 1,
        "acknowledgment_days": 2,
        "resolution_days": 15,
        "reminder_before_days": 2,
        "auto_escalate": 0,
    },
    {
        "level_name": "Province",
        "level_order": 2,
        "acknowledgment_days": 2,
        "resolution_days": 15,
        "reminder_before_days": 2,
        "auto_escalate": 1,
    },
]

# (level_name, region_name, parent_region_or_None)
REGIONS = [
    ("PIU", "Rwanda PIU", None),
    ("Province", "Kigali City", "Rwanda PIU"),
    ("Province", "Northern Province", "Rwanda PIU"),
    ("Province", "Southern Province", "Rwanda PIU"),
    ("Province", "Eastern Province", "Rwanda PIU"),
    ("Province", "Western Province", "Rwanda PIU"),
]

CATEGORIES = [
    "Others",
    "Appreciation",
    "Question",
    "Suggestion or Feedback",
    "Bursary Related complaint",
    "Grant Related complaint",
    "Digital Literacy complaints",
]

ISSUE_TYPES = [
    "Complaint",
    "Suggestion",
    "Question",
    "Appreciation",
]

ISSUE_STATUSES = [
    ("Open", "open", 0, 0, 0),
    ("In Progress", "open", 0, 0, 0),
    ("Awaiting Citizen Feedback", "open", 0, 0, 0),
    ("Resolved", "final", 1, 0, 0),
    ("Rejected", "final", 0, 1, 0),
    ("Appealed", "open", 0, 0, 0),
]

DEPARTMENTS = [
    "PIU - Project Coordination",
    "PIU - Legal",
    "PIU - Environmental Safeguards",
    "PIU - Social Safeguards",
    "Provincial GRC",
]

AGE_GROUPS = ["0-18", "19-35", "36-65", "65+"]

CITIZEN_GROUPS = [
    ("Gender", "Female"),
    ("Gender", "Male"),
]


def _exists(doctype, filters):
    return bool(frappe.get_all(doctype, filters=filters, limit=1))


def _ensure(doctype, payload, key):
    """Insert if not exists by key field. Returns the doc name."""
    filters = {k: payload[k] for k in [key, "project"] if k in payload}
    rows = frappe.get_all(doctype, filters=filters, fields=["name"], limit=1)
    if rows:
        return rows[0].name
    doc = frappe.new_doc(doctype)
    for k, v in payload.items():
        doc.set(k, v)
    doc.insert(ignore_permissions=True)
    return doc.name


def seed():
    # 1. PROJECT
    if frappe.db.exists("GRM Project", PROJECT_CODE):
        proj = frappe.get_doc("GRM Project", PROJECT_CODE)
        print(f"EXISTS project {PROJECT_CODE}")
    else:
        proj = frappe.new_doc("GRM Project")
        proj.project_code = PROJECT_CODE
        proj.title = "Rwanda Digital Acceleration Project"
        proj.description = (
            "RDAP Development Objectives: Increase access to broadband, "
            "increase access to selected digital public services, and "
            "strengthen the digital innovation system. "
            "Uptake channels: smartphone direct, indirect via friends/relatives, "
            "indirect via focal points/facilitators, third-party data entry. "
            "Hotline: 0783349090, 0788569697. Feedback also accepted via email "
            "and verbal/face-to-face."
        )
        proj.start_date = "2026-01-01"
        proj.end_date = "2031-12-31"
        proj.default_language = "en"
        proj.is_active = 0  # Will activate via wizard step 12
        proj.auto_escalation_days = 15
        proj.current_setup_step = 1
        proj.insert(ignore_permissions=True)
        print(f"CREATED project {PROJECT_CODE}")

    # 2. ADMIN LEVEL TYPES
    for lvl in ADMIN_LEVELS:
        payload = dict(lvl, project=proj.name)
        nm = _ensure("GRM Administrative Level Type", payload, "level_name")
        print(f"  level: {nm}")

    # 3. ADMIN REGIONS
    for level_name, region_name, parent_name in REGIONS:
        # Find level type doc name
        lvls = frappe.get_all(
            "GRM Administrative Level Type",
            filters={"project": proj.name, "level_name": level_name},
            fields=["name"], limit=1,
        )
        if not lvls:
            continue
        lvl_doc = lvls[0].name

        # Look up parent region by name within project
        parent_doc = None
        if parent_name:
            ps = frappe.get_all(
                "GRM Administrative Region",
                filters={"project": proj.name, "region_name": parent_name},
                fields=["name"], limit=1,
            )
            if ps:
                parent_doc = ps[0].name

        existing = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": proj.name, "region_name": region_name},
            fields=["name"], limit=1,
        )
        if existing:
            print(f"  region exists: {region_name}")
            continue
        d = frappe.new_doc("GRM Administrative Region")
        d.project = proj.name
        d.region_name = region_name
        d.administrative_level = lvl_doc
        if parent_doc:
            d.parent_region = parent_doc
        d.insert(ignore_permissions=True)
        print(f"  region: {region_name}")

    # 4. ISSUE CATEGORIES
    for cat in CATEGORIES:
        payload = {
            "project": proj.name,
            "category_name": cat,
            "display_label": cat,
        }
        nm = _ensure("GRM Issue Category", payload, "category_name")
        print(f"  cat: {nm}")

    # 5. ISSUE TYPES
    for itype in ISSUE_TYPES:
        payload = {"project": proj.name, "type_name": itype, "display_label": itype}
        nm = _ensure("GRM Issue Type", payload, "type_name")
        print(f"  type: {nm}")

    # 6. ISSUE STATUSES
    for status_name, kind, final_state, rejected, init in ISSUE_STATUSES:
        payload = {
            "project": proj.name,
            "status_name": status_name,
            "open_status": 1 if kind == "open" else 0,
            "final_status": final_state,
            "rejected_status": rejected,
            "initial_status": init,
        }
        nm = _ensure("GRM Issue Status", payload, "status_name")
        print(f"  status: {nm}")

    # Mark Open as initial
    op = frappe.get_all(
        "GRM Issue Status",
        filters={"project": proj.name, "status_name": "Open"},
        fields=["name"], limit=1,
    )
    if op:
        frappe.db.set_value("GRM Issue Status", op[0].name, "initial_status", 1)

    # 7. DEPARTMENTS
    for dept in DEPARTMENTS:
        payload = {"project": proj.name, "department_name": dept}
        nm = _ensure("GRM Issue Department", payload, "department_name")
        print(f"  dept: {nm}")

    # 8. AGE GROUPS
    for ag in AGE_GROUPS:
        payload = {"project": proj.name, "age_group": ag}
        nm = _ensure("GRM Issue Age Group", payload, "age_group")
        print(f"  age: {nm}")

    # 9. CITIZEN GROUPS
    for grp_type, grp_name in CITIZEN_GROUPS:
        existing = frappe.get_all(
            "GRM Issue Citizen Group",
            filters={
                "project": proj.name,
                "group_name": grp_name,
                "group_type": grp_type,
            },
            fields=["name"], limit=1,
        )
        if existing:
            print(f"  cg exists: {grp_type}/{grp_name}")
            continue
        d = frappe.new_doc("GRM Issue Citizen Group")
        d.project = proj.name
        d.group_name = grp_name
        d.group_type = grp_type
        d.insert(ignore_permissions=True)
        print(f"  cg: {grp_type}/{grp_name}")

    frappe.db.commit()
    print(f"--- DONE seeding {PROJECT_CODE} ---")


def assign_users():
    """Attach the four test users to the RDAP project via GRM User Project Assignment."""
    project = PROJECT_CODE
    USERS = [
        ("project-admin@egrm.test", None, ["Rwanda PIU"], None),
        ("field-officer@egrm.test", None, ["Kigali City"], None),
        ("triage-officer@egrm.test", None, ["Rwanda PIU"], None),
        ("resolver@egrm.test", None, ["Kigali City"], None),
    ]

    for email, _role, regions, _dept in USERS:
        for region_name in regions:
            rg = frappe.get_all(
                "GRM Administrative Region",
                filters={"project": project, "region_name": region_name},
                fields=["name"], limit=1,
            )
            if not rg:
                continue
            existing = frappe.get_all(
                "GRM User Project Assignment",
                filters={"user": email, "project": project, "administrative_region": rg[0].name},
                fields=["name"], limit=1,
            )
            if existing:
                print(f"  assignment exists: {email} -> {region_name}")
                continue
            try:
                d = frappe.new_doc("GRM User Project Assignment")
                d.user = email
                d.project = project
                d.administrative_region = rg[0].name
                d.is_active = 1
                d.insert(ignore_permissions=True)
                print(f"  assigned: {email} -> {region_name}")
            except Exception as e:
                print(f"  skip {email} -> {region_name}: {e}")
    frappe.db.commit()
    print("--- DONE assigning users to RDAP ---")
