"""Phase C tests — existing-users list/edit/bulk endpoints.

Covers:
- ``list_project_users`` — pagination, search, role filter.
- ``update_assignment_field`` — allowlist enforcement + happy-path persist.
- ``bulk_update_assignments`` — partial failure shape.
- ``bulk_remove_assignments`` — happy-path delete.

Uses ``frappe.tests.utils.FrappeTestCase`` so the bench test runner
discovers it.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_assignments import (
    bulk_remove_assignments,
    bulk_update_assignments,
    list_project_users,
    update_assignment_field,
)

PROJECT_CODE = "TEST-USER-ASSIGN-A"
LEVEL_NAME = "Province"

ROLE_A = "TEST-USER-ASSIGN-A-Officer"
ROLE_B = "TEST-USER-ASSIGN-A-Supervisor"


def _delete_if_exists(doctype: str, name: str) -> None:
    if frappe.db.exists(doctype, name):
        try:
            frappe.delete_doc(
                doctype, name,
                force=True, delete_permanently=True, ignore_permissions=True,
            )
        except Exception:
            frappe.db.rollback()


class _Fixture:
    """Seeds 1 project + 1 level + 1 region + 2 roles + N users + N assignments."""

    project_code = PROJECT_CODE
    level_name = LEVEL_NAME
    region_name = "Test Region A"
    user_emails: list[str] = []
    assignment_names: list[str] = []
    role_a_name: str | None = None
    role_b_name: str | None = None

    @classmethod
    def seed(cls, n_users: int = 30) -> None:
        cls.teardown()

        if not frappe.db.exists("GRM Project", PROJECT_CODE):
            frappe.get_doc({
                "doctype": "GRM Project",
                "project_code": PROJECT_CODE,
                "title": "Test User Assignment Endpoints",
            }).insert(ignore_permissions=True)

        # Level + region
        level = frappe.get_doc({
            "doctype": "GRM Administrative Level Type",
            "project": PROJECT_CODE,
            "level_name": LEVEL_NAME,
            "level_order": 1,
        }).insert(ignore_permissions=True)

        region = frappe.get_doc({
            "doctype": "GRM Administrative Region",
            "region_name": cls.region_name,
            "project": PROJECT_CODE,
            "administrative_level": level.name,
        }).insert(ignore_permissions=True)
        cls._region_doc_name = region.name

        # Need a real GRM Duty for the role; "Supervise" is seeded in the
        # standard fixtures, so re-use that.
        duty = "Supervise" if frappe.db.exists("GRM Duty", "Supervise") else None

        role_a_doc = frappe.get_doc({
            "doctype": "GRM Project Role",
            "project": PROJECT_CODE,
            "role_name": ROLE_A,
            "is_active": 1,
            "duties": [{"duty": duty}] if duty else [],
        }).insert(ignore_permissions=True)
        cls.role_a_name = role_a_doc.name

        role_b_doc = frappe.get_doc({
            "doctype": "GRM Project Role",
            "project": PROJECT_CODE,
            "role_name": ROLE_B,
            "is_active": 1,
            "duties": [{"duty": duty}] if duty else [],
        }).insert(ignore_permissions=True)
        cls.role_b_name = role_b_doc.name

        cls.user_emails = []
        cls.assignment_names = []
        for i in range(n_users):
            email = f"test_user_assign_{i:02d}@example.com"
            if not frappe.db.exists("User", email):
                frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": "Test",
                    "last_name": f"User{i:02d}",
                    "send_welcome_email": 0,
                    "enabled": 1,
                }).insert(ignore_permissions=True)
            cls.user_emails.append(email)

            # Half on ROLE_A, half on ROLE_B for the role-filter test.
            chosen_role = role_a_doc.name if i % 2 == 0 else role_b_doc.name
            assn = frappe.get_doc({
                "doctype": "GRM User Project Assignment",
                "user": email,
                "project": PROJECT_CODE,
                "role": chosen_role,
                "administrative_region": region.name,
                "position_title": f"Position {i:02d}",
                "is_active": 1,
            }).insert(ignore_permissions=True)
            cls.assignment_names.append(assn.name)

        frappe.db.commit()

    @classmethod
    def teardown(cls) -> None:
        # Assignments first, then users, then roles, then region/level/project.
        for assn in frappe.get_all(
            "GRM User Project Assignment",
            filters={"project": PROJECT_CODE},
            pluck="name",
        ):
            _delete_if_exists("GRM User Project Assignment", assn)
        for email in list(cls.user_emails):
            _delete_if_exists("User", email)
        # Cover users seeded before this fixture ran (paranoid cleanup).
        for email in frappe.get_all(
            "User",
            filters=[["email", "like", "test_user_assign_%@example.com"]],
            pluck="name",
        ):
            _delete_if_exists("User", email)
        for role in frappe.get_all(
            "GRM Project Role",
            filters={"project": PROJECT_CODE},
            pluck="name",
        ):
            _delete_if_exists("GRM Project Role", role)
        for region in frappe.get_all(
            "GRM Administrative Region",
            filters={"project": PROJECT_CODE},
            pluck="name",
        ):
            _delete_if_exists("GRM Administrative Region", region)
        level_id = frappe.db.get_value(
            "GRM Administrative Level Type",
            {"project": PROJECT_CODE, "level_name": LEVEL_NAME},
            "name",
        )
        if level_id:
            _delete_if_exists("GRM Administrative Level Type", level_id)
        _delete_if_exists("GRM Project", PROJECT_CODE)
        cls.user_emails = []
        cls.assignment_names = []
        frappe.db.commit()


class ListProjectUsersTests(FrappeTestCase):
    """``list_project_users`` paginates, searches, and filters correctly."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _Fixture.seed(n_users=30)

    @classmethod
    def tearDownClass(cls) -> None:
        _Fixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")

    def test_list_project_users_paginates(self) -> None:
        result = list_project_users(project=PROJECT_CODE, start=0, limit=10)
        self.assertEqual(len(result["rows"]), 10)
        self.assertEqual(result["total"], 30)
        # Summary keys must always be present, even when zero.
        for key in ("active", "pending", "draft", "unmapped"):
            self.assertIn(key, result["summary"])

    def test_list_project_users_search_email(self) -> None:
        # The seeded emails contain "test_user_assign_05" — partial match.
        result = list_project_users(
            project=PROJECT_CODE, search="assign_05", start=0, limit=25,
        )
        self.assertGreaterEqual(len(result["rows"]), 1)
        for row in result["rows"]:
            self.assertIn("assign_05", (row.get("user_email") or "").lower())

    def test_list_project_users_filter_role(self) -> None:
        result = list_project_users(
            project=PROJECT_CODE, role=_Fixture.role_a_name, start=0, limit=50,
        )
        # 30 users, half on ROLE_A → 15 rows.
        self.assertEqual(result["total"], 15)
        for row in result["rows"]:
            self.assertEqual(row["role"], _Fixture.role_a_name)


