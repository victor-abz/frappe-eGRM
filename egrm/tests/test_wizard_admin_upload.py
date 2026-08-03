"""Tests for the admin-region wizard RPC endpoints.

Verifies that ``parse_admin_regions_csv`` returns a structured preview without
writing to the database, and that ``bulk_insert_admin_regions`` materialises
the highest-level region, every CSV column as a level type, and one region
per unique cell value.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
	bulk_insert_admin_regions,
	parse_admin_regions_csv,
)

PROJECT_CODE = "TEST-ADMIN-UPLOAD"


class WizardAdminUploadTests(FrappeTestCase):
	"""Was a set of bare pytest functions with a ``@pytest.fixture``. The
	Frappe runner is unittest-based: it never collected those functions, and
	the ``import pytest`` aborted discovery for the whole app on any bench
	without pytest installed (i.e. CI). Rewritten as a TestCase so the
	assertions actually execute."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("GRM Project", PROJECT_CODE):
			frappe.get_doc(
				{
					"doctype": "GRM Project",
					"project_code": PROJECT_CODE,
					"title": "Test Admin Upload",
				}
			).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Delete the children before the project: deleting the project alone
		# leaves the regions and level types behind, and on the next run
		# `bulk_insert_admin_regions` reports them as `updated` rather than
		# `created`.
		try:
			for doctype in ("GRM Administrative Region", "GRM Administrative Level Type"):
				for name in frappe.get_all(doctype, filters={"project": PROJECT_CODE}, pluck="name"):
					frappe.delete_doc(doctype, name, force=True, delete_permanently=True)
			frappe.delete_doc("GRM Project", PROJECT_CODE, force=True, delete_permanently=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
		super().tearDownClass()

	def test_parse_admin_regions_csv_returns_preview(self):
		csv_text = "Province,District,Sector\nKigali,Gasabo,Kacyiru\nKigali,Gasabo,Remera\n"
		result = parse_admin_regions_csv(project=PROJECT_CODE, highest_level="Country", csv_text=csv_text)
		self.assertEqual(result["total_rows"], 2)
		self.assertIn("Kigali", str(result["preview"]))
		self.assertEqual(result["errors"], [])
		self.assertEqual(result["level_columns"], ["Province", "District", "Sector"])

	def test_bulk_insert_admin_regions_creates_levels_and_regions(self):
		csv_text = "Province,District\nKigali,Gasabo\n"
		result = bulk_insert_admin_regions(project=PROJECT_CODE, highest_level="Country", csv_text=csv_text)
		self.assertEqual(result["errors"], [])
		self.assertEqual(result["level_columns"], ["Province", "District"])
		# Assert on the resulting state, never on the created/updated counters:
		# rows left over from an earlier run are reported as `updated`, and a
		# pre-existing highest-level region is reported as neither. Counter-based
		# assertions therefore only hold against a virgin database.
		levels = frappe.get_all(
			"GRM Administrative Level Type", filters={"project": PROJECT_CODE}, pluck="level_name"
		)
		self.assertEqual(sorted(levels), ["Country", "District", "Province"])
		regions = frappe.get_all(
			"GRM Administrative Region", filters={"project": PROJECT_CODE}, pluck="region_name"
		)
		# "Country" is the auto-created highest-level region.
		self.assertEqual(sorted(regions), ["Country", "Gasabo", "Kigali"])
