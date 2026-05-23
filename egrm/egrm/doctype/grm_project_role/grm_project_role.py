import frappe
from frappe.model.document import Document


class GRMProjectRole(Document):
    def validate(self) -> None:
        self._validate_project_role_unique()
        self._validate_at_least_one_duty()

    def _validate_project_role_unique(self) -> None:
        existing = frappe.db.exists(
            "GRM Project Role",
            {"project": self.project, "role_name": self.role_name, "name": ["!=", self.name]},
        )
        if existing:
            frappe.throw(
                frappe._("A role named {0} already exists in project {1}").format(self.role_name, self.project)
            )

    def _validate_at_least_one_duty(self) -> None:
        if not self.duties:
            frappe.throw(frappe._("A Project Role must have at least one duty assigned."))


def get_role_duties(role: str) -> list[str]:
    """Return duty_name list for a Project Role; empty list for missing roles."""
    if not role or not frappe.db.exists("GRM Project Role", role):
        return []
    return frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": role},
        pluck="duty",
    )