class UpdateAssignmentFieldTests(FrappeTestCase):
    """``update_assignment_field`` enforces the allowlist + persists changes."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _Fixture.seed(n_users=4)

    @classmethod
    def tearDownClass(cls) -> None:
        _Fixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")

    def test_update_assignment_field_disallowed_fieldname_throws(self) -> None:
        target = _Fixture.assignment_names[0]
        with self.assertRaises(frappe.ValidationError) as ctx:
            update_assignment_field(name=target, fieldname="user", value="x@example.com")
        self.assertIn("not editable inline", str(ctx.exception))

    def test_update_assignment_field_role(self) -> None:
        target = _Fixture.assignment_names[0]
        # Pick the role NOT currently set so we can detect the change.
        current_role = frappe.db.get_value(
            "GRM User Project Assignment", target, "role",
        )
        new_role = (
            _Fixture.role_b_name
            if current_role == _Fixture.role_a_name
            else _Fixture.role_a_name
        )
        result = update_assignment_field(
            name=target, fieldname="role", value=new_role,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            frappe.db.get_value("GRM User Project Assignment", target, "role"),
            new_role,
        )


class BulkAssignmentTests(FrappeTestCase):
    """Bulk-update + bulk-remove behaviour, including partial failures.

    NOTE: ``FrappeTestCase`` rolls back transactions between test methods,
    so the per-method ``setUp`` re-seeds the fixture. This is slower but
    keeps each test independent.
    """

    @classmethod
    def tearDownClass(cls) -> None:
        _Fixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")
        _Fixture.seed(n_users=4)

    def test_bulk_update_assignments_partial_failure(self) -> None:
        # 2 valid names + 1 bogus → updated==2, errors has 1 entry.
        names = list(_Fixture.assignment_names[:2]) + ["NOT-A-REAL-ASSIGNMENT-XYZ"]
        result = bulk_update_assignments(
            names=names, fieldname="position_title", value="Bulk Updated",
        )
        self.assertEqual(result["updated"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["name"], "NOT-A-REAL-ASSIGNMENT-XYZ")
        # Verify the 2 good rows actually persisted the change.
        for n in _Fixture.assignment_names[:2]:
            self.assertEqual(
                frappe.db.get_value("GRM User Project Assignment", n, "position_title"),
                "Bulk Updated",
            )

    def test_bulk_remove_assignments_happy(self) -> None:
        names = list(_Fixture.assignment_names[:3])
        result = bulk_remove_assignments(names=names)
        self.assertEqual(result["removed"], 3)
        self.assertEqual(result["errors"], [])
        for n in names:
            self.assertFalse(frappe.db.exists("GRM User Project Assignment", n))
