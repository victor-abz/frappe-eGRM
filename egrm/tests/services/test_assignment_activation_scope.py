"""Activation is scoped to (user, project), not to each assignment row.

A government worker assigned to several regions on one project must complete a
single OTP exchange. Before this behaviour existed, every row minted its own
code while ``activate_government_worker`` resolves exactly one assignment per
call, leaving the rest permanently ``Pending Activation`` — and since mobile
sync, region lookup and issue filtering all require ``Activated``, such a user
saw no projects at all.

Covers:
- second region reuses the first region's outstanding code
- redeeming that code cascades activation to every sibling row
- a region added after activation is activated on insert, with no new code
- a suspended project account does not get a fresh code via a new region
- assignments on a *different* project keep their own independent code
"""

from __future__ import annotations

from typing import ClassVar

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.api.activation import activate_government_worker

PROJECT_CODE = "TEST-ACTIVATION-SCOPE"
OTHER_PROJECT_CODE = "TEST-ACTIVATION-SCOPE-2"
LEVEL_NAME = "Province"
ROLE_NAME = "TEST-ACTIVATION-SCOPE-Officer"
USER_EMAIL = "test_activation_scope@example.com"

# ``is_government_worker_role`` gates on these duties plus a region.
GOV_DUTIES = ["Intake", "Investigate & Resolve"]


