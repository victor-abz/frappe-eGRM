"""Mobile-API surface tests: ``categories()`` must report each category's
routing target type and resolved target name.
"""

import frappe
import pytest

from egrm.api.lookup import categories


PROJECT = "TEST-LOOKUP-ROUTING"
DEPT_NAME = "DeptL"
ROLE_NAME = "RoleL"
CAT_DEPT = "L-CDept"
CAT_ROLE = "L-CRole"


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
        {"project": PROJECT, "role_name": ROLE_NAME, "is_active": 1},
    )
    cat_dept = _ensure(
        "GRM Issue Category",
        {"category_name": CAT_DEPT},
        {
            "project": PROJECT,
            "category_name": CAT_DEPT,
            "label": CAT_DEPT,
            "abbreviation": "LCD",
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
            "abbreviation": "LCR",
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
    }


def _resp_to_categories(resp) -> list:
    assert resp["status"] == "success", resp
    return resp["data"]


def test_lookup_returns_role_routing(routed_category):
    cats = _resp_to_categories(categories(project_id=PROJECT))
    role_cat = next(c for c in cats if c["name"] == routed_category["role_cat"])
    assert role_cat["routing_target_type"] == "Role"
    assert role_cat["role"] == routed_category["role"]
    assert role_cat["department"] is None


def test_lookup_returns_department_routing(routed_category):
    cats = _resp_to_categories(categories(project_id=PROJECT))
    dept_cat = next(c for c in cats if c["name"] == routed_category["dept_cat"])
    assert dept_cat["routing_target_type"] == "Department"
    assert dept_cat["department"] == routed_category["dept"]
    assert dept_cat["role"] is None
