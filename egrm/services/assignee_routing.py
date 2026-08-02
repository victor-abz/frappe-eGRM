"""Resolve the User who should own a newly created GRM Issue.

Single entry point: ``resolve_assignee(issue) -> (user, reason)``.

ASSIGNMENT RULE
===============

The rule routes purely on **role + region + duty**. Departments are not
consulted — they are a labeling concern, not a routing concern.

Inputs from the issue: ``project``, ``administrative_region``, ``category``,
optionally ``reporter`` and (for sync/mobile push) an explicit ``assignee``.

Resolution order — first match wins:

* **Explicit override.** If the payload already names an ``assignee``, use it
  verbatim. The mobile sync path uses this to honor manual choices.

* **Case A — staff self-submission.** When a logged-in reporter holds the
  ``Investigate & Resolve`` duty in this project AND has an active
  assignment in the issue's region (or any ancestor in the region's
  parent chain), the reporter becomes the assignee. "Issue is in my
  location → I own it until I reassign."

* **Case B — category routes to a Role** (``routing_target_type = "Role"``).
  Walk the region chain closest-first (exact region, then parents). At
  each level pick the user(s) who are:
    1. actively assigned to (project, role, that region),
    2. hold the ``Investigate & Resolve`` duty via their role.
  The first level with at least one candidate wins; never let an ancestor
  outrank an exact-region match. Among candidates at the winning level,
  pick the one with the lowest current open-issue count
  (tie-break: earliest assignment ``creation``, then ``user`` ASC).

* **No eligible user.** Return ``(None, reason)`` with a structured reason
  code the caller logs onto the issue. The issue is then left unassigned
  for an operator to handle from the desk.

Categories whose ``routing_target_type`` is not ``"Role"`` (legacy
``"Department"`` rows, or NULL) are treated as misconfigured: the resolver
returns ``NO_ROUTING_TARGET:<category>`` and leaves the issue unassigned.
The wizard's category step is the place to fix that.
"""

from __future__ import annotations

import frappe

from egrm.services._constants import ACTIVE_ASSIGNMENT_STATUSES
from egrm.services.category_routing import resolve_category_routing

RESOLVE_DUTY = "Investigate & Resolve"
# Review fix B5: re-exported alias of the single-source-of-truth set in
# ``egrm.services._constants``. Now includes "Pending Activation" so we
# stay in lock-step with ``duty_coverage.compute_coverage``.
ACTIVE_STATUSES = ACTIVE_ASSIGNMENT_STATUSES


# --------------------------------------------------------------------------- #
# Reason codes
# --------------------------------------------------------------------------- #


class Reason:
	EXPLICIT_OVERRIDE = "EXPLICIT_OVERRIDE"
	REPORTER_SELF_SUBMIT = "REPORTER_SELF_SUBMIT"
	ROLE_CANDIDATE = "ROLE_CANDIDATE"
	NO_REGION = "NO_REGION"
	NO_CATEGORY = "NO_CATEGORY"
	NO_ROUTING_TARGET = "CATEGORY_HAS_NO_ROUTING_TARGET"
	NO_RESOLVER_ROLE = "NO_RESOLVER_FOR_ROLE"


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


def resolve_assignee(issue) -> tuple[str | None, str]:
	"""Pick an assignee for ``issue`` (a not-yet-inserted GRM Issue doc).

	Returns ``(user, reason)``. The reason is a structured code suitable
	for logging; the user is ``None`` when no eligible candidate exists.
	Never raises.
	"""
	if getattr(issue, "assignee", None):
		return issue.assignee, Reason.EXPLICIT_OVERRIDE

	project = getattr(issue, "project", None)
	region = getattr(issue, "administrative_region", None)
	if not project or not region:
		return None, Reason.NO_REGION

	# --- Case A: real raiser with duty + scope owns their own issue ------- #
	reporter = getattr(issue, "reporter", None)
	if frappe.session.user != "Guest" and reporter and reporter != "Guest":
		if _is_user_eligible(reporter, project, region):
			return reporter, Reason.REPORTER_SELF_SUBMIT

	# --- Case B: category routes to a Role -------------------------------- #
	category = getattr(issue, "category", None)
	if not category:
		return None, Reason.NO_CATEGORY

	routing = resolve_category_routing(category)
	target_type = routing["target_type"]
	target_name = routing["target_name"]

	if target_type != "Role" or not target_name:
		return None, f"{Reason.NO_ROUTING_TARGET}:{category}"

	region_chain = _region_with_ancestors(region)
	user = _resolve_via_role(project, target_name, region_chain)
	if user:
		return user, f"{Reason.ROLE_CANDIDATE}:{target_name}"
	return None, f"{Reason.NO_RESOLVER_ROLE}:{target_name}"


