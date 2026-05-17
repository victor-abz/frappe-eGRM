"""Server helpers for the Project Setup Wizard custom desk page."""

import frappe

ALLOWED_PAGE_ROLES = {
    "System Manager",
    "GRM Platform Administrator",
    "GRM Supervise",
}

# Kept in lock-step with grm_project_wizard.js TOTAL_STEPS — bump both together.
TOTAL_SETUP_STEPS = 13


_DEFAULT_STATUSES = (
    {"status_name": "New", "initial_status": 1},
    {"status_name": "In Progress", "open_status": 1},
    {"status_name": "Resolved", "final_status": 1},
    {"status_name": "Closed", "final_status": 1},
    {"status_name": "Rejected", "rejected_status": 1},
)
_DEFAULT_ISSUE_TYPES = ("Complaint", "Inquiry", "Feedback")
_DEFAULT_DEPARTMENT = "General"


def _has_project_link(doctype: str, name_field: str, value: str, project: str) -> bool:
    """True if a `doctype` row with `name_field=value` is linked to `project`."""
    return bool(
        frappe.db.sql(
            f"""
            SELECT 1
            FROM `tab{doctype}` d
            JOIN `tabGRM Project Link` pl
              ON pl.parent = d.name AND pl.parenttype = %s
            WHERE d.{name_field} = %s AND pl.project = %s
            LIMIT 1
            """,
            (doctype, value, project),
        )
    )


def _ensure_default_catalog(project: str) -> None:
    """Idempotently fill *missing* operational catalog slots for `project`.

    Called from ``activate_project`` so that a wizard run that skipped
    Step 12 (or the AQE walker which only walks Step 9) still produces a
    project that can serve public submissions, mobile sync, and the
    issue lifecycle.

    The rule is *fill, not duplicate*. The project's curated rows are
    reused; we only insert a default for a slot that's missing entirely:

      - Initial status   ─ seed "Open"     ONLY if no row has initial_status=1
      - Final status     ─ seed "Resolved" ONLY if no row has final_status=1
      - Rejected status  ─ seed "Rejected" ONLY if no row has rejected_status=1
      - Open status      ─ seed "In Progress" ONLY if no open_status=1 row exists
      - Issue type       ─ seed "Complaint"/"Inquiry"/"Feedback" by name,
                            but ONLY if the project has NO type linked
      - "General" dept   ─ seed by name (always available as a routing fallback)

    Inserting "Open" with initial_status=1 against a project whose
    curated initial status has a different name (e.g. STJ-HOSP's "New")
    used to trip ``GRMIssueStatus.validate_unique_type`` — the
    name-keyed `_has_project_link` check happily said "no Open here"
    while a different name *was* already the initial. The flag-keyed
    check below avoids that collision.
    """
    # Statuses — fill missing flag slots, never duplicate
    needs_initial = not _project_has_status_flag(project, "initial_status")
    needs_open = not _project_has_status_flag(project, "open_status")
    needs_final = not _project_has_status_flag(project, "final_status")
    needs_rejected = not _project_has_status_flag(project, "rejected_status")
    fill_map = {
        "initial_status": ("New", needs_initial),
        "open_status": ("In Progress", needs_open),
        "final_status": ("Resolved", needs_final),
        "rejected_status": ("Rejected", needs_rejected),
    }
    seeded_names: set[str] = set()
    for flag, (default_name, needed) in fill_map.items():
        if not needed:
            continue
        if default_name in seeded_names:
            continue
        # Skip if a row with this exact name (regardless of flags) is
        # already linked — `validate_unique_type` will reject any insert
        # that adds a second initial; we should *promote* the existing
        # row instead.
        if _has_project_link(
            "GRM Issue Status", "status_name", default_name, project
        ):
            existing_name = frappe.db.sql(
                """
                SELECT s.name FROM `tabGRM Issue Status` s
                JOIN `tabGRM Project Link` pl ON pl.parent = s.name
                WHERE pl.parenttype = 'GRM Issue Status'
                  AND s.status_name = %s AND pl.project = %s
                LIMIT 1
                """,
                (default_name, project),
            )
            if existing_name:
                frappe.db.set_value(
                    "GRM Issue Status", existing_name[0][0], flag, 1,
                    update_modified=False,
                )
            seeded_names.add(default_name)
            continue
        doc = frappe.new_doc("GRM Issue Status")
        doc.status_name = default_name
        setattr(doc, flag, 1)
        doc.append("grm_project_link", {"project": project})
        doc.flags.ignore_permissions = True
        doc.insert()
        seeded_names.add(default_name)

    # Issue types — only seed defaults if the project has none at all
    if not _project_has_any_link("GRM Issue Type", project):
        for type_name in _DEFAULT_ISSUE_TYPES:
            doc = frappe.new_doc("GRM Issue Type")
            doc.type_name = type_name
            doc.append("grm_project_link", {"project": project})
            doc.flags.ignore_permissions = True
            doc.insert()

    # Department — always make sure "General" exists as a routing fallback
    if not _has_project_link(
        "GRM Issue Department", "department_name", _DEFAULT_DEPARTMENT, project
    ):
        doc = frappe.new_doc("GRM Issue Department")
        doc.department_name = _DEFAULT_DEPARTMENT
        doc.append("grm_project_link", {"project": project})
        doc.flags.ignore_permissions = True
        doc.insert()


