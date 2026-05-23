"""Tests for the wizard's bulk user-creation RPC endpoints.

The tests seed a project, one Administrative Level Type, and one
Administrative Region (so the wizard CSV can reference a region by name)
before invoking ``parse_users_csv`` and ``bulk_create_users``.
"""

import frappe
import pytest

from egrm.egrm.page.grm_project_wizard.grm_project_wizard import (
    bulk_create_users,
    parse_users_csv,
)

PROJECT_CODE = "TEST-USER-IMPORT"
REGION_NAME = "Kacyiru"
LEVEL_NAME = "Sector"


def _ensure_role(role_name: str) -> None:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)


def _seed_project_with_one_region() -> None:
    if not frappe.db.exists("GRM Project", PROJECT_CODE):
        frappe.get_doc({
            "doctype": "GRM Project",
            "project_code": PROJECT_CODE,
            "title": "Test User Import",
        }).insert(ignore_permissions=True)
    if not frappe.db.exists(
        "GRM Administrative Level Type",
        {"project": PROJECT_CODE, "level_name": LEVEL_NAME},
    ):
        frappe.get_doc({
            "doctype": "GRM Administrative Level Type",
            "project": PROJECT_CODE,
            "level_name": LEVEL_NAME,
            "level_order": 1,
        }).insert(ignore_permissions=True)
    level_id = frappe.db.get_value(
        "GRM Administrative Level Type",
        {"project": PROJECT_CODE, "level_name": LEVEL_NAME},
        "name",
    )
    if not frappe.db.exists(
        "GRM Administrative Region",
        {"project": PROJECT_CODE, "region_name": REGION_NAME},
    ):
        frappe.get_doc({
            "doctype": "GRM Administrative Region",
            "project": PROJECT_CODE,
            "region_name": REGION_NAME,
            "administrative_level": level_id,
            "path": REGION_NAME,
        }).insert(ignore_permissions=True)
    _ensure_role("GRM Field Officer")


@pytest.fixture
def project_with_regions():
    _seed_project_with_one_region()
    yield PROJECT_CODE
    try:
        frappe.delete_doc("GRM Project", PROJECT_CODE, force=True, delete_permanently=True)
    except Exception:
        frappe.db.rollback()


def test_parse_users_csv_returns_validation(project_with_regions):
    csv_text = (
        "first_name,last_name,position,region,phone\n"
        f"Alice,Doe,Field Officer,{REGION_NAME},+250788000001\n"
    )
    r = parse_users_csv(project=project_with_regions, csv_text=csv_text)
    assert r["total_rows"] == 1
    assert r["errors"] == []


def test_bulk_create_users_inserts_and_returns_codes(project_with_regions):
    csv_text = (
        "first_name,last_name,position,region,phone\n"
        f"Alice,Doe,Field Officer,{REGION_NAME},+250788000001\n"
    )
    r = bulk_create_users(project=project_with_regions, csv_text=csv_text)
    assert r["created"] >= 1
    assert "activation_codes" in r
