"""Tests for the wizard's bulk user-creation RPC endpoints.

The tests seed a project, one Administrative Level Type, and one
Administrative Region (so the wizard CSV can reference a region by name)
before invoking ``parse_users_csv`` and ``bulk_create_users``.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
	bulk_create_users,
	parse_users_csv,
)

PROJECT_CODE = "TEST-USER-IMPORT"
REGION_NAME = "Kacyiru"
LEVEL_NAME = "Sector"
POSITION = "Field Officer"


def _ensure_role(role_name: str) -> None:
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)


def _seed_project_with_one_region() -> None:
	if not frappe.db.exists("GRM Project", PROJECT_CODE):
		frappe.get_doc(
			{
				"doctype": "GRM Project",
				"project_code": PROJECT_CODE,
				"title": "Test User Import",
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists(
		"GRM Administrative Level Type",
		{"project": PROJECT_CODE, "level_name": LEVEL_NAME},
	):
		frappe.get_doc(
			{
				"doctype": "GRM Administrative Level Type",
				"project": PROJECT_CODE,
				"level_name": LEVEL_NAME,
				"level_order": 1,
			}
		).insert(ignore_permissions=True)
	level_id = frappe.db.get_value(
		"GRM Administrative Level Type",
		{"project": PROJECT_CODE, "level_name": LEVEL_NAME},
		"name",
	)
	if not frappe.db.exists(
		"GRM Administrative Region",
		{"project": PROJECT_CODE, "region_name": REGION_NAME},
	):
		frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"project": PROJECT_CODE,
				"region_name": REGION_NAME,
				"administrative_level": level_id,
				"path": REGION_NAME,
			}
		).insert(ignore_permissions=True)
	_ensure_role("GRM Field Officer")
	# The importer treats the CSV `position` cell as a *GRM Project Role*
	# name (government_worker_importer.py: `role_name = project_role or
	# position or DEFAULT`), and refuses to run at all if the project has no
	# Project Role rows. The Frappe `Role` above is a separate thing.
	if not frappe.db.exists("GRM Project Role", {"project": PROJECT_CODE, "role_name": POSITION}):
		frappe.get_doc(
			{
				"doctype": "GRM Project Role",
				"project": PROJECT_CODE,
				"role_name": POSITION,
				# `duties` is reqd — GRMProjectRole.validate() rejects an empty
				# table. "Intake" ships in egrm/fixtures/grm_duty.json.
				"duties": [{"duty": "Intake"}],
			}
		).insert(ignore_permissions=True)


CSV_TEXT = (
	"first_name,last_name,position,region,phone\n" f"Alice,Doe,{POSITION},{REGION_NAME},+250788000001\n"
)


class WizardUserCreationTests(FrappeTestCase):
	"""Was a set of bare pytest functions with a ``@pytest.fixture``. The
	Frappe runner is unittest-based: it never collected those functions, and
	the ``import pytest`` aborted discovery for the whole app on any bench
	without pytest installed (i.e. CI). Rewritten as a TestCase so the
	assertions actually execute."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_seed_project_with_one_region()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Delete the children (and the Users the importer minted) before the
		# project. Deleting the project alone leaves them behind, and the next
		# run reports the same row as an update rather than a creation.
		try:
			users = frappe.get_all(
				"GRM User Project Assignment", filters={"project": PROJECT_CODE}, pluck="user"
			)
			for doctype in (
				"GRM User Project Assignment",
				"GRM Administrative Region",
				"GRM Administrative Level Type",
				"GRM Project Role",
			):
				for name in frappe.get_all(doctype, filters={"project": PROJECT_CODE}, pluck="name"):
					frappe.delete_doc(doctype, name, force=True, delete_permanently=True)
			for user in set(users):
				if user != "Administrator":
					frappe.delete_doc("User", user, force=True, delete_permanently=True)
			frappe.delete_doc("GRM Project", PROJECT_CODE, force=True, delete_permanently=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
		super().tearDownClass()

	def test_parse_users_csv_returns_validation(self):
		r = parse_users_csv(project=PROJECT_CODE, csv_text=CSV_TEXT)
		self.assertEqual(r["total_rows"], 1)
		self.assertEqual(r["errors"], [])

	def test_bulk_create_users_inserts_and_returns_codes(self):
		r = bulk_create_users(project=PROJECT_CODE, csv_text=CSV_TEXT)
		self.assertEqual(r["errors"], [])
		# Assert on the resulting state, not on `created`: a User left over from
		# an earlier run is reused rather than created, which would make a
		# `created >= 1` assertion pass only against a virgin database.
		self.assertEqual(len(r["activation_codes"]), 1)
		code = r["activation_codes"][0]
		self.assertTrue(frappe.db.exists("User", code["email"]))
		self.assertTrue(
			frappe.db.exists("GRM User Project Assignment", {"user": code["email"], "project": PROJECT_CODE})
		)
