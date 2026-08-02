"""
EGRM API - Issue Management Endpoints
-----------------------------------
This module contains API endpoints for managing GRM issues.
"""

import json
import logging

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

from egrm.api._roles import GRM_ALL_PROJECTS_ROLES

# `create_issue_from_sync` was removed when sync.py was refactored to the
# WatermelonDB-style protocol. We now route create() through sync.create_record.
from egrm.api.sync import create_record as _sync_create_record
from egrm.utils.project_access import get_user_accessible_projects

# Configure logging
log = logging.getLogger(__name__)


# Drafts (docstatus=0 GRM Issues) are private to their owner. Bypass roles
# can still see other users' drafts via the API; everyone else gets the
# same "not found" response whether the draft doesn't exist or simply
# belongs to another duty-holder. This mirrors permission_query_conditions
# / has_permission in server_scripts/grm_issue_permissions.py so the desk
# and the API layer agree on visibility.
_DRAFT_BYPASS_ROLES = frozenset({"System Manager", "GRM Platform Administrator", "GRM Supervise"})


def _user_can_see_others_drafts(user):
	if user == "Administrator":
		return True
	return bool(_DRAFT_BYPASS_ROLES.intersection(frappe.get_roles(user)))


def _validate_creator_scope(issue_data: dict, user: str) -> dict | None:
	"""Reject create() when staff raise an issue outside their region scope.

	Returns ``None`` when the create may proceed, or an error envelope
	when the user does not have an active assignment in the issue's
	administrative region (or any ancestor). Bypass roles skip the gate.
	"""
	if user == "Administrator":
		return None
	if _DRAFT_BYPASS_ROLES.intersection(frappe.get_roles(user)):
		return None
	project = issue_data.get("project")
	region = issue_data.get("administrative_region")
	if not project or not region:
		# Let the downstream sync.create_record raise a normal validation
		# error so the missing-fields message stays consistent.
		return None
	from egrm.services.assignee_routing import is_user_in_scope

	if not is_user_in_scope(user, project, region):
		return {
			"status": "error",
			"message": _("You can only raise issues inside your assigned region(s)."),
			"code": "OUT_OF_SCOPE",
		}
	return None


def _draft_or_filters(user):
	"""Return an or_filters list that hides other users' drafts, or None
	when the user is allowed to see everything."""
	if _user_can_see_others_drafts(user):
		return None
	return [["docstatus", ">", 0], ["owner", "=", user]]


def _draft_blocks_access(issue_id, user):
	"""True when this issue is a draft owned by someone else and the user
	is not a bypass role. Callers should return a 'not found' response so
	the existence of another user's draft is not leaked."""
	if _user_can_see_others_drafts(user):
		return False
	row = frappe.db.get_value("GRM Issue", issue_id, ("docstatus", "owner"), as_dict=True)
	if not row:
		return False
	return (row.get("docstatus") or 0) == 0 and row.get("owner") != user


