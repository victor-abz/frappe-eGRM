"""Tests for ``egrm.services.category_routing`` and the GRM Issue
``before_insert`` auto-routing path.

Categories now route only to a Role; department routing is rejected at
validation time. Legacy (NULL or "Department"-typed) rows are returned as
``target_name=None`` so the assignee resolver records a structured "no
routing target" reason and leaves the issue unassigned.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.services.category_routing import resolve_category_routing

PROJECT = "TEST-ROUTING"
ROLE_NAME = "RoleA"
CAT_ROLE = "C-Role"
CAT_LEGACY = "C-Legacy"


def _ensure(doctype: str, filters: dict, payload: dict) -> str:
	if frappe.db.exists(doctype, filters):
		return frappe.db.get_value(doctype, filters, "name")
	return frappe.get_doc({**payload, "doctype": doctype}).insert(ignore_permissions=True).name


class CategoryRoutingTests(FrappeTestCase):
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
				"abbreviation": "CRL",
				"routing_target_type": "Role",
				"assigned_role": cls.role,
				"confidentiality_level": "Public",
				"redirection_protocol": "0",
				"grm_project_link": [{"project": PROJECT}],
			},
		)
		# GRMIssue.validate_project_entities() requires status, issue_type and
		# administrative_region to resolve to this project. The wizard normally
		# seeds these ("Skipping default seed ... wizard owns its catalog"), so
		# a bare GRM Project has none of them.
		cls.status = _ensure(
			"GRM Issue Status",
			{"project": PROJECT, "status_name": "Open"},
			{
				"project": PROJECT,
				"status_name": "Open",
				"initial_status": 1,
				"open_status": 1,
				"grm_project_link": [{"project": PROJECT}],
			},
		)
		cls.issue_type = _ensure(
			"GRM Issue Type",
			{"project": PROJECT, "type_name": "Complaint"},
			{
				"project": PROJECT,
				"type_name": "Complaint",
				"grm_project_link": [{"project": PROJECT}],
			},
		)
		cls.level = _ensure(
			"GRM Administrative Level Type",
			{"project": PROJECT, "level_name": "Sector"},
			{"project": PROJECT, "level_name": "Sector", "level_order": 1},
		)
		cls.region = _ensure(
			"GRM Administrative Region",
			{"project": PROJECT, "region_name": "R-Routing"},
			{
				"project": PROJECT,
				"region_name": "R-Routing",
				"administrative_level": cls.level,
				"path": "R-Routing",
			},
		)
		# Auto-routing puts an assignee on the issue, and
		# validate_project_entities() then demands that user hold an active
		# assignment on the project.
		cls.assignment = _ensure(
			"GRM User Project Assignment",
			{"user": "Administrator", "project": PROJECT, "role": cls.role},
			{
				"user": "Administrator",
				"project": PROJECT,
				"role": cls.role,
				"administrative_region": cls.region,
				"is_active": 1,
			},
		)
		frappe.db.commit()

	@classmethod
	def _issue_payload(cls, **overrides) -> dict:
		payload = {
			"doctype": "GRM Issue",
			"project": PROJECT,
			"category": cls.role_cat,
			"status": cls.status,
			"issue_type": cls.issue_type,
			"administrative_region": cls.region,
			"reporter": "Administrator",
			"contact_medium": "anonymous",
			"title": "T",
			"description": "D",
		}
		payload.update(overrides)
		return payload

	@classmethod
	def tearDownClass(cls):
		# Best-effort: issues/categories/roles hang off the project, so let the
		# cascade handle them and swallow integrity errors.
		try:
			for issue in frappe.get_all("GRM Issue", filters={"project": PROJECT}, pluck="name"):
				frappe.delete_doc("GRM Issue", issue, force=True, delete_permanently=True)
			frappe.delete_doc("GRM Project", PROJECT, force=True, delete_permanently=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
		super().tearDownClass()

	def test_resolve_returns_role(self):
		r = resolve_category_routing(self.role_cat)
		self.assertEqual(r["target_type"], "Role")
		self.assertEqual(r["target_name"], self.role)

	def test_resolve_legacy_null_returns_no_target(self):
		"""Pre-migration row: ``routing_target_type`` NULL must surface as
		``target_name=None`` so callers treat it as misconfigured."""
		frappe.db.set_value(
			"GRM Issue Category",
			self.role_cat,
			"routing_target_type",
			None,
		)
		try:
			r = resolve_category_routing(self.role_cat)
			self.assertEqual(r["target_type"], "Role")
			self.assertIsNone(r["target_name"])
		finally:
			# Restore unconditionally — the other tests in this class share the
			# class-scoped category and run in an unspecified order.
			frappe.db.set_value(
				"GRM Issue Category",
				self.role_cat,
				"routing_target_type",
				"Role",
			)

	def test_resolve_unknown_category_returns_safe_default(self):
		r = resolve_category_routing("ZZZ-DOES-NOT-EXIST")
		self.assertEqual(r["target_type"], "Role")
		self.assertIsNone(r["target_name"])
		self.assertIsNone(r["target_doc"])

	def test_new_issue_inherits_role_routing(self):
		issue = frappe.get_doc(self._issue_payload()).insert(ignore_permissions=True)
		self.assertEqual(issue.assigned_role, self.role)
		self.assertFalse(issue.assigned_department)

	def test_caller_role_override_wins(self):
		"""Caller-supplied ``assigned_role`` wins over the category default."""
		other_role = _ensure(
			"GRM Project Role",
			{"project": PROJECT, "role_name": "OverrideRole"},
			{
				"project": PROJECT,
				"role_name": "OverrideRole",
				"is_active": 1,
				"duties": [{"duty": "Intake"}],
			},
		)
		issue = frappe.get_doc(self._issue_payload(assigned_role=other_role)).insert(ignore_permissions=True)
		self.assertEqual(issue.assigned_role, other_role)

	def test_category_rejects_department_target(self):
		"""Saving a category with ``routing_target_type='Department'`` must throw."""
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "GRM Issue Category",
					"project": PROJECT,
					"category_name": "C-RejectDept",
					"label": "C-RejectDept",
					"abbreviation": "RDP",
					"routing_target_type": "Department",
					"confidentiality_level": "Public",
					"redirection_protocol": "0",
					"grm_project_link": [{"project": PROJECT}],
				}
			).insert(ignore_permissions=True)
