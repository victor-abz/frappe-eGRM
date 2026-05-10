"""Single source of truth for resolving a GRM Issue Category's routing target.

Consumers MUST call ``resolve_category_routing(category_name)`` instead of
reading ``assigned_department`` directly. Keeps the dept-vs-role logic in
one place and lets us evolve routing (e.g. add a 'User' target type) without
hunting through the codebase.
"""
import frappe


def resolve_category_routing(category_name: str) -> dict:
    """Resolve where issues of this category should be routed.

    Returns:
        ``{"target_type": "Department" | "Role",
            "target_name": str | None,
            "target_doc": <Frappe Document> | None}``

    Backwards-compatibility:
        Categories whose ``routing_target_type`` is NULL (pre-migration) are
        treated as ``"Department"`` and routed to ``assigned_department``.
    """
    cat = frappe.db.get_value(
        "GRM Issue Category",
        category_name,
        ["routing_target_type", "assigned_department", "assigned_role"],
        as_dict=True,
    )
    if not cat:
        return {"target_type": "Department", "target_name": None, "target_doc": None}

    target_type = cat.routing_target_type or "Department"
    if target_type == "Role":
        target_name = cat.assigned_role
        target_doc = (
            frappe.get_doc("GRM Project Role", target_name) if target_name else None
        )
    else:
        target_name = cat.assigned_department
        target_doc = (
            frappe.get_doc("GRM Issue Department", target_name)
            if target_name
            else None
        )

    return {"target_type": target_type, "target_name": target_name, "target_doc": target_doc}


def resolve_routing_for_issue_creation(category_name: str) -> dict:
    """Wizard-friendly variant returning the values to write onto a new GRM Issue.

    For Department routing: ``{"assigned_department": <name>, "assigned_role": None}``.
    For Role routing:       ``{"assigned_department": None, "assigned_role": <name>}``.
    """
    r = resolve_category_routing(category_name)
    if r["target_type"] == "Role":
        return {"assigned_department": None, "assigned_role": r["target_name"]}
    return {"assigned_department": r["target_name"], "assigned_role": None}