def _delete_if_exists(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		try:
			frappe.delete_doc(
				doctype,
				name,
				force=True,
				delete_permanently=True,
				ignore_permissions=True,
			)
		except Exception:
			frappe.db.rollback()


class TestAssignmentActivationScope(FrappeTestCase):
	regions: ClassVar[dict[str, str]] = {}
	role_name: str | None = None
	other_role_name: str | None = None
	other_region: str | None = None

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls._teardown()
		cls._seed()

	@classmethod
	def tearDownClass(cls) -> None:
		cls._teardown()
		super().tearDownClass()

	# ---------------------------------------------------------------- fixtures

	@classmethod
	def _seed_project(cls, project_code: str) -> tuple[str, str]:
		"""Create project + level + one region. Returns (role, region)."""
		if not frappe.db.exists("GRM Project", project_code):
			frappe.get_doc(
				{
					"doctype": "GRM Project",
					"project_code": project_code,
					"title": f"Activation scope {project_code}",
				}
			).insert(ignore_permissions=True)

		level = frappe.get_doc(
			{
				"doctype": "GRM Administrative Level Type",
				"project": project_code,
				"level_name": LEVEL_NAME,
				"level_order": 1,
			}
		).insert(ignore_permissions=True)

		duties = [{"duty": d} for d in GOV_DUTIES if frappe.db.exists("GRM Duty", d)]
		role = frappe.get_doc(
			{
				"doctype": "GRM Project Role",
				"project": project_code,
				"role_name": f"{project_code}-Officer",
				"is_active": 1,
				"duties": duties,
			}
		).insert(ignore_permissions=True)

		region = frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"region_name": f"{project_code} Region 1",
				"project": project_code,
				"administrative_level": level.name,
			}
		).insert(ignore_permissions=True)

		return role.name, region.name

	@classmethod
	def _seed(cls) -> None:
		if not frappe.db.exists("User", USER_EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER_EMAIL,
					"first_name": "Activation",
					"last_name": "Scope",
					"send_welcome_email": 0,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)

		cls.role_name, first_region = cls._seed_project(PROJECT_CODE)
		cls.regions = {"a": first_region}

		level_name = frappe.db.get_value(
			"GRM Administrative Level Type",
			{"project": PROJECT_CODE, "level_name": LEVEL_NAME},
			"name",
		)
		for key, label in (("b", "Region 2"), ("c", "Region 3")):
			region = frappe.get_doc(
				{
					"doctype": "GRM Administrative Region",
					"region_name": f"{PROJECT_CODE} {label}",
					"project": PROJECT_CODE,
					"administrative_level": level_name,
				}
			).insert(ignore_permissions=True)
			cls.regions[key] = region.name

		cls.other_role_name, cls.other_region = cls._seed_project(OTHER_PROJECT_CODE)
		frappe.db.commit()

	@classmethod
	def _teardown(cls) -> None:
		for project_code in (PROJECT_CODE, OTHER_PROJECT_CODE):
			for assn in frappe.get_all(
				"GRM User Project Assignment",
				filters={"project": project_code},
				pluck="name",
			):
				_delete_if_exists("GRM User Project Assignment", assn)
		_delete_if_exists("User", USER_EMAIL)
		for project_code in (PROJECT_CODE, OTHER_PROJECT_CODE):
			for role in frappe.get_all("GRM Project Role", filters={"project": project_code}, pluck="name"):
				_delete_if_exists("GRM Project Role", role)
			for region in frappe.get_all(
				"GRM Administrative Region",
				filters={"project": project_code},
				pluck="name",
			):
				_delete_if_exists("GRM Administrative Region", region)
			for level in frappe.get_all(
				"GRM Administrative Level Type",
				filters={"project": project_code},
				pluck="name",
			):
				_delete_if_exists("GRM Administrative Level Type", level)
			_delete_if_exists("GRM Project", project_code)
		frappe.db.commit()

	def setUp(self) -> None:
		super().setUp()
		for assn in frappe.get_all(
			"GRM User Project Assignment",
			filters={"user": USER_EMAIL},
			pluck="name",
		):
			_delete_if_exists("GRM User Project Assignment", assn)

	# ----------------------------------------------------------------- helpers

	def _assign(self, region: str, project: str | None = None, role: str | None = None):
		return frappe.get_doc(
			{
				"doctype": "GRM User Project Assignment",
				"user": USER_EMAIL,
				"project": project or PROJECT_CODE,
				"role": role or self.role_name,
				"administrative_region": region,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)

	def _statuses(self, project: str = PROJECT_CODE) -> list[str]:
		return frappe.get_all(
			"GRM User Project Assignment",
			filters={"user": USER_EMAIL, "project": project},
			pluck="activation_status",
		)

	# ------------------------------------------------------------------- tests

	def test_second_region_reuses_the_outstanding_code(self):
		first = self._assign(self.regions["a"])
		second = self._assign(self.regions["b"])

		self.assertEqual(first.activation_status, "Pending Activation")
		self.assertTrue(first.activation_code)
		self.assertEqual(second.activation_status, "Pending Activation")
		self.assertEqual(
			second.activation_code,
			first.activation_code,
			"a second region must share the project's outstanding OTP",
		)

	def test_activation_cascades_to_every_region_on_the_project(self):
		first = self._assign(self.regions["a"])
		self._assign(self.regions["b"])
		self._assign(self.regions["c"])

		result = activate_government_worker(USER_EMAIL, first.activation_code)

		self.assertTrue(result["success"], result)
		statuses = self._statuses()
		self.assertEqual(len(statuses), 3)
		self.assertEqual(
			statuses,
			["Activated"] * 3,
			"one OTP must clear every region on the project",
		)

	def test_region_added_after_activation_needs_no_new_code(self):
		first = self._assign(self.regions["a"])
		activate_government_worker(USER_EMAIL, first.activation_code)

		later = self._assign(self.regions["b"])

		self.assertEqual(later.activation_status, "Activated")
		self.assertFalse(
			later.activation_code,
			"an already-activated account must not mint another OTP",
		)

	def test_new_region_does_not_bypass_a_suspended_account(self):
		first = self._assign(self.regions["a"])
		first.db_set("activation_status", "Suspended", update_modified=False)

		later = self._assign(self.regions["b"])

		self.assertEqual(later.activation_status, "Suspended")
		self.assertFalse(later.activation_code)

	def test_other_project_keeps_an_independent_code(self):
		first = self._assign(self.regions["a"])
		other = self._assign(
			self.other_region,
			project=OTHER_PROJECT_CODE,
			role=self.other_role_name,
		)

		self.assertNotEqual(
			other.activation_code,
			first.activation_code,
			"activation is scoped per project, not across all of a user's work",
		)

		activate_government_worker(USER_EMAIL, first.activation_code)

		self.assertEqual(
			frappe.db.get_value("GRM User Project Assignment", other.name, "activation_status"),
			"Pending Activation",
			"cascade must not cross a project boundary",
		)