def _project_has_any_link(doctype: str, project: str) -> bool:
    """True if `project` already has at least one `doctype` row linked."""
    return bool(
        frappe.db.sql(
            """
            SELECT 1
            FROM `tabGRM Project Link` pl
            WHERE pl.parenttype = %s AND pl.project = %s
            LIMIT 1
            """,
            (doctype, project),
        )
    )


def _project_has_status_flag(project: str, flag: str) -> bool:
    """True if `project` already has a GRM Issue Status row with `flag`=1."""
    if flag not in {
        "initial_status", "open_status", "final_status", "rejected_status",
    }:
        # Defensive: never interpolate an arbitrary identifier into SQL.
        raise ValueError(f"unsupported status flag: {flag}")
    rows = frappe.db.sql(
        f"""
        SELECT 1
        FROM `tabGRM Issue Status` s
        JOIN `tabGRM Project Link` pl ON pl.parent = s.name
        WHERE pl.parenttype = 'GRM Issue Status'
          AND s.{flag} = 1
          AND pl.project = %s
        LIMIT 1
        """,
        (project,),
    )
    return bool(rows)


def _require_wizard_role() -> None:
    """Raise PermissionError unless caller has at least one allowed role.

    The page-level role list in ``grm_project_wizard.json`` only gates the
    desk UI; whitelisted endpoints must enforce the same role check, or any
    authenticated user could call them via RPC.
    """
    if not (set(frappe.get_roles(frappe.session.user)) & ALLOWED_PAGE_ROLES):
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def activate_project(project: str) -> dict:
    """Flip GRM Project.is_setup_complete = 1 after validating prerequisites.

    Prerequisites:
      - At least one GRM Administrative Level Type defined for the project.
      - At least one GRM Project Role defined and active for the project.

    Side-effect: idempotently seeds the minimum operational catalog
    (default Issue Statuses, Issue Types, Issue Department) for the
    project. The wizard's Step 12 lets a human curate these later, but
    skipping it MUST NOT leave the project in a state where downstream
    flows (public submit, mobile sync, FLOW chains) crash on the missing
    initial-status / department lookup. The seeding is no-op when the
    catalog already exists.
    """
    _require_wizard_role()
    if not project:
        frappe.throw(frappe._("project argument is required"))

    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} does not exist").format(project))

    issues: list[str] = []
    if not frappe.db.exists("GRM Administrative Level Type", {"project": project}):
        issues.append(frappe._("No administrative levels defined for this project."))
    if not frappe.db.exists(
        "GRM Project Role", {"project": project, "is_active": 1}
    ):
        issues.append(frappe._("No active Project Roles defined for this project."))

    if issues:
        frappe.throw("\n".join(issues))

    # Every region must have at least one user covering Intake, Review,
    # and Investigate & Resolve duties. Without this the lifecycle stalls
    # (citizen submissions route to a Resolver who can't be Accepted, or
    # to nobody at all).
    from egrm.services.duty_coverage import assert_full_coverage
    assert_full_coverage(project)

    _ensure_default_catalog(project)

    frappe.db.set_value(
        "GRM Project", project,
        {
            "is_setup_complete": 1,
            "is_active": 1,
            "current_setup_step": TOTAL_SETUP_STEPS,
        },
        update_modified=False,
    )
    frappe.db.commit()

    return {"ok": True, "project": project}


@frappe.whitelist()
def preview_duty_coverage(project: str) -> dict:
    """Return per-region duty-coverage gaps for the wizard UI.

    The wizard can render the result on Step 9 (Users) as a live preview
    so the operator sees which regions still need a user before they hit
    "Activate". This endpoint is read-only and does not mutate state.
    """
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    from egrm.services.duty_coverage import compute_coverage
    return compute_coverage(project)


