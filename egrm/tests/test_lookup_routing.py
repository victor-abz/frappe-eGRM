"""Mobile-API surface tests: ``categories()`` must report each category's
routing target type and resolved target name.

Categories now route only to a Role; legacy Department-typed rows still
exist in DBs but no longer validate on save, so we don't fabricate them
here.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.api.lookup import categories

PROJECT = "TEST-LOOKUP-ROUTING"
ROLE_NAME = "RoleL"
CAT_ROLE = "L-CRole"


def _ensure(doctype: str, filters: dict, payload: dict) -> str:
	if frappe.db.exists(doctype, filters):
		return frappe.db.get_value(doctype, filters, "name")
	return frappe.get_doc({**payload, "doctype": doctype}).insert(ignore_permissions=True).name


def _resp_to_categories(resp) -> list:
	assert resp["status"] == "success", resp
	return resp["data"]


class LookupRoutingTests(FrappeTestCase):
	"""Was a set of bare pytest functions with a ``@pytest.fixture``. The
	Frappe runner is unittest-based: it never collected those functions, and
	the ``import pytest`` aborted discovery for the whole app on any bench
	without pytest installed (i.e. CI). Rewritten as a TestCase so the
	assertions actually execute."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("GRM Project", PROJECT):
			frappe.get_doc(
				{
					"doctype": "GRM Project",
					"project_code": PROJECT,
					"title": "T",
				}
			).insert(ignore_permissions=True)
		cls.role = _ensure(
			"GRM Project Role",
			{"project": PROJECT, "role_name": ROLE_NAME},
			{
				"project": PROJECT,
				"role_name": ROLE_NAME,
				"is_active": 1,
				# `duties` is reqd — GRMProjectRole.validate() rejects an empty
				# table. "Intake" ships in egrm/fixtures/grm_duty.json.
				"duties": [{"duty": "Intake"}],
			},
		)
		cls.role_cat = _ensure(
			"GRM Issue Category",
			{"category_name": CAT_ROLE},
			{
				"project": PROJECT,
				"category_name": CAT_ROLE,
				"label": CAT_ROLE,
				"abbreviation": "LCR",
				"routing_target_type": "Role",
				"assigned_role": cls.role,
				"confidentiality_level": "Public",
				"redirection_protocol": "0",
				"grm_project_link": [{"project": PROJECT}],
			},
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Best-effort: the category and role are linked to the project, so let
		# the cascade handle them and swallow integrity errors.
		try:
			frappe.delete_doc("GRM Issue Category", cls.role_cat, force=True, delete_permanently=True)
			frappe.delete_doc("GRM Project", PROJECT, force=True, delete_permanently=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
		super().tearDownClass()

	def test_lookup_returns_role_routing(self):
		cats = _resp_to_categories(categories(project_id=PROJECT))
		role_cat = next(c for c in cats if c["name"] == self.role_cat)
		self.assertEqual(role_cat["routing_target_type"], "Role")
		self.assertEqual(role_cat["role"], self.role)
		self.assertIsNone(role_cat["department"])