@frappe.whitelist()
def list(project_id=None, status=None, assignee=None, reporter=None, limit=50, offset=0):
	"""
	List issues with filters

	Args:
	    project_id (str, optional): Project ID
	    status (str, optional): Status filter
	    assignee (str, optional): Assignee filter
	    reporter (str, optional): Reporter filter
	    limit (int): Number of records to return
	    offset (int): Offset for pagination

	Returns:
	    dict: List of issues
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Listing issues for user: {user}")

		# Build filters
		filters = {}
		if project_id:
			filters["project"] = project_id
		if status:
			filters["status"] = status
		if assignee:
			filters["assignee"] = assignee
		if reporter:
			filters["reporter"] = reporter

		# Get user's accessible projects if no specific project
		if not project_id:
			accessible_projects = get_user_accessible_projects(user)
			if accessible_projects:
				filters["project"] = ["in", accessible_projects]
			else:
				# User has no project access
				return {"status": "success", "data": []}

		# Get issues. or_filters keeps drafts private to their owner —
		# frappe.get_all bypasses permission_query_conditions, so without
		# this another user's draft would leak through the API even though
		# the desk list correctly hides it.
		issues = frappe.get_all(
			"GRM Issue",
			filters=filters,
			or_filters=_draft_or_filters(user),
			fields=[
				"name",
				"tracking_code",
				"description",
				"status",
				"assignee",
				"reporter",
				"citizen",
				"citizen_type",
				"citizen_age_group",
				"citizen_group_1",
				"citizen_group_2",
				"gender",
				"category",
				"issue_type",
				"resolution_days",
				"resolution_date",
				"intake_date",
				"issue_date",
				"administrative_region",
				"confirmed",
				"resolution_accepted",
				"rating",
				"escalate_flag",
				"project",
				"contact_information",
				"contact_medium",
				"creation",
				"owner",
				"docstatus",
			],
			limit=limit,
			start=offset,
			order_by="creation desc",
		)

		# Enhance issue data
		for issue in issues:
			# Get status details
			if issue.status:
				status_doc = frappe.get_doc("GRM Issue Status", issue.status)
				issue.status_details = {
					"id": status_doc.name,
					"name": status_doc.status_name,
					"final_status": status_doc.final_status,
					"initial_status": status_doc.initial_status,
					"open_status": status_doc.open_status,
					"rejected_status": status_doc.rejected_status,
				}

			# Get category details
			if issue.category:
				category_doc = frappe.get_doc("GRM Issue Category", issue.category)
				issue.category_details = {
					"id": category_doc.name,
					"name": category_doc.category_name,
					"confidentiality_level": category_doc.confidentiality_level,
				}

			# Get issue type details
			if issue.issue_type:
				type_doc = frappe.get_doc("GRM Issue Type", issue.issue_type)
				issue.type_details = {"id": type_doc.name, "name": type_doc.type_name}

			# Get administrative region details
			if issue.administrative_region:
				region_doc = frappe.get_doc("GRM Administrative Region", issue.administrative_region)
				issue.region_details = {
					"administrative_id": region_doc.name,
					"name": region_doc.region_name,
					"latitude": getattr(region_doc, "latitude", None),
					"longitude": getattr(region_doc, "longitude", None),
				}

			# Get attachments / logs / comments (field names match the
			# current child doctype schema — see grm_issue_attachment.json,
			# grm_issue_log.json, grm_issue_comment.json).
			issue.attachments = frappe.get_all(
				"GRM Issue Attachment",
				filters={"parent": issue.name},
				fields=["name", "attachment", "file_name", "local_url", "uploaded"],
			)
			issue.logs = frappe.get_all(
				"GRM Issue Log",
				filters={"parent": issue.name},
				fields=["text", "user", "timestamp", "action_taken"],
				order_by="timestamp desc",
			)
			issue.comments = frappe.get_all(
				"GRM Issue Comment",
				filters={"parent": issue.name},
				fields=["name", "user", "comment", "creation"],
				order_by="creation desc",
			)

		frappe.log(f"Returning {len(issues)} issues")
		return {"status": "success", "data": issues}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in list_issues: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get(issue_id):
	"""
	Get a single issue with full details

	Args:
	    issue_id (str): Issue ID

	Returns:
	    dict: Issue details
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting issue {issue_id} for user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts are private to their owner — return the same 'not found'
		# response a non-existent issue would yield so the existence of
		# another user's draft is not leaked through the API.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if user has permission to read the issue
		if not frappe.has_permission("GRM Issue", "read", issue_id):
			log.warning(f"User {user} does not have permission to read issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to access this issue"),
			}

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Convert to dict and enhance
		issue_dict = issue.as_dict()

		# Get related data
		if issue_dict.get("status"):
			status_doc = frappe.get_doc("GRM Issue Status", issue_dict["status"])
			issue_dict["status_details"] = status_doc.as_dict()

		if issue_dict.get("category"):
			category_doc = frappe.get_doc("GRM Issue Category", issue_dict["category"])
			issue_dict["category_details"] = category_doc.as_dict()

		if issue_dict.get("issue_type"):
			type_doc = frappe.get_doc("GRM Issue Type", issue_dict["issue_type"])
			issue_dict["type_details"] = type_doc.as_dict()

		if issue_dict.get("administrative_region"):
			region_doc = frappe.get_doc("GRM Administrative Region", issue_dict["administrative_region"])
			issue_dict["region_details"] = region_doc.as_dict()

		frappe.log(f"Returning issue {issue_id}")
		return {"status": "success", "data": issue_dict}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create(issue_data):
	"""
	Create a new issue using the sync creation logic for consistency

	Args:
	    issue_data (dict): Issue data

	Returns:
	    dict: Created issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Creating issue for user: {user}")

		# Parse issue data if it's a string
		if isinstance(issue_data, str):
			issue_data = json.loads(issue_data)

		# Route through the WatermelonDB-style sync.create_record so issue.create()
		# and the offline-sync path always produce structurally identical records.
		record_id = issue_data.get("id") if isinstance(issue_data, dict) else None
		if not record_id:
			return {
				"status": "error",
				"message": _("Missing 'id' on issue payload"),
			}

		# Staff raising an issue must do so inside their assigned region(s).
		# Bypass roles (Administrator / System Manager / Platform Admin /
		# Supervise) skip the gate so admin-desk creation isn't blocked.
		scope_error = _validate_creator_scope(issue_data, user)
		if scope_error:
			return scope_error

		try:
			_sync_create_record("GRM Issue", issue_data)
		except frappe.PermissionError as pe:
			return {"status": "error", "message": str(pe)}
		except Exception as e:
			frappe.log_error(f"Error creating issue via sync.create_record: {e}")
			return {"status": "error", "message": str(e)}

		if not frappe.db.exists("GRM Issue", record_id):
			return {
				"status": "error",
				"message": _("Issue creation failed; record not found"),
			}

		issue = frappe.get_doc("GRM Issue", record_id)
		frappe.log(f"Issue {issue.name} created and submitted")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in create_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def update(issue_id, issue_data):
	"""
	Update an existing issue

	Args:
	    issue_id (str): Issue ID
	    issue_data (dict): Updated issue data

	Returns:
	    dict: Updated issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Updating issue {issue_id} for user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if user has permission to update the issue
		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} does not have permission to update issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to update this issue"),
			}

		# Parse issue data if it's a string
		if isinstance(issue_data, str):
			issue_data = json.loads(issue_data)

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Track changes for logging
		changes = []

		# Update fields. Field names track the GRM Issue DocType schema —
		# `citizen_name`/`title` no longer exist; the canonical names
		# under the duty-driven schema are `citizen` (display name) and
		# `description` (issue body). `getattr(issue, field, MISSING)`
		# is used so a deployment that customises the schema doesn't
		# crash with AttributeError on a missing field.
		updatable_fields = [
			"description",
			"citizen",
			"citizen_type",
			"citizen_age_group",
			"citizen_group_1",
			"citizen_group_2",
			"gender",
			"contact_medium",
			"contact_information",
			"ongoing_issue",
			"confirmed",
			"resolution_accepted",
			"rating",
			"research_result",
			"reject_reason",
		]

		_MISSING = object()
		for field in updatable_fields:
			current = getattr(issue, field, _MISSING)
			if current is _MISSING:
				continue
			if field in issue_data and current != issue_data[field]:
				old_value = current
				setattr(issue, field, issue_data[field])
				changes.append(f"{field}: {old_value} → {issue_data[field]}")

		# Update related fields
		if "status" in issue_data and issue.status != issue_data["status"]:
			old_status = issue.status
			issue.status = issue_data["status"]
			changes.append(f"status: {old_status} → {issue_data['status']}")

		# Save issue
		issue.save()

		# Add update log if there were changes. GRM Issue Log child uses
		# text/user/timestamp (the legacy log_type/log_by/log_date/description
		# field names were dropped in the duty-driven schema rev — passing
		# them in caused "Value missing for: Log Entry/User/Timestamp"
		# validation errors and made the controller return status=error
		# even when the field-level update itself had succeeded).
		if changes:
			issue.append(
				"grm_issue_log",
				{
					"text": f"Updated: {', '.join(changes)}",
					"user": user,
					"timestamp": now_datetime(),
					"action_taken": "Updated",
					"action_taken_by": user,
					"action_taken_date": now_datetime(),
				},
			)
			issue.save()

		frappe.log(f"Updated issue {issue_id}")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in update_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def assign(issue_id, assignee_id):
	"""
	Assign an issue to a user

	Args:
	    issue_id (str): Issue ID
	    assignee_id (str): User ID to assign to

	Returns:
	    dict: Updated issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Assigning issue {issue_id} to {assignee_id} by user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if assignee exists
		if not frappe.db.exists("User", assignee_id):
			log.warning(f"Assignee {assignee_id} not found")
			return {"status": "error", "message": _("Assignee not found")}

		# Check if user has permission to assign the issue
		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} does not have permission to assign issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to assign this issue"),
			}

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Update assignee
		issue.assignee = assignee_id

		# Update status to accepted if it's initial
		if issue.status:
			status_doc = frappe.get_doc("GRM Issue Status", issue.status)
			if status_doc.initial_status:
				# Find accepted status — MUST be project-scoped AND not the
				# initial status itself, otherwise we either leak another
				# project's status or leave the issue in its starting bucket.
				accepted_status = frappe.get_all(
					"GRM Issue Status",
					filters={
						"open_status": 1,
						"initial_status": 0,
						"project": issue.project,
					},
					fields=["name"],
					limit=1,
				)
				if accepted_status:
					issue.status = accepted_status[0].name

		# Save issue
		issue.save()

		# Add assignment log (text/user/timestamp — see update() for context).
		assignee_name = frappe.get_value("User", assignee_id, "full_name")
		issue.append(
			"grm_issue_log",
			{
				"text": f"Assigned to {assignee_name}",
				"user": user,
				"timestamp": now_datetime(),
				"action_taken": "Assigned",
				"action_taken_by": user,
				"action_taken_date": now_datetime(),
			},
		)
		issue.save()

		frappe.log(f"Assigned issue {issue_id} to {assignee_id}")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in assign_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def resolve(issue_id, resolution_text=None):
	"""
	Resolve an issue

	Args:
	    issue_id (str): Issue ID
	    resolution_text (str, optional): Resolution description

	Returns:
	    dict: Updated issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Resolving issue {issue_id} by user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if user has permission to resolve the issue
		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} does not have permission to resolve issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to resolve this issue"),
			}

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Find resolved status — MUST be project-scoped to avoid picking up
		# a final status from a different project (each GRM Project owns
		# its own status taxonomy).
		resolved_status = frappe.get_all(
			"GRM Issue Status",
			filters={"final_status": 1, "project": issue.project},
			fields=["name"],
			limit=1,
		)

		if not resolved_status:
			log.warning(f"No resolved status found for project {issue.project}")
			return {"status": "error", "message": _("No resolved status configured")}

		# Update issue
		issue.status = resolved_status[0].name
		issue.resolution_date = now_datetime()
		if resolution_text:
			issue.research_result = resolution_text

		# Save issue
		issue.save()

		# Add resolution log (text/user/timestamp — see update() for context).
		issue.append(
			"grm_issue_log",
			{
				"text": f"Resolved: {resolution_text or 'No description provided'}",
				"user": user,
				"timestamp": now_datetime(),
				"action_taken": "Resolved",
				"action_taken_by": user,
				"action_taken_date": now_datetime(),
			},
		)
		issue.save()

		frappe.log(f"Resolved issue {issue_id}")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in resolve_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def reopen(issue_id, reason=None):
	"""
	Reopen a resolved issue

	Args:
	    issue_id (str): Issue ID
	    reason (str, optional): Reason for reopening

	Returns:
	    dict: Updated issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Reopening issue {issue_id} by user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if user has permission to reopen the issue
		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} does not have permission to reopen issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to reopen this issue"),
			}

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Find reopened status
		reopened_status = get_reopened_status(issue.project)
		if not reopened_status:
			log.warning("No reopened status found")
			return {"status": "error", "message": _("No reopened status configured")}

		# Update issue
		issue.status = reopened_status
		issue.resolution_date = None

		# Save issue
		issue.save()

		# Add reopen log (text/user/timestamp — see update() for context).
		issue.append(
			"grm_issue_log",
			{
				"text": f"Reopened: {reason or 'No reason provided'}",
				"user": user,
				"timestamp": now_datetime(),
				"action_taken": "Reopened",
				"action_taken_by": user,
				"action_taken_date": now_datetime(),
			},
		)
		issue.save()

		frappe.log(f"Reopened issue {issue_id}")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in reopen_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def escalate(issue_id, reason=None):
	"""
	Escalate an issue

	Args:
	    issue_id (str): Issue ID
	    reason (str, optional): Reason for escalation

	Returns:
	    dict: Updated issue
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Escalating issue {issue_id} by user: {user}")

		# Check if issue exists
		if not frappe.db.exists("GRM Issue", issue_id):
			log.warning(f"Issue {issue_id} not found")
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		# Check if user has permission to escalate the issue
		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} does not have permission to escalate issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to escalate this issue"),
			}

		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Set escalation flag and tracking fields
		issue.escalate_flag = True
		issue.escalated_date = now_datetime()
		issue.escalated_by = user
		if reason:
			issue.escalation_reason = reason
			# Append a row to the grm_issue_escalation_reason child table
			# (the legacy `escalation_reasons` attr did not exist on the
			# GRMIssue controller — passing it caused an
			# AttributeError and made the controller return status=error
			# while leaving the issue partially escalated).
			try:
				# GRM Issue Escalation Reason child fields:
				# user (Link User, reqd), comment (Data, reqd),
				# due_at (Datetime, reqd).
				from frappe.utils import add_days

				issue.append(
					"grm_issue_escalation_reason",
					{
						"user": user,
						"comment": reason,
						"due_at": add_days(now_datetime(), 7),
					},
				)
			except Exception:
				# The child table fieldset may differ by deployment; fall
				# through silently — the parent-level tracking fields
				# above are the canonical record.
				pass

		# Save issue
		issue.save()

		# Add escalation log (text/user/timestamp — see update() for context).
		issue.append(
			"grm_issue_log",
			{
				"text": f"Escalated: {reason or 'No reason provided'}",
				"user": user,
				"timestamp": now_datetime(),
				"action_taken": "Escalated",
				"action_taken_by": user,
				"action_taken_date": now_datetime(),
			},
		)
		issue.save()

		frappe.log(f"Escalated issue {issue_id}")
		return {"status": "success", "data": issue.as_dict()}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in escalate_issue: {e!s}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_latest_issues(last_sync_timestamp=None, limit=50, offset=0):
	"""
	Get issues created after the last sync timestamp.
	This is a lightweight endpoint that only returns essential issue data.

	Args:
	    last_sync_timestamp (str, optional): Last sync timestamp in ISO format
	    limit (int): Maximum number of issues to return
	    offset (int): Offset for pagination

	Returns:
	    dict: {
	        "data": List of issues created after the timestamp,
	        "total_count": Total number of issues matching the criteria,
	        "has_more": Boolean indicating if there are more issues to load
	    }
	"""
	try:
		user = frappe.session.user
		frappe.log(f"Getting latest issues for user: {user}, last_sync: {last_sync_timestamp}")

		# Parse timestamp
		if last_sync_timestamp:
			try:
				last_sync = get_datetime(last_sync_timestamp)
			except (ValueError, TypeError):
				last_sync = None
		else:
			last_sync = None

		# Get user's accessible projects
		accessible_projects = get_user_accessible_projects(user)
		if not accessible_projects:
			return {
				"status": "success",
				"data": {"issues": [], "total_count": 0, "has_more": False},
			}

		# Build filters. List form lets us add the draft-visibility AND
		# clause alongside the OR of (docstatus>0, owner=user) via or_filters
		# below, which matches frappe.get_all's compound-where semantics.
		filters = [["project", "in", accessible_projects]]
		if last_sync:
			filters.append(["creation", ">", last_sync])

		draft_or = _draft_or_filters(user)

		# Get total count first (mirror the same filter shape so the
		# "has_more" computation doesn't lie when drafts are hidden).
		if draft_or:
			total_count = frappe.db.count(
				"GRM Issue",
				filters=[*filters, ["docstatus", ">", 0]],
			) + frappe.db.count(
				"GRM Issue",
				filters=[*filters, ["docstatus", "=", 0], ["owner", "=", user]],
			)
		else:
			total_count = frappe.db.count("GRM Issue", filters=filters)

		# Get paginated issues with minimal fields for efficiency
		issues = frappe.get_all(
			"GRM Issue",
			filters=filters,
			or_filters=draft_or,
			fields=[
				"name",
				"description",
				"status",
				"assignee",
				"reporter",
				"category",
				"issue_type",
				"creation",
				"modified",
				"administrative_region",
				"project",
				"confirmed",
				"resolution_accepted",
				"escalate_flag",
				"owner",
				"docstatus",
			],
			limit=cint(limit),
			start=cint(offset),
			order_by="creation desc",
		)

		# Enhance with minimal required related data
		for issue in issues:
			# Get status details
			if issue.status:
				status_doc = frappe.get_doc("GRM Issue Status", issue.status)
				issue.status_details = {
					"id": status_doc.name,
					"name": status_doc.status_name,
					"final_status": status_doc.final_status,
				}

			# Get category details
			if issue.category:
				category_doc = frappe.get_doc("GRM Issue Category", issue.category)
				issue.category_details = {
					"id": category_doc.name,
					"name": category_doc.category_name,
				}

			# Get administrative region details
			if issue.administrative_region:
				region_doc = frappe.get_doc("GRM Administrative Region", issue.administrative_region)
				issue.region_details = {
					"administrative_id": region_doc.name,
					"name": region_doc.region_name,
				}

		has_more = total_count > (cint(offset) + len(issues))

		frappe.log(f"Returning {len(issues)} latest issues")
		return {
			"status": "success",
			"data": {
				"issues": issues,
				"total_count": total_count,
				"has_more": has_more,
			},
		}

	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error in get_latest_issues: {e!s}")
		return {"status": "error", "message": str(e)}