@frappe.whitelist()
def preview_remove_regions(project: str, regions) -> dict:
    """Compute the exact impact of removing ``regions`` *without* deleting.

    Returns a per-target row describing what would be touched plus rolled-up
    totals, so the wizard can render an explicit confirm dialog like
    "Remove X regions + Y descendants, unassigning Z users".
    """
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    if isinstance(regions, str):
        regions = frappe.parse_json(regions) or []
    if not isinstance(regions, list):
        frappe.throw(frappe._("regions must be a list of region IDs"))

    def _collect_descendants(root: str) -> list[str]:
        out: list[str] = []
        frontier: list[str] = [root]
        seen: set[str] = {root}
        while frontier:
            children = frappe.get_all(
                "GRM Administrative Region",
                filters={"project": project, "parent_region": ("in", frontier)},
                pluck="name",
            )
            frontier = []
            for c in children:
                if c in seen:
                    continue
                seen.add(c)
                out.append(c)
                frontier.append(c)
        return out

    rows: list[dict] = []
    seen_targets: set[str] = set()
    total_regions = 0
    total_descendants = 0
    total_users = 0
    invalid: list[str] = []
    for r in regions:
        r = (r or "").strip()
        if not r or r in seen_targets:
            continue
        seen_targets.add(r)
        owner = frappe.db.get_value("GRM Administrative Region", r, ["project", "region_name"], as_dict=True)
        if not owner or owner.project != project:
            invalid.append(r)
            continue
        descendants = _collect_descendants(r)
        deletion_set = descendants + [r]
        users = frappe.get_all(
            "GRM User Project Assignment",
            filters={"project": project, "administrative_region": ("in", deletion_set), "is_active": 1},
            pluck="name",
        )
        rows.append({
            "region": r,
            "region_name": owner.region_name,
            "descendants": len(descendants),
            "users": len(users),
        })
        total_regions += 1
        total_descendants += len(descendants)
        total_users += len(users)

    return {
        "rows": rows,
        "totals": {
            "regions": total_regions,
            "descendants": total_descendants,
            "users": total_users,
        },
        "invalid": invalid,
    }


@frappe.whitelist()
def remove_regions(project: str, regions, cascade_users: bool = False) -> dict:
    """Bulk-delete ``GRM Administrative Region`` rows in ``project``.

    Used by the Step 9 coverage banner so the operator can drop scaffolding
    regions that have no users (and therefore block the activation gate).

    Pruning is *complete*: every descendant of a selected region is also
    deleted, so the project never ends up with orphan-parent regions.

    By default, if any region in the deletion set (selected or descendant)
    has active ``GRM User Project Assignment`` rows, the whole batch is
    aborted with ``has_active_users`` so the operator can confirm. When
    ``cascade_users`` is true (a second confirmation in the UI), those
    assignments are deleted first. Returns
    ``{"deleted": [...], "skipped": [...], "cascaded_users": N, "cascaded_regions": N}``.
    """
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))

    if isinstance(regions, str):
        regions = frappe.parse_json(regions) or []
    if not isinstance(regions, list):
        frappe.throw(frappe._("regions must be a list of region IDs"))
    if isinstance(cascade_users, str):
        cascade_users = cascade_users.lower() in ("1", "true", "yes")

    def _collect_descendants(root: str) -> list[str]:
        """BFS collect every descendant of ``root`` in this project."""
        out: list[str] = []
        frontier: list[str] = [root]
        seen: set[str] = {root}
        while frontier:
            parents = frontier
            frontier = []
            for batch_start in range(0, len(parents), 200):
                batch = parents[batch_start:batch_start + 200]
                children = frappe.get_all(
                    "GRM Administrative Region",
                    filters={"project": project, "parent_region": ("in", batch)},
                    pluck="name",
                )
                for c in children:
                    if c in seen:
                        continue
                    seen.add(c)
                    out.append(c)
                    frontier.append(c)
        return out

    deleted: list[str] = []
    skipped: list[dict] = []
    cascaded_users = 0
    cascaded_regions = 0

    for region in regions:
        region = (region or "").strip()
        if not region:
            continue
        owner = frappe.db.get_value("GRM Administrative Region", region, "project")
        if owner != project:
            skipped.append({"region": region, "reason": "not_in_project"})
            continue

        # Build the full deletion set: the region itself + every descendant.
        descendants = _collect_descendants(region)
        # Deepest-first: descendants are appended in BFS order, so reverse
        # the descendant list and put the selected region last to satisfy
        # any parent-FK checks Frappe might apply.
        deletion_order = list(reversed(descendants)) + [region]

        # Gather all active assignments in the deletion set in one pass.
        active_assignments = []
        if deletion_order:
            active_assignments = frappe.get_all(
                "GRM User Project Assignment",
                filters={
                    "project": project,
                    "administrative_region": ("in", deletion_order),
                    "is_active": 1,
                },
                pluck="name",
            )
        if active_assignments and not cascade_users:
            skipped.append({
                "region": region,
                "reason": "has_active_users",
                "descendants": len(descendants),
                "users": len(active_assignments),
            })
            continue

        for assignment in active_assignments:
            frappe.delete_doc(
                "GRM User Project Assignment", assignment,
                ignore_permissions=True, force=True, delete_permanently=True,
            )
            cascaded_users += 1

        for r in deletion_order:
            frappe.delete_doc(
                "GRM Administrative Region", r,
                ignore_permissions=True, force=True, delete_permanently=True,
            )
        deleted.append(region)
        cascaded_regions += len(descendants)

    frappe.db.commit()
    return {
        "deleted": deleted,
        "skipped": skipped,
        "cascaded_users": cascaded_users,
        "cascaded_regions": cascaded_regions,
    }


