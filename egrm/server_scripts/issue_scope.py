"""Region scoping for GRM Issue visibility.

Holding a duty on a project says *what* a government worker may do; this
module says *which* grievances they may do it to. A worker sees an issue
when it sits in their assigned administrative region (or anywhere beneath
it in the hierarchy), or when they personally handled it at some point —
the second half is what keeps an escalated grievance on the desk of the
officer who escalated it, even though escalation moves the issue into the
region above them.

Every rule here exists twice on purpose: once as a SQL predicate for
list/report queries (permission_query_conditions) and once in Python for
the per-document check (has_permission). Both are built from the same
``user_region_scope`` map so the desk list and the desk form cannot
disagree about what is visible.

Used by egrm.server_scripts.grm_issue_permissions.
"""

import logging

import frappe

log = logging.getLogger(__name__)

__all__ = [
	"HANDLED_BY_FIELDS",
	"handled_by_user_condition",
	"has_handled",
	"is_in_user_scope",
	"region_condition",
	"sql_literal",
	"user_region_scope",
]

# Fields that record "this user handled this issue at some point". An issue
# stays visible to everyone named in one of these fields even after it
# leaves their region, so a worker never loses sight of a grievance they
# personally touched. The escalation child table counts too — see
# has_handled / handled_by_user_condition.
HANDLED_BY_FIELDS: tuple[str, ...] = (
	"owner",
	"reporter",
	"assignee",
	"escalated_by",
	"resolved_by",
	"rejected_by",
)

ACTIVE_ASSIGNMENT_FILTERS: dict = {
	"is_active": 1,
	"activation_status": ["in", ("Activated", "")],
}


def sql_literal(value: str) -> str:
	"""Quote a Python string as a SQL string literal.

	Escapes BOTH backslashes (the MySQL string-literal escape character)
	and single quotes, so a region path or project code containing either
	cannot break out of the literal.
	"""
	return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _descendant_prefix_test(path: str) -> str:
	"""SQL predicate matching every region *under* ``path``.

	Deliberately LEFT()/= rather than ``LIKE 'path:%'``. A permission
	condition is spliced into queries that are later run with bind
	parameters, and MySQLdb re-runs %-formatting over the finished SQL:
	a literal ``%`` from a LIKE pattern blows up with "not enough
	arguments for format string". LEFT() also sidesteps LIKE's wildcard
	escaping entirely, so a region named "50%_Sector" cannot widen the
	match. The comparison runs against a single row (the correlated
	subquery pins _r by primary key), so losing index-friendliness costs
	nothing here.
	"""
	prefix = f"{path}:"
	return f"LEFT(_r.path, {len(prefix)}) = {sql_literal(prefix)}"


def user_region_scope(user: str) -> dict[str, dict]:
	"""Map each in-scope project to the region scope the user holds on it.

	Returns ``{project: {"all": bool, "regions": set[str], "paths": set[str]}}``
	covering only projects where the user's assignment role carries at least
	one duty (an assignment to a duty-less role grants nothing).

	``all`` is True when at least one assignment on that project leaves
	``administrative_region`` blank — that field is optional on GRM User
	Project Assignment, and an assignment with no region has always meant
	"the whole project", so it keeps that meaning here.

	Regions are kept as names plus materialized paths, and descendants are
	matched by path prefix at query time rather than expanded into a name
	list, so a national-level assignment does not turn every list query
	into a 15,000-element IN clause.
	"""
	scope: dict[str, dict] = {}
	if not user or user == "Guest":
		return scope

	rows = frappe.get_all(
		"GRM User Project Assignment",
		filters={"user": user, **ACTIVE_ASSIGNMENT_FILTERS},
		fields=["project", "role", "administrative_region"],
		ignore_permissions=True,
	)
	if not rows:
		return scope

	role_has_duty: dict[str, bool] = {}
	region_names: set[str] = set()
	for row in rows:
		if row.role not in role_has_duty:
			role_has_duty[row.role] = bool(
				frappe.get_all(
					"GRM Project Role Duty",
					filters={"parent": row.role},
					pluck="duty",
					ignore_permissions=True,
				)
			)
		if not role_has_duty[row.role]:
			continue

		entry = scope.setdefault(row.project, {"all": False, "regions": set(), "paths": set()})
		if not row.administrative_region:
			entry["all"] = True
			continue
		entry["regions"].add(row.administrative_region)
		region_names.add(row.administrative_region)

	if region_names:
		path_by_region = {
			r.name: r.path
			for r in frappe.get_all(
				"GRM Administrative Region",
				filters={"name": ["in", list(region_names)]},
				fields=["name", "path"],
				ignore_permissions=True,
			)
		}
		for entry in scope.values():
			entry["paths"] = {path_by_region[r] for r in entry["regions"] if path_by_region.get(r)}

	return scope