# Utility functions


def get_reopened_status(project_id):
	"""
	Get reopened status for a project

	Args:
	    project_id (str): Project ID

	Returns:
	    str: Reopened status ID
	"""
	# Find a status with "reopen" or "reopened" in the name — project-scoped.
	statuses = frappe.get_all(
		"GRM Issue Status",
		filters=[
			["status_name", "like", "%reopen%"],
			["project", "=", project_id],
		],
		fields=["name"],
	)

	if statuses:
		return statuses[0].name

	# Fallback: Get first non-final status in the same project.
	statuses = frappe.get_all(
		"GRM Issue Status",
		filters={"final_status": 0, "project": project_id},
		fields=["name"],
	)

	if statuses:
		return statuses[0].name

	return None


def user_has_project_access(user, project_id):
	"""
	Check if a user has access to a project

	Args:
	    user (str): User ID
	    project_id (str): Project ID

	Returns:
	    bool: True if user has access, False otherwise
	"""
	# Check if user is Administrator or has an all-projects GRM role (full access)
	if user == "Administrator" or GRM_ALL_PROJECTS_ROLES & set(frappe.get_roles(user)):
		return True

	# Check if user is assigned to project
	assignments = frappe.get_all(
		"GRM User Project Assignment",
		filters={"user": user, "project": project_id, "is_active": 1},
		fields=["name"],
	)

	return len(assignments) > 0


