"""Desk and mobile must answer "which projects can this user see?" identically.

``egrm.api.sync`` used to carry its own copy of
``get_user_accessible_projects``. The two copies disagreed on which roles
bypass project scoping: the shared helper honours
``GRM_ALL_PROJECTS_ROLES`` (which includes ``GRM Supervise``), the sync
copy honoured only System Manager / GRM Platform Administrator. A
supervisor whose assignments were still ``Pending Activation`` therefore
saw issues on the desk and an empty screen in the mobile app, because
``pull_changes`` short-circuits on an empty project list.

These tests pin the two answers together so the copies cannot drift again.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.api.sync import get_user_accessible_projects as sync_accessible_projects
from egrm.utils.project_access import get_user_accessible_projects as desk_accessible_projects

PROJECT = "TEST-ACCESS-PARITY"
LEVEL_NAME = "AP-Province"
REGION_NAME = "AP-Region"
SUPERVISOR_ROLE = "AP-Supervisor"
FIELD_ROLE = "AP-Field"

SUPERVISOR = "ap.supervisor@example.com"
FIELD_PENDING = "ap.pending@example.com"
FIELD_ACTIVE = "ap.active@example.com"


def _ensure(doctype: str, filters: dict, payload: dict) -> str:
	if frappe.db.exists(doctype, filters):
		return frappe.db.get_value(doctype, filters, "name")
	return frappe.get_doc({**payload, "doctype": doctype}).insert(ignore_permissions=True).name


def _ensure_user(email: str, first_name: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	return email


class ProjectAccessParityTests(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure(
			"GRM Project",
			{"project_code": PROJECT},
			{"project_code": PROJECT, "title": "Access parity", "is_active": 1},
		)
		level = _ensure(
			"GRM Administrative Level Type",
			{"project": PROJECT, "level_name": LEVEL_NAME},
			{"project": PROJECT, "level_name": LEVEL_NAME, "level_order": 1},
		)
		cls.region = _ensure(
			"GRM Administrative Region",
			{"project": PROJECT, "region_name": REGION_NAME},
			{
				"project": PROJECT,
				"region_name": REGION_NAME,
				"administrative_level": level,
				"path": REGION_NAME,
			},
		)
		# Supervise is the duty that maps to the `GRM Supervise` Frappe role,
		# the one the two helpers disagreed about.
		cls.supervisor_role = _ensure(
			"GRM Project Role",
			{"project": PROJECT, "role_name": SUPERVISOR_ROLE},
			{
				"project": PROJECT,
				"role_name": SUPERVISOR_ROLE,
				"is_active": 1,
				"duties": [{"duty": "Intake"}, {"duty": "Supervise"}],
			},
		)
		cls.field_role = _ensure(
			"GRM Project Role",
			{"project": PROJECT, "role_name": FIELD_ROLE},
			{
				"project": PROJECT,
				"role_name": FIELD_ROLE,
				"is_active": 1,
				"duties": [{"duty": "Intake"}],
			},
		)

		for email, name in (
			(SUPERVISOR, "Supervisor"),
			(FIELD_PENDING, "Pending"),
			(FIELD_ACTIVE, "Active"),
		):
			_ensure_user(email, name)

		cls.assignments = {
			SUPERVISOR: cls._assign(SUPERVISOR, cls.supervisor_role, cls.region),
			FIELD_PENDING: cls._assign(FIELD_PENDING, cls.field_role, cls.region),
			FIELD_ACTIVE: cls._assign(FIELD_ACTIVE, cls.field_role, cls.region),
		}

		# Reproduce the reported account exactly: holds `GRM Supervise` while
		# every assignment is still Pending Activation. Granted directly
		# because a pending assignment does not itself grant duty roles.
		supervisor_doc = frappe.get_doc("User", SUPERVISOR)
		if "GRM Supervise" not in {r.role for r in supervisor_doc.roles}:
			supervisor_doc.append("roles", {"role": "GRM Supervise"})
			supervisor_doc.flags.ignore_permissions = True
			supervisor_doc.save(ignore_permissions=True)

		frappe.db.set_value(
			"GRM User Project Assignment",
			cls.assignments[FIELD_ACTIVE],
			{"activation_status": "Activated"},
			update_modified=False,
		)
		frappe.db.commit()

	@classmethod
	def _assign(cls, user: str, role: str, region: str) -> str:
		existing = frappe.db.get_value(
			"GRM User Project Assignment",
			{"user": user, "project": PROJECT, "role": role, "administrative_region": region},
		)
		if existing:
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "GRM User Project Assignment",
				"user": user,
				"project": PROJECT,
				"role": role,
				"administrative_region": region,
				"is_active": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_supervisor_with_pending_assignment_sees_same_projects_on_both_surfaces(self):
		"""The reported bug: desk said RDAP, mobile said nothing."""
		self.assertEqual(
			sync_accessible_projects(SUPERVISOR),
			desk_accessible_projects(SUPERVISOR),
			"mobile sync and desk disagree on project access for a GRM Supervise holder",
		)

	def test_activated_field_worker_sees_same_projects_on_both_surfaces(self):
		self.assertEqual(
			sync_accessible_projects(FIELD_ACTIVE),
			desk_accessible_projects(FIELD_ACTIVE),
		)
		self.assertIn(PROJECT, sync_accessible_projects(FIELD_ACTIVE))

	def test_pending_field_worker_is_denied_on_both_surfaces(self):
		"""Parity must not become "everyone sees everything": a plain worker
		who has not activated is still denied, on both surfaces."""
		self.assertEqual(sync_accessible_projects(FIELD_PENDING), [])
		self.assertEqual(desk_accessible_projects(FIELD_PENDING), [])

	def test_second_assignment_inherits_activation_no_second_code(self):
		"""Activating once per project covers later region assignments."""
		second_region = _ensure(
			"GRM Administrative Region",
			{"project": PROJECT, "region_name": REGION_NAME + "-2"},
			{
				"project": PROJECT,
				"region_name": REGION_NAME + "-2",
				"administrative_level": frappe.db.get_value(
					"GRM Administrative Level Type", {"project": PROJECT, "level_name": LEVEL_NAME}
				),
				"path": REGION_NAME + "-2",
			},
		)
		name = self._assign(FIELD_ACTIVE, self.field_role, second_region)
		doc = frappe.get_doc("GRM User Project Assignment", name)
		self.assertEqual(doc.activation_status, "Activated")
		self.assertFalse(doc.activation_code, "a second OTP was minted for an already-activated user")
