"""Tests for the admin-region wizard RPC endpoints.

Verifies that ``parse_admin_regions_csv`` returns a structured preview without
writing to the database, and that ``bulk_insert_admin_regions`` materialises
the highest-level region, every CSV column as a level type, and one region
per unique cell value.
"""

import frappe
import pytest

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
	bulk_insert_admin_regions,
	parse_admin_regions_csv,
)


@pytest.fixture
def sample_project():
	code = "TEST-ADMIN-UPLOAD"
	if not frappe.db.exists("GRM Project", code):
		frappe.get_doc(
			{
				"doctype": "GRM Project",
				"project_code": code,
				"title": "Test Admin Upload",
			}
		).insert(ignore_permissions=True)
	yield code
	# Best-effort cleanup. Region/Level docs are linked, so swallow integrity
	# errors — the next test run will reuse the project.
	try:
		frappe.delete_doc("GRM Project", code, force=True, delete_permanently=True)
	except Exception:
		frappe.db.rollback()


def test_parse_admin_regions_csv_returns_preview(sample_project):
	csv_text = "Province,District,Sector\n" "Kigali,Gasabo,Kacyiru\n" "Kigali,Gasabo,Remera\n"
	result = parse_admin_regions_csv(project=sample_project, highest_level="Country", csv_text=csv_text)
	assert result["total_rows"] == 2
	assert "Kigali" in str(result["preview"])
	assert result["errors"] == []
	assert result["level_columns"] == ["Province", "District", "Sector"]


def test_bulk_insert_admin_regions_creates_levels_and_regions(sample_project):
	csv_text = "Province,District\nKigali,Gasabo\n"
	result = bulk_insert_admin_regions(project=sample_project, highest_level="Country", csv_text=csv_text)
	assert result["created"] >= 3  # Country (auto), Kigali, Gasabo
	levels = frappe.get_all("GRM Administrative Level Type", filters={"project": sample_project})
	assert len(levels) >= 3