def user_has_region_access(user, region_id):
	"""
	Check if a user has access to a region

	Args:
	    user (str): User ID
	    region_id (str): Region ID

	Returns:
	    bool: True if user has access, False otherwise
	"""
	# Check if user is Administrator or has System Manager role (full access)
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	# For now, return True
	# This would need to be implemented based on how regional assignments are stored
	return True


def create_log_entry(issue_id, log_type, user, description):
	"""
	Create a log entry for an issue

	Args:
	    issue_id (str): Issue ID
	    log_type (str): Log type
	    user (str): User ID
	    description (str): Log description

	Returns:
	    None
	"""
	try:
		# Get issue
		issue = frappe.get_doc("GRM Issue", issue_id)

		# Add log entry (text/user/timestamp — see update() for context).
		issue.append(
			"grm_issue_log",
			{
				"text": description,
				"user": user,
				"timestamp": get_datetime(),
				"action_taken": log_type,
				"action_taken_by": user,
				"action_taken_date": get_datetime(),
			},
		)

		# Save issue
		issue.save()

		frappe.log(f"Created log entry for issue {issue_id}: {log_type} - {description}")
	except Exception as e:
		print(frappe.get_traceback())
		frappe.log_error(f"Error creating log entry for issue {issue_id}: {e!s}")


