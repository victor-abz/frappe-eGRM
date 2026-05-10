"""Tests for ``egrm.services.category_routing`` and the GRM Issue
``before_insert`` auto-routing path.

Each test seeds a project, a department, a role, and two categories
(one routed to the department, one to the role) so we can exercise both
sides of the helper.
"""

import frappe
import pytest

from egrm.services.category_routing import resolve_category_routing


PROJECT = "TEST-ROUTING"
DEPT_NAME = "DeptA"
ROLE_NAME = "RoleA"
CAT_DEPT = "C-Dept"
CAT_ROLE = "C-Role"


def _ensure(doctype: str, filters: dict, payload: dict) -> str:
    if frappe.db.exists(doctype, filters):
        return frappe.db.get_value(doctype, filters, "name")
    return frappe.get_doc({**payload, "doctype": doctype}).insert(
        ignore_permissions=True
    ).name


@pytest.fixture
def routed_category():
    if not frappe.db.exists("GRM Project", PROJECT):
        frappe.get_doc({
            "doctype": "GRM Project",
            "project_code": PROJECT,
            "title": "T",
        }).insert(ignore_permissions=True)

    dept = _ensure(
        "GRM Issue Department",
        {"department_name": DEPT_NAME},
        {
            "department_name": DEPT_NAME,
            "grm_project_link": [{"project": PROJECT}],
        },
    )
    role = _ensure(
        "GRM Project Role",
        {"project": PROJECT, "role_name": ROLE_NAME},
        {
            "project": PROJECT,
            "role_name": ROLE_NAME,
            "is_active": 1,
        },
    )
    cat_dept = _ensure(
        "GRM Issue Category",
        {"category_name": CAT_DEPT},
        {
            "project": PROJECT,
            "category_name": CAT_DEPT,
            "label": CAT_DEPT,
            "abbreviation": "CDP",
            "routing_target_type": "Department",
            "assigned_department": dept,
            "confidentiality_level": "Public",
            "redirection_protocol": "0",
            "grm_project_link": [{"project": PROJECT}],
        },
    )
    cat_role = _ensure(
        "GRM Issue Category",
        {"category_name": CAT_ROLE},
        {
            "project": PROJECT,
            "category_name": CAT_ROLE,
            "label": CAT_ROLE,
            "abbreviation": "CRL",
            "routing_target_type": "Role",
            "assigned_role": role,
            "confidentiality_level": "Public",
            "redirection_protocol": "0",
            "grm_project_link": [{"project": PROJECT}],
        },
    )
    yield {
        "dept_cat": cat_dept,
        "role_cat": cat_role,
        "dept": dept,
        "role": role,
        "project": PROJECT,
    }


def test_resolve_returns_department(routed_category):
    r = resolve_category_routing(routed_category["dept_cat"])
    assert r["target_type"] == "Department"
    assert r["target_name"] == routed_category["dept"]


def test_resolve_returns_role(routed_category):
    r = resolve_category_routing(routed_category["role_cat"])
    assert r["target_type"] == "Role"
    assert r["target_name"] == routed_category["role"]


def test_resolve_legacy_category_falls_back_to_department(routed_category):
    """Pre-migration row: ``routing_target_type`` NULL must default to Department."""
    frappe.db.set_value(
        "GRM Issue Category",
        routed_category["dept_cat"],
        "routing_target_type",
        None,
    )
    r = resolve_category_routing(routed_category["dept_cat"])
    assert r["target_type"] == "Department"
    assert r["target_name"] == routed_category["dept"]


def test_resolve_unknown_category_returns_safe_default():
    r = resolve_category_routing("ZZZ-DOES-NOT-EXIST")
    assert r["target_type"] == "Department"
    assert r["target_name"] is None
    assert r["target_doc"] is None


def test_new_issue_inherits_role_routing(routed_category):
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": routed_category["project"],
        "category": routed_category["role_cat"],
        "title": "T",
        "description": "D",
    }).insert(ignore_permissions=True)
    assert issue.assigned_role == routed_category["role"]
    assert not issue.assigned_department


def test_new_issue_inherits_department_routing(routed_category):
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": routed_category["project"],
        "category": routed_category["dept_cat"],
        "title": "T",
        "description": "D",
    }).insert(ignore_permissions=True)
    assert issue.assigned_department == routed_category["dept"]
    assert not issue.assigned_role


def test_caller_overrides_default_routing(routed_category):
    """Caller-supplied ``assigned_department`` wins over the category default."""
    other_dept = _ensure(
        "GRM Issue Department",
        {"department_name": "OverrideDept"},
        {
            "department_name": "OverrideDept",
            "grm_project_link": [{"project": routed_category["project"]}],
        },
    )
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": routed_category["project"],
        "category": routed_category["role_cat"],
        "title": "T",
        "description": "D",
        "assigned_department": other_dept,
    }).insert(ignore_permissions=True)
    assert issue.assigned_department == other_dept
    # role auto-assignment skipped because the caller already set a routing target
    assert not issue.assigned_role
