"""Tests for ``egrm.services.category_routing`` and the GRM Issue
``before_insert`` auto-routing path.

Categories now route only to a Role; department routing is rejected at
validation time. Legacy (NULL or "Department"-typed) rows are returned as
``target_name=None`` so the assignee resolver records a structured "no
routing target" reason and leaves the issue unassigned.
"""

import frappe
import pytest

from egrm.services.category_routing import resolve_category_routing


PROJECT = "TEST-ROUTING"
ROLE_NAME = "RoleA"
CAT_ROLE = "C-Role"
CAT_LEGACY = "C-Legacy"


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

    role = _ensure(
        "GRM Project Role",
        {"project": PROJECT, "role_name": ROLE_NAME},
        {
            "project": PROJECT,
            "role_name": ROLE_NAME,
            "is_active": 1,
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
        "role_cat": cat_role,
        "role": role,
        "project": PROJECT,
    }


def test_resolve_returns_role(routed_category):
    r = resolve_category_routing(routed_category["role_cat"])
    assert r["target_type"] == "Role"
    assert r["target_name"] == routed_category["role"]


def test_resolve_legacy_null_returns_no_target(routed_category):
    """Pre-migration row: ``routing_target_type`` NULL must surface as
    ``target_name=None`` so callers treat it as misconfigured."""
    frappe.db.set_value(
        "GRM Issue Category",
        routed_category["role_cat"],
        "routing_target_type",
        None,
    )
    r = resolve_category_routing(routed_category["role_cat"])
    assert r["target_type"] == "Role"
    assert r["target_name"] is None
    # restore for any later assertions in the same session
    frappe.db.set_value(
        "GRM Issue Category",
        routed_category["role_cat"],
        "routing_target_type",
        "Role",
    )


def test_resolve_unknown_category_returns_safe_default():
    r = resolve_category_routing("ZZZ-DOES-NOT-EXIST")
    assert r["target_type"] == "Role"
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


def test_caller_role_override_wins(routed_category):
    """Caller-supplied ``assigned_role`` wins over the category default."""
    other_role = _ensure(
        "GRM Project Role",
        {"project": PROJECT, "role_name": "OverrideRole"},
        {"project": PROJECT, "role_name": "OverrideRole", "is_active": 1},
    )
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": routed_category["project"],
        "category": routed_category["role_cat"],
        "title": "T",
        "description": "D",
        "assigned_role": other_role,
    }).insert(ignore_permissions=True)
    assert issue.assigned_role == other_role


def test_category_rejects_department_target(routed_category):
    """Saving a category with ``routing_target_type='Department'`` must throw."""
    with pytest.raises(frappe.ValidationError):
        frappe.get_doc({
            "doctype": "GRM Issue Category",
            "project": PROJECT,
            "category_name": "C-RejectDept",
            "label": "C-RejectDept",
            "abbreviation": "RDP",
            "routing_target_type": "Department",
            "confidentiality_level": "Public",
            "redirection_protocol": "0",
            "grm_project_link": [{"project": PROJECT}],
        }).insert(ignore_permissions=True)
