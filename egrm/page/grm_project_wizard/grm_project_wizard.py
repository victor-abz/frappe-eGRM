"""Server helpers for the Project Setup Wizard custom desk page."""

import frappe


@frappe.whitelist()
def activate_project(project: str) -> dict:
    """Flip GRM Project.is_setup_complete = 1 after validating prerequisites.

    Prerequisites:
      - At least one GRM Administrative Level Type defined for the project.
      - At least one GRM Project Role defined and active for the project.
    """
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
    return {"ok": True, "project": project}