def region_condition(entry: dict) -> str:
	"""SQL predicate: the issue's region sits inside this project scope.

	Mirrors ``assignee_routing.is_user_in_scope`` (the gate deciding where
	staff may *raise* an issue) so the read side and the write side agree
	on what "my region" means: the assigned region itself, or any region
	beneath it in the hierarchy.

	An issue whose region is blank or dangling matches nothing here and so
	is visible only to bypass roles — administrative_region is a required
	field, so that state means the row needs repair, not that it should be
	broadcast to every officer on the project.
	"""
	if entry["all"]:
		return "1=1"

	tests: list[str] = []
	if entry["regions"]:
		names = ", ".join(sql_literal(r) for r in sorted(entry["regions"]))
		tests.append(f"_r.name IN ({names})")
	tests.extend(_descendant_prefix_test(p) for p in sorted(entry["paths"]))
	if not tests:
		return "1=0"

	return (
		"EXISTS (SELECT 1 FROM `tabGRM Administrative Region` _r"
		" WHERE _r.name = `tabGRM Issue`.administrative_region"
		f" AND ({' OR '.join(tests)}))"
	)


def handled_by_user_condition(user: str) -> str:
	"""SQL predicate: this user personally handled the issue at some point.

	Keeps an issue visible after it moves out of the user's region — most
	importantly after they escalate it, which reparents the issue to the
	region above them and would otherwise make it vanish from the desk of
	the very person who raised the escalation.
	"""
	safe = sql_literal(user)
	tests = [f"`tabGRM Issue`.{field} = {safe}" for field in HANDLED_BY_FIELDS]
	tests.append(
		"EXISTS (SELECT 1 FROM `tabGRM Issue Escalation Reason` _er"
		" WHERE _er.parent = `tabGRM Issue`.name"
		" AND _er.parenttype = 'GRM Issue'"
		f" AND _er.user = {safe})"
	)
	return f"({' OR '.join(tests)})"


def has_handled(doc, user: str) -> bool:
	"""Python twin of handled_by_user_condition, for the doc-level check."""
	for field in HANDLED_BY_FIELDS:
		if getattr(doc, field, None) == user:
			return True

	escalations = getattr(doc, "grm_issue_escalation_reason", None)
	if escalations is None:
		# Doc loaded without its child rows — ask the database instead.
		name = getattr(doc, "name", None)
		if not name:
			return False
		return bool(
			frappe.db.exists(
				"GRM Issue Escalation Reason",
				{"parent": name, "parenttype": "GRM Issue", "user": user},
			)
		)
	return any(getattr(row, "user", None) == user for row in escalations)


def is_in_user_scope(doc, user: str, project: str) -> bool:
	"""Doc-level twin of the region + handled-by-me rules used in SQL.

	Built on the same ``user_region_scope`` map as the list query so the
	two surfaces cannot drift: a doc the desk list shows is a doc the form
	will open, and vice versa. The hierarchy test is the path-prefix form
	of ``assignee_routing.is_user_in_scope``.
	"""
	if has_handled(doc, user):
		return True

	entry = user_region_scope(user).get(project)
	if not entry:
		return False
	if entry["all"]:
		return True

	region = getattr(doc, "administrative_region", None)
	if not region:
		return False
	if region in entry["regions"]:
		return True

	path = frappe.db.get_value("GRM Administrative Region", region, "path")
	if not path:
		return False
	return any(path.startswith(f"{parent}:") for parent in entry["paths"])