def is_user_in_scope(user: str, project: str, region: str) -> bool:
	"""Public guard used by the staff create API.

	True when ``user`` has an active project assignment whose region equals
	``region`` or is any ancestor of ``region`` in the same project.
	"""
	if not user or user in ("Guest", "Administrator"):
		return user == "Administrator"
	region_chain = _region_with_ancestors(region)
	if not region_chain:
		return False
	rows = frappe.db.sql(
		"""
        SELECT 1 FROM `tabGRM User Project Assignment`
        WHERE user = %s
          AND project = %s
          AND is_active = 1
          AND activation_status IN %s
          AND administrative_region IN %s
        LIMIT 1
        """,
		(user, project, ACTIVE_STATUSES, tuple(region_chain)),
	)
	return bool(rows)


# --------------------------------------------------------------------------- #
# Case A helper
# --------------------------------------------------------------------------- #


def _is_user_eligible(user: str, project: str, region: str) -> bool:
	"""Eligible = in scope AND holds the resolve duty."""
	if not is_user_in_scope(user, project, region):
		return False
	return _user_holds_resolve_duty(user, project)


def _user_holds_resolve_duty(user: str, project: str) -> bool:
	"""Inline form of ``_user_has_duty`` scoped to the resolve duty.

	Mirrored from ``grm_issue.py`` rather than imported to avoid a circular
	dependency (the doctype controller calls this module on insert).
	"""
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	role_names = frappe.get_all(
		"GRM User Project Assignment",
		filters={
			"user": user,
			"project": project,
			"is_active": 1,
			"activation_status": ["in", list(ACTIVE_STATUSES)],
		},
		pluck="role",
		ignore_permissions=True,
	)
	if not role_names:
		return False
	return bool(
		frappe.get_all(
			"GRM Project Role Duty",
			filters={"parent": ["in", role_names], "duty": RESOLVE_DUTY},
			limit=1,
			ignore_permissions=True,
		)
	)


# --------------------------------------------------------------------------- #
# Case B (Role)
# --------------------------------------------------------------------------- #


def _resolve_via_role(project: str, role: str, region_chain: list[str]) -> str | None:
	"""Walk the region chain closest-first, pick the least-loaded duty-holder
	in (project, role, region) at the first level that has at least one
	candidate."""
	if not region_chain:
		return None
	for region in region_chain:
		candidates = frappe.db.sql(
			"""
            SELECT DISTINCT a.user
            FROM `tabGRM User Project Assignment` a
            JOIN `tabGRM Project Role Duty` prd ON prd.parent = a.role
            WHERE a.project = %s
              AND a.is_active = 1
              AND a.activation_status IN %s
              AND a.administrative_region = %s
              AND a.role = %s
              AND prd.duty = %s
            """,
			(project, ACTIVE_STATUSES, region, role, RESOLVE_DUTY),
			as_dict=True,
		)
		users = [c["user"] for c in candidates]
		if not users:
			continue
		return _pick_least_loaded(users, project)
	return None


def _pick_least_loaded(users: list[str], project: str) -> str | None:
	"""Stable tie-break: open-issue count ASC, assignment.creation ASC, user ASC."""
	if not users:
		return None
	if len(users) == 1:
		return users[0]
	placeholders = ", ".join(["%s"] * len(users))
	rows = frappe.db.sql(
		f"""
        SELECT a.user,
               (
                   SELECT COUNT(*) FROM `tabGRM Issue` i
                   JOIN `tabGRM Issue Status` s ON s.name = i.status
                   WHERE i.assignee = a.user
                     AND i.project = %s
                     AND s.open_status = 1
               ) AS open_count,
               MIN(a.creation) AS first_assigned
        FROM `tabGRM User Project Assignment` a
        WHERE a.user IN ({placeholders})
          AND a.project = %s
        GROUP BY a.user
        ORDER BY open_count ASC, first_assigned ASC, a.user ASC
        LIMIT 1
        """,
		(project, *users, project),
		as_dict=True,
	)
	return rows[0]["user"] if rows else users[0]


# --------------------------------------------------------------------------- #
# Region chain
# --------------------------------------------------------------------------- #


def _region_with_ancestors(region: str) -> list[str]:
	"""Return [region, parent, grandparent, …] within the same project.

	Uses ``GRM Administrative Region.path`` (materialized colon-separated
	path) to walk ancestors in O(1) queries. The list is ordered exact-first
	so callers can prefer closer matches.
	"""
	if not region:
		return []
	region_doc = frappe.db.get_value(
		"GRM Administrative Region",
		region,
		["name", "path", "project"],
		as_dict=True,
	)
	if not region_doc:
		return []
	chain: list[str] = [region_doc["name"]]
	if not region_doc.get("path") or ":" not in region_doc["path"]:
		return chain
	path_parts = region_doc["path"].split(":")
	for i in range(len(path_parts) - 2, -1, -1):
		ancestor_path = ":".join(path_parts[: i + 1])
		ancestor_name = frappe.db.get_value(
			"GRM Administrative Region",
			{"path": ancestor_path, "project": region_doc["project"]},
			"name",
		)
		if ancestor_name and ancestor_name not in chain:
			chain.append(ancestor_name)
	return chain