# ---------------------------------------------------------------------------
# Phase C — Admin Region bulk upload endpoints
# ---------------------------------------------------------------------------

from egrm.services.admin_region_importer import (
    parse_csv as _parse_admin_csv,
    import_csv as _import_admin_csv,
)


@frappe.whitelist()
def parse_admin_regions_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Validate-only preview of a region CSV. Does not write."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    return _parse_admin_csv(project=project, highest_level=highest_level, csv_text=csv_text)


@frappe.whitelist()
def bulk_insert_admin_regions(project: str, highest_level: str, csv_text: str) -> dict:
    """Validate + insert regions. Returns counts and any errors."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    return _import_admin_csv(project=project, highest_level=highest_level, csv_text=csv_text)


# ---------------------------------------------------------------------------
# Phase B.2 — Project Role grid endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
def project_role_add(
    project: str,
    role_name: str,
    admin_level: str | None = None,
    duties: list | str | None = None,
) -> dict:
    """Create a new GRM Project Role row.

    ``duties`` is a list of duty names (or a JSON-encoded list when posted
    via REST form-encoding) that MUST contain at least one entry. The role
    is created with those duties attached atomically. We do NOT default to
    a placeholder duty: silently injecting one would pollute the role with
    an unintended responsibility (the doctype's
    ``_validate_at_least_one_duty`` would still pass but the operator's
    intent is lost). Callers must collect the duty list up-front.
    """
    _require_wizard_role()
    project = (project or "").strip()
    role_name = (role_name or "").strip()
    if not project or not role_name:
        frappe.throw(frappe._("project and role_name are required"))
    if frappe.db.exists("GRM Project Role", {"project": project, "role_name": role_name}):
        frappe.throw(frappe._("A role named {0} already exists for this project.").format(role_name))
    if isinstance(duties, str):
        import json as _json
        try:
            duties = _json.loads(duties or "[]")
        except Exception:
            frappe.throw(frappe._("duties must be a JSON-encoded list of duty names"))
    if not duties:
        frappe.throw(frappe._("Pick at least one duty for this role."))
    doc = frappe.get_doc({
        "doctype": "GRM Project Role",
        "project": project,
        "role_name": role_name,
        "admin_level": admin_level or None,
        "is_active": 1,
        "duties": [{"duty": d} for d in duties],
    }).insert()
    return {"name": doc.name, "role_name": doc.role_name}


@frappe.whitelist()
def project_role_toggle_duty(role: str, duty: str, value: int) -> dict:
    """Add or remove a single duty on a Project Role. Idempotent."""
    _require_wizard_role()
    role = (role or "").strip()
    duty = (duty or "").strip()
    if not role or not duty:
        frappe.throw(frappe._("role and duty are required"))
    doc = frappe.get_doc("GRM Project Role", role)
    existing = {d.duty for d in (doc.duties or [])}
    want = bool(int(value))
    if want and duty not in existing:
        doc.append("duties", {"duty": duty})
        doc.save()
    elif not want and duty in existing:
        doc.duties = [d for d in doc.duties if d.duty != duty]
        doc.save()
    return {"role": role, "duty": duty, "value": 1 if want else 0}


@frappe.whitelist()
def project_role_delete(role: str) -> dict:
    """Delete a Project Role (only if no users currently bound)."""
    _require_wizard_role()
    role = (role or "").strip()
    if not role:
        frappe.throw(frappe._("role is required"))
    bound = frappe.db.count("GRM Government Worker", {"project_role": role})
    if bound:
        frappe.throw(frappe._("Cannot delete: {0} user(s) currently use this role.").format(bound))
    frappe.delete_doc("GRM Project Role", role)
    return {"deleted": role}


@frappe.whitelist()
def project_role_seed_defaults(project: str) -> dict:
    """Idempotently insert any missing default project roles for this project.

    Default roles are derived from the universal duty catalog (GRM Duty) — one
    role per lifecycle phase, mirroring the legacy GRM_DEFAULT_DUTIES list in
    the wizard JS. Existing roles are left untouched.
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(frappe._("project is required"))

    defaults = [
        ("Intake Officer",        ["Intake"]),
        ("Review Officer",        ["Review"]),
        ("Assignment Officer",    ["Assignment"]),
        ("Investigation Officer", ["Investigate & Resolve"]),
        ("Feedback Officer",      ["Feedback"]),
        ("Supervisor",            ["Supervise"]),
    ]
    added: list[str] = []
    for role_name, duty_names in defaults:
        if frappe.db.exists("GRM Project Role", {"project": project, "role_name": role_name}):
            continue
        doc = frappe.get_doc({
            "doctype": "GRM Project Role",
            "project": project,
            "role_name": role_name,
            "is_active": 1,
            "duties": [{"duty": d} for d in duty_names if frappe.db.exists("GRM Duty", d)],
        }).insert()
        added.append(doc.name)
    return {"added": added, "count": len(added)}


