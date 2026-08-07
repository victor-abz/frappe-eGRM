"""Mobile app request log.

One row per backend call made by the Android app, uploaded in batches so
administrators can see what the field apps are actually doing: who called
what, how it responded, and which app version they are running.

Rows are written only by ``egrm.api.app_logs.ingest``; the DocType is
``in_create`` so nothing creates them through the desk UI.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime

# Logs are a debugging aid, not a permanent record. Anything older than this
# is dropped by the daily cleanup so the table cannot grow without bound.
RETENTION_DAYS = 30


class GRMAppRequestLog(Document):
	pass


def delete_old_logs() -> None:
	"""Daily scheduler hook: drop request logs past the retention window."""
	cutoff = add_days(now_datetime(), -RETENTION_DAYS)
	frappe.db.delete("GRM App Request Log", {"log_time": ("<", cutoff)})
	frappe.db.commit()
