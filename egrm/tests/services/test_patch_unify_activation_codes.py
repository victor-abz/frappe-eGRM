"""Patch coverage: unify_activation_codes_per_project.

The patch has to leave every user who was stranded by the per-row activation
bug in a state they can actually recover from on the next ``bench migrate`` —
one live code per (user, project), or outright activated when the account had
already proved itself.

Covers:
- a group with an activated member has its remaining rows activated
- a group whose codes are all live converges on the live one
- a group whose codes have ALL lapsed gets one fresh, live code
- a single-assignment user is left alone (never affected by the bug)
- re-running the patch is a no-op
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now, now_datetime

from egrm.patches.v16_0.unify_activation_codes_per_project import execute as run_patch

PROJECT_CODE = "TEST-UNIFY-PATCH"
LEVEL_NAME = "Province"


def _delete_if_exists(doctype: str, name: str) -> None:
    if frappe.db.exists(doctype, name):
        try:
            frappe.delete_doc(
                doctype, name,
                force=True, delete_permanently=True, ignore_permissions=True,
            )
        except Exception:
            frappe.db.rollback()


class TestUnifyActivationCodesPatch(FrappeTestCase):
    role_name: str | None = None
    regions: list[str] = []
    emails: list[str] = []

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._teardown()

        if not frappe.db.exists("GRM Project", PROJECT_CODE):
            frappe.get_doc({
                "doctype": "GRM Project",
                "project_code": PROJECT_CODE,
                "title": "Unify activation codes patch",
            }).insert(ignore_permissions=True)

        level = frappe.get_doc({
            "doctype": "GRM Administrative Level Type",
            "project": PROJECT_CODE,
            "level_name": LEVEL_NAME,
            "level_order": 1,
        }).insert(ignore_permissions=True)

        duties = [
            {"duty": d}
            for d in ("Intake", "Investigate & Resolve")
            if frappe.db.exists("GRM Duty", d)
        ]
        role = frappe.get_doc({
            "doctype": "GRM Project Role",
            "project": PROJECT_CODE,
            "role_name": f"{PROJECT_CODE}-Officer",
            "is_active": 1,
            "duties": duties,
        }).insert(ignore_permissions=True)
        cls.role_name = role.name

        cls.regions = []
        for i in range(3):
            region = frappe.get_doc({
                "doctype": "GRM Administrative Region",
                "region_name": f"{PROJECT_CODE} R{i}",
                "project": PROJECT_CODE,
                "administrative_level": level.name,
            }).insert(ignore_permissions=True)
            cls.regions.append(region.name)

        frappe.db.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._teardown()
        super().tearDownClass()

    @classmethod
    def _teardown(cls) -> None:
        for assn in frappe.get_all(
            "GRM User Project Assignment",
            filters={"project": PROJECT_CODE},
            pluck="name",
        ):
            _delete_if_exists("GRM User Project Assignment", assn)
        for email in frappe.get_all(
            "User",
            filters=[["email", "like", "unify_patch_%@example.com"]],
            pluck="name",
        ):
            _delete_if_exists("User", email)
        for dt in (
            "GRM Project Role",
            "GRM Administrative Region",
            "GRM Administrative Level Type",
        ):
            for name in frappe.get_all(
                dt, filters={"project": PROJECT_CODE}, pluck="name"
            ):
                _delete_if_exists(dt, name)
        _delete_if_exists("GRM Project", PROJECT_CODE)
        frappe.db.commit()

    def setUp(self) -> None:
        super().setUp()
        for assn in frappe.get_all(
            "GRM User Project Assignment",
            filters={"project": PROJECT_CODE},
            pluck="name",
        ):
            _delete_if_exists("GRM User Project Assignment", assn)

    # ----------------------------------------------------------------- helpers

    def _user(self, tag: str) -> str:
        email = f"unify_patch_{tag}@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": "Unify",
                "last_name": tag,
                "send_welcome_email": 0,
                "enabled": 1,
            }).insert(ignore_permissions=True)
        return email

    def _assign(self, email: str, region: str) -> str:
        doc = frappe.get_doc({
            "doctype": "GRM User Project Assignment",
            "user": email,
            "project": PROJECT_CODE,
            "role": self.role_name,
            "administrative_region": region,
            "is_active": 1,
        }).insert(ignore_permissions=True)
        return doc.name

    def _force(self, name: str, **values) -> None:
        """Write raw state, bypassing the new before_insert behaviour, to
        reproduce rows as they exist on a pre-fix database."""
        frappe.db.set_value(
            "GRM User Project Assignment", name, values, update_modified=False
        )

    def _rows(self, email: str) -> list:
        return frappe.get_all(
            "GRM User Project Assignment",
            filters={"user": email, "project": PROJECT_CODE},
            fields=[
                "name",
                "activation_status",
                "activation_code",
                "activation_expires_on",
            ],
        )

    # ------------------------------------------------------------------- tests

    def test_group_with_an_activated_member_activates_the_rest(self):
        email = self._user("activated")
        names = [self._assign(email, r) for r in self.regions]
        self._force(names[0], activation_status="Activated")
        for name in names[1:]:
            self._force(name, activation_status="Pending Activation")

        run_patch()

        statuses = [r.activation_status for r in self._rows(email)]
        self.assertEqual(statuses, ["Activated"] * 3)

    def test_group_with_live_codes_converges_on_the_live_one(self):
        email = self._user("live")
        names = [self._assign(email, r) for r in self.regions]
        far = add_to_date(now(), hours=40)
        near = add_to_date(now(), hours=10)
        self._force(names[0], activation_code="111111",
                    activation_expires_on=near,
                    activation_status="Pending Activation")
        self._force(names[1], activation_code="222222",
                    activation_expires_on=far,
                    activation_status="Pending Activation")
        self._force(names[2], activation_code="333333",
                    activation_expires_on=near,
                    activation_status="Pending Activation")

        run_patch()

        rows = self._rows(email)
        self.assertEqual(
            {r.activation_code for r in rows},
            {"222222"},
            "the latest-expiring live code should win",
        )

    def test_group_with_all_codes_lapsed_gets_one_fresh_live_code(self):
        email = self._user("expired")
        names = [self._assign(email, r) for r in self.regions]
        lapsed = add_to_date(now(), hours=-72)
        for i, name in enumerate(names):
            self._force(name, activation_code=f"9999{i:02d}",
                        activation_expires_on=lapsed,
                        activation_status="Expired")

        run_patch()

        rows = self._rows(email)
        codes = {r.activation_code for r in rows}
        self.assertEqual(len(codes), 1, "group must share exactly one code")
        self.assertNotIn(
            codes.pop(),
            {"999900", "999901", "999902"},
            "a lapsed code must be replaced, not merely unified",
        )
        for row in rows:
            self.assertEqual(row.activation_status, "Pending Activation")
            self.assertGreater(
                get_datetime(row.activation_expires_on),
                now_datetime(),
                "the reissued code must actually be redeemable",
            )

    def test_single_assignment_user_is_untouched(self):
        email = self._user("single")
        name = self._assign(email, self.regions[0])
        lapsed = add_to_date(now(), hours=-72)
        self._force(name, activation_code="555555",
                    activation_expires_on=lapsed,
                    activation_status="Expired")

        run_patch()

        row = self._rows(email)[0]
        self.assertEqual(row.activation_code, "555555")
        self.assertEqual(row.activation_status, "Expired")

    def test_rerunning_the_patch_changes_nothing(self):
        email = self._user("idempotent")
        names = [self._assign(email, r) for r in self.regions]
        lapsed = add_to_date(now(), hours=-72)
        for i, name in enumerate(names):
            self._force(name, activation_code=f"8888{i:02d}",
                        activation_expires_on=lapsed,
                        activation_status="Expired")

        run_patch()
        first = {r.name: (r.activation_code, r.activation_status)
                 for r in self._rows(email)}

        run_patch()
        second = {r.name: (r.activation_code, r.activation_status)
                  for r in self._rows(email)}

        self.assertEqual(first, second)