# ---------------------------------------------------------------------------
# Phase D — Government Worker bulk creation endpoints
# ---------------------------------------------------------------------------

from egrm.services.government_worker_importer import (
    auto_generate_per_region as _auto_generate_per_region,
    bulk_create_from_csv as _bulk_create_from_csv,
    export_activation_codes as _export_codes,
    parse_users_csv as _parse_users_csv,
)

_USER_TEMPLATE_HEADERS = "first_name,last_name,position,region,phone,email\n"
_USER_TEMPLATE_SAMPLE = (
    "Alice,Mukamana,Field Officer,Kacyiru,+250788000001,\n"
    "Bob,Habimana,Field Officer,Remera,+250788000002,bob@example.org\n"
)


@frappe.whitelist()
def parse_users_csv(project: str, csv_text: str) -> dict:
    """Validate-only preview of a worker CSV. Does not write."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    return _parse_users_csv(project=project, csv_text=csv_text)


@frappe.whitelist()
def bulk_create_users(
    project: str, csv_text: str, default_password: str | None = None
) -> dict:
    """Insert workers from CSV. Returns counts + activation codes."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    return _bulk_create_from_csv(
        project=project, csv_text=csv_text, default_password=default_password
    )


@frappe.whitelist()
def auto_generate_regional_users(
    project: str, level_type: str, position_template: str = "{level}_officer"
) -> dict:
    """Auto-generate one Field Officer per region at the given administrative level."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    if not (level_type or "").strip():
        frappe.throw(frappe._("level_type is required"))
    return _auto_generate_per_region(
        project=project, level_type=level_type, position_template=position_template
    )


@frappe.whitelist()
def export_activation_codes(project: str) -> str:
    """Return CSV text of all activation codes for the project."""
    _require_wizard_role()
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))
    return _export_codes(project=project)


# ---------------------------------------------------------------------------
# Phase E — Step 10 Issue Routing Finalization
# ---------------------------------------------------------------------------


@frappe.whitelist()
def update_category_routing(
    project: str, category: str, target_type: str, target: str
) -> dict:
    """Set routing target on an issue category.

    Args:
        project: GRM Project name. Used to verify the category belongs here.
        category: GRM Issue Category name (the row being updated).
        target_type: Must be ``"Role"`` — department routing is no longer
            supported.
        target: GRM Project Role name.
    """
    _require_wizard_role()
    if target_type != "Role":
        frappe.throw(frappe._(
            "Only Role routing is supported. Update the category to route to a Role."
        ))
    if not (project and category and target):
        frappe.throw(frappe._("project, category, and target are required"))

    cat = frappe.get_doc("GRM Issue Category", category)
    if cat.project != project:
        frappe.throw(frappe._("Category does not belong to this project"))

    cat.routing_target_type = "Role"
    cat.assigned_role = target
    cat.assigned_department = None
    cat.save(ignore_permissions=True)
    return {
        "category": category,
        "routing_target_type": "Role",
        "target": target,
    }


@frappe.whitelist()
def export_user_template() -> str:
    """Return a CSV template for the bulk users upload tab.

    Bound to a whitelisted method (NOT the existing click command
    ``generate_worker_template`` — click commands cannot be served via
    ``/api/method/``). Returns the CSV body as a plain string; the
    Frappe HTTP layer wraps it in JSON ``message``. The wizard JS pulls
    ``response.message`` and writes it to a Blob for download.
    """
    _require_wizard_role()
    return _USER_TEMPLATE_HEADERS + _USER_TEMPLATE_SAMPLE


# ---------------------------------------------------------------------------
# Phase F — Step 12 default Issue Status seeding
# ---------------------------------------------------------------------------

# Default status set covers the standard GRM lifecycle pattern referenced in
# the Step 12 intro copy ("New" → "In Progress" → "Resolved" → "Closed", plus
# "Rejected" for dismissed cases). Idempotent — only inserts statuses missing
# for the project.
_DEFAULT_ISSUE_STATUSES = [
    {"status_name": "New",         "initial_status": 1, "open_status": 0, "final_status": 0, "rejected_status": 0},
    {"status_name": "In Progress", "initial_status": 0, "open_status": 1, "final_status": 0, "rejected_status": 0},
    {"status_name": "Resolved",    "initial_status": 0, "open_status": 0, "final_status": 1, "rejected_status": 0},
    {"status_name": "Closed",      "initial_status": 0, "open_status": 0, "final_status": 1, "rejected_status": 0},
    {"status_name": "Rejected",    "initial_status": 0, "open_status": 0, "final_status": 0, "rejected_status": 1},
]


@frappe.whitelist()
def issue_status_seed_defaults(project: str) -> dict:
    """Idempotently seed default Issue Statuses for a project.

    Only inserts statuses whose name is not already present for this project.
    Returns the list of inserted names (so the wizard can show a toast).
    """
    _require_wizard_role()
    project = (project or "").strip()
    if not project:
        frappe.throw(frappe._("project is required"))
    if not frappe.db.exists("GRM Project", project):
        frappe.throw(frappe._("Project {0} not found").format(project))

    existing = {
        (row.status_name or "").lower()
        for row in frappe.db.sql(
            """
            SELECT s.status_name
            FROM `tabGRM Issue Status` s
            JOIN `tabGRM Project Link` l ON l.parent = s.name AND l.parenttype = 'GRM Issue Status'
            WHERE l.project = %s
            """,
            (project,),
            as_dict=True,
        )
    }

    added: list[str] = []
    for spec in _DEFAULT_ISSUE_STATUSES:
        if spec["status_name"].lower() in existing:
            continue
        doc = frappe.get_doc({
            "doctype": "GRM Issue Status",
            **spec,
            "grm_project_link": [{"project": project}],
        }).insert()
        added.append(doc.name)
    return {"added": added, "count": len(added)}


# ---------------------------------------------------------------------------
# Phase A + B + C (Step 9 redesign) — bulk-user mapper + Data Import wrappers
#                                     + existing-users list/edit/bulk
# ---------------------------------------------------------------------------
# Endpoints are split across three helper modules to keep each <= 400 lines
# (plan §Engineering Conventions clause 4):
#   - `grm_project_wizard_user_import`        — Phase A introspection
#   - `grm_project_wizard_user_data_import`   — Phase B Data Import wrappers
#   - `grm_project_wizard_user_assignments`   — Phase C list/edit/bulk
# Re-exported here so frontend RPC paths stay stable.
from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_import import (  # noqa: E402, F401
    get_assignment_field_meta,
    auto_detect_user_import_mapping,
)
from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import import (  # noqa: E402, F401
    prepare_user_import,
    start_user_import,
    poll_user_import,
    download_user_template,
)
from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_assignments import (  # noqa: E402, F401
    list_project_users,
    update_assignment_field,
    bulk_update_assignments,
    bulk_remove_assignments,
)
from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_create import (  # noqa: E402, F401
    create_assignment,
)
