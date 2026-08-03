"""Signing in activates a worker's pending assignments.

The OTP proves the person holds the account. So does logging in. Requiring
both stranded imported workers: their rows stayed ``Pending Activation``,
and every project-scoped query (mobile sync, region lookup, issue
filtering) requires ``Activated`` — so they signed in successfully and
then saw an empty app.

``Suspended`` is not an unfinished signup, it is an admin block, and must
survive a login.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.utils.login_activation import activate_pending_assignments_on_login

PROJECT = "TEST-LOGIN-ACTIVATION"
LEVEL_NAME = "LA-Province"
REGION_NAME = "LA-Region"
ROLE_NAME = "LA-Field"

PENDING_USER = "la.pending@example.com"
SUSPENDED_USER = "la.suspended@example.com"
EXPIRED_USER = "la.expired@example.com"


def _ensure(doctype: str, filters: dict, payload: dict) -> str:
	if frappe.db.exists(doctype, filters):
		return frappe.db.get_value(doctype, filters, "name")
	return frappe.get_doc({**payload, "doctype": doctype}).insert(ignore_permissions=True).name


class ActivateOnLoginTests(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure(
			"GRM Project",
			{"project_code": PROJECT},
			{"project_code": PROJECT, "title": "Login activation", "is_active": 1},
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
		cls.region_two = _ensure(
			"GRM Administrative Region",
			{"project": PROJECT, "region_name": REGION_NAME + "-2"},
			{
				"project": PROJECT,
				"region_name": REGION_NAME + "-2",
				"administrative_level": level,
				"path": REGION_NAME + "-2",
			},
		)
		cls.role = _ensure(
			"GRM Project Role",
			{"project": PROJECT, "role_name": ROLE_NAME},
			{
				"project": PROJECT,
				"role_name": ROLE_NAME,
				"is_active": 1,
				"duties": [{"duty": "Intake"}],
			},
		)

		for email in (PENDING_USER, SUSPENDED_USER, EXPIRED_USER):
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"enabled": 1,
						"user_type": "System User",
						"send_welcome_email": 0,
					}
				).insert(ignore_permissions=True)

		# Two regions for the pending user, mirroring the multi-region
		# accounts that motivated this: one login must cover both.
		cls.pending = [
			cls._assign(PENDING_USER, cls.region),
			cls._assign(PENDING_USER, cls.region_two),
		]
		cls.suspended = cls._assign(SUSPENDED_USER, cls.region)
		cls.expired = cls._assign(EXPIRED_USER, cls.region)

		cls._reset_fixture_state()

	@classmethod
	def _reset_fixture_state(cls):
		"""Put the fixtures back into their pre-login state.

		The code under test commits, which defeats FrappeTestCase's per-test
		rollback — so without an explicit reset these rows stay Activated and
		every assertion here passes vacuously on the second run onwards.
		"""
		for name in cls.pending:
			frappe.db.set_value(
				"GRM User Project Assignment",
				name,
				{"activation_status": "Pending Activation", "activation_code": "535263"},
				update_modified=False,
			)
		frappe.db.set_value(
			"GRM User Project Assignment",
			cls.suspended,
			"activation_status",
			"Suspended",
			update_modified=False,
		)
		frappe.db.set_value(
			"GRM User Project Assignment",
			cls.expired,
			"activation_status",
			"Expired",
			update_modified=False,
		)

		# Same reason: the duty role granted by a previous run would make
		# test_login_grants_the_duty_roles pass without doing anything.
		user = frappe.get_doc("User", PENDING_USER)
		kept = [r.role for r in user.roles if r.role != "GRM Intake"]
		if len(kept) != len(user.roles):
			user.set("roles", [{"role": r} for r in kept])
			user.flags.ignore_permissions = True
			user.save(ignore_permissions=True)
		frappe.db.commit()

	def setUp(self):
		super().setUp()
		self._reset_fixture_state()

	@classmethod
	def _assign(cls, user: str, region: str) -> str:
		existing = frappe.db.get_value(
			"GRM User Project Assignment",
			{"user": user, "project": PROJECT, "role": cls.role, "administrative_region": region},
		)
		if existing:
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "GRM User Project Assignment",
				"user": user,
				"project": PROJECT,
				"role": cls.role,
				"administrative_region": region,
				"is_active": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _login_as(self, user: str):
		frappe.set_user(user)
		try:
			return activate_pending_assignments_on_login()
		finally:
			frappe.set_user("Administrator")

	def test_login_activates_every_pending_assignment(self):
		self.assertEqual(
			frappe.db.get_value("GRM User Project Assignment", self.pending[0], "activation_status"),
			"Pending Activation",
			"precondition: assignment starts pending",
		)
		self._login_as(PENDING_USER)
		for name in self.pending:
			self.assertEqual(
				frappe.db.get_value("GRM User Project Assignment", name, "activation_status"),
				"Activated",
			)

	def test_login_clears_the_outstanding_code(self):
		self._login_as(PENDING_USER)
		self.assertFalse(
			frappe.db.get_value("GRM User Project Assignment", self.pending[0], "activation_code"),
			"a redundant OTP is left outstanding after login",
		)

	def test_login_grants_the_duty_roles(self):
		self._login_as(PENDING_USER)
		roles = {r.role for r in frappe.get_doc("User", PENDING_USER).roles}
		self.assertIn("GRM Intake", roles)

	def test_login_does_not_lift_a_suspension(self):
		self._login_as(SUSPENDED_USER)
		self.assertEqual(
			frappe.db.get_value("GRM User Project Assignment", self.suspended, "activation_status"),
			"Suspended",
			"a suspended worker was let back in by logging in",
		)

	def test_login_revives_an_expired_code(self):
		"""An expired code means nobody redeemed it in time, not that the
		account is blocked. Logging in supersedes it."""
		self._login_as(EXPIRED_USER)
		self.assertEqual(
			frappe.db.get_value("GRM User Project Assignment", self.expired, "activation_status"),
			"Activated",
		)

	def test_second_login_is_a_no_op(self):
		self._login_as(PENDING_USER)
		self.assertEqual(self._login_as(PENDING_USER), [])

	def test_guest_session_activates_nothing(self):
		self.assertEqual(self._login_as("Guest"), [])
