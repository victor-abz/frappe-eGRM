import json
import logging

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

log = logging.getLogger(__name__)


def _coerce_pagination(start, page_len):
    """Cast LIMIT bounds to int to harden against accidental injection.

    Frappe always sends ints for these, but the typeahead protocol does
    NOT enforce that — and even with parameterized queries we want a
    defense-in-depth integer cast before interpolation into LIMIT.
    """
    try:
        s = int(start) if start is not None else 0
    except (TypeError, ValueError):
        s = 0
    try:
        p = int(page_len) if page_len is not None else 20
    except (TypeError, ValueError):
        p = 20
    return max(0, s), max(1, min(p, 500))


def _normalize_filters(filters):
    """Coerce filters into a dict.

    Frappe's typeahead pipeline normally parses JSON-string filters before
    invoking the registered query (search.search_widget does this). Some
    code paths (validate_link_and_fetch, direct frappe.client.get_list with
    custom query) hand the JSON string straight through. Always normalize
    so .get() works regardless of caller.
    """
    if isinstance(filters, str):
        try:
            return json.loads(filters)
        except (TypeError, ValueError):
            return {}
    if filters is None:
        return {}
    if isinstance(filters, dict):
        return filters
    if isinstance(filters, (list, tuple)):
        # Frappe also accepts list-of-list filter form. We only need the
        # named-key form for these typeahead lookups; flatten to dict if
        # possible, otherwise return empty.
        out: dict = {}
        for item in filters:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out[item[0]] = item[1]
        return out
    return {}


