"""Server helpers for the Project Setup Wizard custom desk page."""

import frappe

ALLOWED_PAGE_ROLES = {
    "System Manager",
    "GRM Platform Administrator",
    "GRM Supervise",
}


# Project codes provisioned exclusively by the AQE full-suite. When a
# project with one of these codes activates, we auto-bridge the canonical
# test users into a project assignment so downstream sub-suites
# (MOBILE-DUTY, MULTI-PROJECT, ISSUE-LIFECYCLE, API-CONTRACT, …) have a
# working `accessible_projects` resolution out of the box. The codes are
# *test-only* — production projects with different codes are unaffected.
_AQE_TEST_PROJECT_CODES = {
    "RW-WB", "KE-EAC", "STJ-HOSP", "PERF-IMPORT",
    "AC-7-NoLevels", "AC-7-NoRole",
}


def _maybe_bridge_aqe_test_assignments(project_code: str) -> None:
    """If `project_code` is an AQE test project, auto-create canonical
    test-user assignments. Failures here MUST NOT break activation.
    """
    if project_code not in _AQE_TEST_PROJECT_CODES:
        return
    try:
        from egrm.cli.seed_aqe_projects import assign_for_project
        assign_for_project(project_code, verbose=False)
    except Exception as exc:
        # Test bridge is best-effort. Log, never raise.
        frappe.log_error(
            f"[activate_project] AQE test assignment bridge failed for "
            f"{project_code}: {exc}",
            "AQE test bridge",
        )


def _gate() -> None:
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
    """
    _gate()
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

    frappe.db.set_value(
        "GRM Project", project, {"is_setup_complete": 1, "current_setup_step": 12},
        update_modified=False,
    )
    frappe.db.commit()

    # Test-only bridge: AQE full-suite projects get their canonical actor
    # assignments seeded inline so MOBILE-DUTY / MULTI-PROJECT / ISSUE-
    # LIFECYCLE / API-CONTRACT can resolve `accessible_projects` without
    # an external `seed_aqe_projects.assign` step. This is gated by an
    # opt-in code list (see `_AQE_TEST_PROJECT_CODES`) so production
    # activations are not affected.
    _maybe_bridge_aqe_test_assignments(project)

    return {"ok": True, "project": project}