@frappe.whitelist()
def upload_attachment(issue_id=None, attachment_data=None):
	"""
	Append a single attachment row to an existing issue.

	Mobile contract (DataManager.uploadAttachment):
	    body = {
	        "issue_id": <GRM Issue.name>,
	        "attachment_data": {
	            "issue": <GRM Issue.name>,
	            "attachment_url": <File doc URL or local URI>,
	            "attachment_name": <display name>,
	            "created_at": <ms-epoch, optional>,
	        },
	    }

	The bulk attachment-upload path is `egrm.api.sync.push_changes` with embedded
	base64 file_data; this endpoint is a lightweight fallback used when the
	mobile already has a server-resident URL (e.g. file already uploaded as a
	Frappe File doc) and only needs to register the row on the parent issue.
	"""
	user = frappe.session.user
	try:
		if isinstance(attachment_data, str):
			attachment_data = json.loads(attachment_data)

		if not issue_id:
			return {"status": "error", "message": _("issue_id is required")}
		if not isinstance(attachment_data, dict):
			return {
				"status": "error",
				"message": _("attachment_data must be an object"),
			}

		attachment_url = attachment_data.get("attachment_url") or attachment_data.get("attachment")
		attachment_name = attachment_data.get("attachment_name") or attachment_data.get("file_name")
		local_url = attachment_data.get("local_url") or attachment_data.get("attachment_url")

		if not attachment_url:
			return {
				"status": "error",
				"message": _("attachment_url is required"),
			}

		if not frappe.db.exists("GRM Issue", issue_id):
			return {"status": "error", "message": _("Issue not found")}

		# Drafts owned by another user are invisible — surface as not found.
		if _draft_blocks_access(issue_id, user):
			return {"status": "error", "message": _("Issue not found")}

		if not frappe.has_permission("GRM Issue", "write", issue_id):
			log.warning(f"User {user} lacks permission to attach to issue {issue_id}")
			return {
				"status": "error",
				"message": _("You do not have permission to add attachments to this issue"),
			}

		issue = frappe.get_doc("GRM Issue", issue_id)
		row = issue.append(
			"grm_issue_attachment",
			{
				"attachment": attachment_url,
				"file_name": attachment_name,
				"local_url": local_url,
				"uploaded": 1,
			},
		)
		# GRM Issue Attachment is allow_on_submit=1, so child rows may be
		# appended after the parent has been submitted. The duty-driven
		# 'write' check above has already authorised this user to attach
		# to this issue; we elevate the underlying save() because Frappe's
		# check_docstatus_transition demands `submit` DocPerm on any save
		# of a submitted doc, which our admin/duty roles intentionally do
		# not hold (submit/cancel are reserved for Investigate & Resolve /
		# System Manager). The save is bounded to a child-table append.
		if issue.docstatus == 1:
			issue.flags.ignore_validate_update_after_submit = True
		issue.flags.ignore_permissions = True
		issue.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "success",
			"data": {
				"name": row.name,
				"issue": issue_id,
				"attachment": attachment_url,
				"file_name": attachment_name,
				"local_url": local_url,
				"uploaded": 1,
			},
		}
	except frappe.PermissionError as pe:
		return {"status": "error", "message": str(pe)}
	except Exception as e:
		frappe.log_error(
			f"Error in upload_attachment for issue {issue_id}: {e}",
			"egrm.api.issue.upload_attachment",
		)
		return {"status": "error", "message": str(e)}