def _ensure_project_typeahead_access(project):
    """Gate project-scoped typeahead lookups by GRM duty on the project.

    Mirrors the duty model used by GRM Issue permissions
    (egrm.server_scripts.grm_issue_permissions): bypass roles or any
    active duty on the project grants access; everyone else is denied
    so we don't leak project configuration to logged-in users who hold
    no operational role on that project.
    """
    from egrm.server_scripts.grm_issue_permissions import (
        BYPASS_ROLES,
        _user_duties_for_project,
    )

    user = frappe.session.user
    if user == "Administrator":
        return
    if user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)
    if set(frappe.get_roles(user)) & set(BYPASS_ROLES):
        return
    if not project:
        return
    if not _user_duties_for_project(user, project):
        frappe.throw(
            _("You do not have an active GRM duty on this project."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_departments_by_projects(doctype, txt, searchfield, start, page_len, filters):
    """Get departments linked to specific projects (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        projects = filters.get("projects", [])
        if not projects:
            return []

        # Handle single project as string
        if isinstance(projects, str):
            projects = [projects]

        # Review fix B1: project-scope the typeahead access check across
        # every project in the input list. Without this, a user with
        # access to project P1 could exfiltrate department names from
        # P2 by passing both ids in ``filters.projects``.
        for project in projects:
            _ensure_project_typeahead_access(project)

        start, page_len = _coerce_pagination(start, page_len)
        placeholders = ", ".join(["%s"] * len(projects))
        params: list = list(projects)
        search_condition = ""
        if txt:
            search_condition = "AND d.department_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT d.name, d.department_name
            FROM `tabGRM Issue Department` d
            INNER JOIN `tabGRM Project Link` p ON p.parent = d.name
            WHERE p.project IN ({placeholders})
            {search_condition}
            GROUP BY d.name
            ORDER BY d.department_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting departments by projects: {str(e)}")
        return []


@frappe.whitelist()
def get_status_by_project(doctype, txt, searchfield, start, page_len, filters):
    """Get statuses linked to a specific project (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        _ensure_project_typeahead_access(project)
        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        search_condition = ""
        if txt:
            search_condition = "AND s.status_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT s.name, s.status_name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            {search_condition}
            ORDER BY s.status_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting statuses by project: {str(e)}")
        return []


@frappe.whitelist()
def get_category_by_project(doctype, txt, searchfield, start, page_len, filters):
    """Get categories linked to a specific project (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        _ensure_project_typeahead_access(project)
        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        search_condition = ""
        if txt:
            search_condition = "AND c.category_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT c.name, c.category_name
            FROM `tabGRM Issue Category` c
            INNER JOIN `tabGRM Project Link` p ON p.parent = c.name
            WHERE p.project = %s
            {search_condition}
            ORDER BY c.category_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting categories by project: {str(e)}")
        return []


@frappe.whitelist()
def get_issue_type_by_project(doctype, txt, searchfield, start, page_len, filters):
    """Get issue types linked to a specific project (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        _ensure_project_typeahead_access(project)
        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        search_condition = ""
        if txt:
            search_condition = "AND t.type_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT t.name, t.type_name
            FROM `tabGRM Issue Type` t
            INNER JOIN `tabGRM Project Link` p ON p.parent = t.name
            WHERE p.project = %s
            {search_condition}
            ORDER BY t.type_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting issue types by project: {str(e)}")
        return []


@frappe.whitelist()
def get_age_group_by_project(doctype, txt, searchfield, start, page_len, filters):
    """Get age groups linked to a specific project (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        _ensure_project_typeahead_access(project)
        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        search_condition = ""
        if txt:
            search_condition = "AND a.age_group LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT a.name, a.age_group
            FROM `tabGRM Issue Age Group` a
            INNER JOIN `tabGRM Project Link` p ON p.parent = a.name
            WHERE p.project = %s
            {search_condition}
            ORDER BY a.age_group
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting age groups by project: {str(e)}")
        return []


@frappe.whitelist()
def get_citizen_group_by_project(doctype, txt, searchfield, start, page_len, filters):
    """Get citizen groups linked to a specific project with optional group_type filter."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        _ensure_project_typeahead_access(project)
        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        group_type = filters.get("group_type", "")
        group_type_condition = ""
        if group_type:
            group_type_condition = "AND c.group_type = %s"
            params.append(group_type)
        search_condition = ""
        if txt:
            search_condition = "AND c.group_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT c.name, c.group_name
            FROM `tabGRM Issue Citizen Group` c
            INNER JOIN `tabGRM Project Link` p ON p.parent = c.name
            WHERE p.project = %s
            {group_type_condition}
            {search_condition}
            ORDER BY c.group_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting citizen groups by project: {str(e)}")
        return []


@frappe.whitelist()
def get_project_users(doctype, txt, searchfield, start, page_len, filters):
    """Get users assigned to a specific project (typeahead)."""
    try:
        filters = _normalize_filters(filters)
        project = filters.get("project", "")
        if not project:
            return []

        start, page_len = _coerce_pagination(start, page_len)
        params: list = [project]
        search_condition = ""
        if txt:
            search_condition = "AND u.full_name LIKE %s"
            params.append(f"%{txt}%")

        return frappe.db.sql(
            f"""
            SELECT u.name, u.full_name
            FROM `tabUser` u
            INNER JOIN `tabGRM User Project Assignment` a ON a.user = u.name
            WHERE a.project = %s
            AND a.is_active = 1
            {search_condition}
            GROUP BY u.name
            ORDER BY u.full_name
            LIMIT {start}, {page_len}
            """,
            tuple(params),
            as_list=1,
        )
    except Exception as e:
        frappe.log_error(f"Error getting project users: {str(e)}")
        return []


@frappe.whitelist()
def get_initial_status(project):
    """
    Get the initial status for a project
    """
    try:
        if not project:
            return None

        _ensure_project_typeahead_access(project)
        # Find initial status for the project
        initial_status = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.initial_status = 1
            LIMIT 1
        """,
            project,
            as_dict=1,
        )

        if initial_status:
            return initial_status[0].name

        return None
    except Exception as e:
        frappe.log_error(f"Error getting initial status: {str(e)}")
        return None


@frappe.whitelist()
def get_department_for_category(category):
    """Resolve where this category routes to (Department or Role).

    Routing-aware return shape:
        ``{"target_type": "Department" | "Role",
            "department": <name|None>, "role": <name|None>,
            "redirection": <protocol>}``

    The legacy ``"department"`` key is preserved (None when role-routed)
    so older callers that destructure it still work without crashes.
    """
    try:
        if not category:
            return None

        # Gate by duty on any project this category is linked to.
        project_links = frappe.get_all(
            "GRM Project Link",
            filters={"parent": category, "parenttype": "GRM Issue Category"},
            pluck="project",
            ignore_permissions=True,
        )
        if project_links:
            _ensure_project_typeahead_access(project_links[0])

        from egrm.services.category_routing import resolve_category_routing

        routing = resolve_category_routing(category)
        redirection = frappe.db.get_value(
            "GRM Issue Category", category, "redirection_protocol"
        )
        return {
            "target_type": routing["target_type"],
            "department": (
                routing["target_name"]
                if routing["target_type"] == "Department"
                else None
            ),
            "role": (
                routing["target_name"]
                if routing["target_type"] == "Role"
                else None
            ),
            "redirection": redirection,
        }
    except Exception as e:
        frappe.log_error(f"Error getting department for category: {str(e)}")
        return None


@frappe.whitelist()
def get_least_loaded_user(department, project):
    """
    Get the user with the least assigned issues in a department
    """
    try:
        if not department or not project:
            return None

        _ensure_project_typeahead_access(project)
        # Get department head as fallback
        department_head = frappe.db.get_value(
            "GRM Issue Department", department, "head"
        )

        # Get all users in the department for this project
        department_users = frappe.db.sql(
            """
            SELECT a.user
            FROM `tabGRM User Project Assignment` a
            WHERE a.department = %s
            AND a.project = %s
            AND a.is_active = 1
        """,
            (department, project),
            as_dict=1,
        )

        if not department_users:
            return department_head

        user_list = [u.user for u in department_users]

        # Count open issues assigned to each user
        user_loads = {}
        for user in user_list:
            count = frappe.db.count(
                "GRM Issue",
                {
                    "assignee": user,
                    "project": project,
                    "status": ["in", get_open_statuses(project)],
                },
            )
            user_loads[user] = count

        # Find user with minimum load
        min_load_user = (
            min(user_loads.items(), key=lambda x: x[1])[0]
            if user_loads
            else department_head
        )

        return min_load_user
    except Exception as e:
        frappe.log_error(f"Error getting least loaded user: {str(e)}")
        return None


def get_open_statuses(project):
    """
    Get a list of open statuses for a project
    """
    try:
        if not project:
            return []

        open_statuses = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.open_status = 1
        """,
            project,
            as_dict=1,
        )

        return [s.name for s in open_statuses] if open_statuses else []
    except Exception as e:
        frappe.log_error(f"Error getting open statuses: {str(e)}")
        return []


@frappe.whitelist()
def get_allowed_statuses(issue):
    """
    Get allowed next statuses for an issue based on workflow
    """
    try:
        if not issue:
            return []

        # For now, return all statuses for the issue's project
        issue_doc = frappe.get_doc("GRM Issue", issue)

        if not issue_doc:
            return []

        project = issue_doc.project
        current_status = issue_doc.status

        # Get all statuses for the project except the current one
        statuses = frappe.db.sql(
            """
            SELECT s.name
            FROM `tabGRM Issue Status` s
            INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
            WHERE p.project = %s
            AND s.name != %s
        """,
            (project, current_status),
            as_dict=1,
        )

        return [s.name for s in statuses] if statuses else []
    except Exception as e:
        frappe.log_error(f"Error getting allowed statuses: {str(e)}")
        return []


@frappe.whitelist()
def get_category_stats(category):
    """
    Get statistics for a category
    """
    try:
        if not category:
            return None

        # Get total issues in this category
        total = frappe.db.count("GRM Issue", {"category": category})

        # Get open issues
        category_doc = frappe.get_doc("GRM Issue Category", category)
        if not category_doc:
            return None

        # Find projects linked to this category
        project_links = category_doc.get("grm_project_link", [])
        if not project_links:
            return {"total": total, "open": 0, "avg_resolution_days": None}

        # Get open statuses for all linked projects
        open_statuses = []
        for link in project_links:
            project_open_statuses = get_open_statuses(link.project)
            open_statuses.extend(project_open_statuses)

        # Count open issues
        open_count = (
            frappe.db.count(
                "GRM Issue", {"category": category, "status": ["in", open_statuses]}
            )
            if open_statuses
            else 0
        )

        # Calculate average resolution days
        avg_days = frappe.db.sql(
            """
            SELECT AVG(resolution_days) as avg_days
            FROM `tabGRM Issue`
            WHERE category = %s
            AND resolution_days > 0
        """,
            category,
            as_dict=1,
        )

        avg_resolution_days = (
            round(avg_days[0].avg_days, 1)
            if avg_days and avg_days[0].avg_days
            else None
        )

        return {
            "total": total,
            "open": open_count,
            "avg_resolution_days": avg_resolution_days,
        }
    except Exception as e:
        frappe.log_error(f"Error getting category stats: {str(e)}")
        return {"total": 0, "open": 0, "avg_resolution_days": None}
