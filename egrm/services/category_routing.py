"""Single source of truth for resolving a GRM Issue Category's routing target.

Consumers MUST call ``resolve_category_routing(category_name)`` instead of
reading ``assigned_role`` directly. Keeps the routing-target logic in one
place.

Routing model
-------------
Categories route only to a **Role**. The resolver in
``egrm.services.assignee_routing`` then picks a specific User from that role
based on region + duty. Legacy categories with
``routing_target_type == "Department"`` or NULL are treated as misconfigured
— ``target_name`` is returned as ``None`` so the assignee resolver records a
``CATEGORY_HAS_NO_ROUTING_TARGET`` log entry and leaves the issue
unassigned. Operators fix this in the wizard's category step.
"""

import frappe


def resolve_category_routing(category_name: str) -> dict:
	"""Resolve where issues of this category should be routed.

	Returns:
	    ``{"target_type": "Role",
	        "target_name": str | None,
	        "target_doc": <Frappe Document> | None}``

	``target_name`` is ``None`` when the category is missing, NULL-typed, or
	typed as Department (legacy). Callers MUST handle the ``None`` case.
	"""
	cat = frappe.db.get_value(
		"GRM Issue Category",
		category_name,
		["routing_target_type", "assigned_role"],
		as_dict=True,
	)
	if not cat or cat.routing_target_type != "Role" or not cat.assigned_role:
		return {"target_type": "Role", "target_name": None, "target_doc": None}

	target_doc = frappe.get_doc("GRM Project Role", cat.assigned_role)
	return {"target_type": "Role", "target_name": cat.assigned_role, "target_doc": target_doc}


def resolve_routing_for_issue_creation(category_name: str) -> dict:
	"""Wizard-friendly variant returning the values to write onto a new GRM Issue.

	Returns ``{"assigned_role": <name | None>}``. ``assigned_department`` is
	no longer populated from the category — the field on GRM Issue remains
	for back-compat but is left null for newly created issues.
	"""
	r = resolve_category_routing(category_name)
	return {"assigned_role": r["target_name"]}
