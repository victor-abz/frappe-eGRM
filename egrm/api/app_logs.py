"""Mobile app request-log ingestion.

The Android app buffers the backend calls it makes and uploads them here in
batches, so administrators can aggregate field activity in the desk: who is
using the app, which endpoints fail, and which app versions are deployed.

The app already redacts credentials before buffering; this endpoint applies
its own caps and never trusts the client for identity.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint

# Caps applied server-side regardless of what the client sends, so a buggy or
# hostile client cannot fill the table or a single row.
MAX_BATCH = 200
MAX_BODY_CHARS = 4000
MAX_ENDPOINT_CHARS = 500


def _truncate(value, limit: int):
	if value is None:
		return None
	text = value if isinstance(value, str) else str(value)
	if len(text) <= limit:
		return text
	return f"{text[:limit]}… [truncated {len(text) - limit} chars]"


@frappe.whitelist(methods=["POST"])
def ingest(logs=None) -> dict:
	"""Store a batch of client request logs.

	``logs`` is a list (or JSON-encoded list) of entries with the keys
	``timestamp``, ``method``, ``url``, ``status``, ``durationMs``,
	``requestBody``, ``responseBody``, ``error``, ``appVersion``,
	``runtimeVersion`` and ``platform``.

	The owning user is taken from the session, never from the payload, so a
	client cannot attribute its activity to somebody else.

	Returns the number of rows accepted, and how many were dropped because the
	batch exceeded ``MAX_BATCH``.
	"""
	if isinstance(logs, str):
		try:
			logs = json.loads(logs)
		except ValueError:
			frappe.throw(_("logs must be a JSON array"))

	if not isinstance(logs, list):
		frappe.throw(_("logs must be a JSON array"))

	dropped = max(0, len(logs) - MAX_BATCH)
	batch = logs[:MAX_BATCH]
	user = frappe.session.user

	accepted = 0
	for entry in batch:
		if not isinstance(entry, dict):
			continue

		status = cint(entry.get("status"))
		doc = frappe.get_doc(
			{
				"doctype": "GRM App Request Log",
				"log_time": entry.get("timestamp") or frappe.utils.now(),
				"user": user,
				"app_version": _truncate(entry.get("appVersion"), 40),
				"runtime_version": _truncate(entry.get("runtimeVersion"), 40),
				"platform": _truncate(entry.get("platform"), 60),
				"method": _truncate(entry.get("method"), 10),
				"endpoint": _truncate(entry.get("url"), MAX_ENDPOINT_CHARS),
				"http_status": status,
				"duration_ms": cint(entry.get("durationMs")),
				# status 0 means the request never completed (offline, timeout,
				# abort) — as much a failure as a 4xx/5xx for triage purposes.
				"is_error": 1 if (status == 0 or status >= 400) else 0,
				"request_body": _truncate(entry.get("requestBody"), MAX_BODY_CHARS),
				"response_body": _truncate(entry.get("responseBody"), MAX_BODY_CHARS),
				"error": _truncate(entry.get("error"), 500),
			}
		)
		doc.insert(ignore_permissions=True)
		accepted += 1

	frappe.db.commit()

	return {"accepted": accepted, "dropped": dropped}
