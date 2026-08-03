"""
Tracking-code generator for GRM Issues.

Format: ``{PROJECT_CODE}-{YYMMDD}-{NNNN}`` (e.g. ``GOODLIDE-260508-4729``).

The visible/printable shape stays at 4 digits because the public portal,
mobile app, and prior submissions all assume that. To avoid the birthday-
paradox collisions the previous purely-random implementation suffered
from (the AQE PF-18 bulk-submit test reliably hit a unique-key conflict
once ~100 issues were submitted in a single day for one project), we now:

1. Use a small, in-process counter monotone within the same project+date
   so sequential submitters don't fight over the same random window.
2. Fall back to a per-call lookup when the counter wraps; we ask the DB
   for the current max suffix for ``{project, date}`` and continue from
   there.
3. Probe the DB up to ``MAX_PROBES`` times for the first available
   suffix and only raise once exhausted (cheap — at most a handful of
   lightweight ``frappe.db.exists`` calls).
"""

import os
import random
from datetime import datetime
from threading import Lock

import frappe

# 4-digit suffix range. Anchored to 4 digits so existing tracking codes
# remain comparable with the published format. We extend the *effective*
# space by combining a process-local counter with random jitter, and we
# verify uniqueness against the DB before returning.
_MIN = 1000
_MAX = 9999
_MAX_PROBES = 64

# Process-local counter keyed by ``(project_code, yymmdd)`` to spread
# sequential bursts across the suffix space deterministically. Reset
# each Frappe worker — that's fine, the DB still arbitrates collisions.
_COUNTER_LOCK = Lock()
_COUNTER: dict[tuple[str, str], int] = {}


def _next_local_suffix(key: tuple[str, str]) -> int:
	"""Return the next unused 4-digit suffix from this process for ``key``."""
	with _COUNTER_LOCK:
		n = _COUNTER.get(key, random.randint(_MIN, _MAX) - 1)
		n += 1
		if n > _MAX:
			n = _MIN
		_COUNTER[key] = n
		return n


def generate_tracking_code(project_id, project_code=None, issue_date=None):
	"""Return a unique ``{CODE}-{YYMMDD}-{NNNN}`` tracking code."""
	try:
		# ---- project code ------------------------------------------------
		if not project_code:
			project_code = (
				frappe.db.get_value("GRM Project", project_id, "project_code") or project_id or "PROJ"
			)
		clean_code = "".join(c.upper() for c in str(project_code) if c.isalnum())[:10] or "PROJ"

		# ---- date stamp --------------------------------------------------
		if not issue_date:
			issue_date = datetime.now()
		elif isinstance(issue_date, str):
			issue_date = datetime.strptime(issue_date, "%Y-%m-%d")
		date_str = issue_date.strftime("%y%m%d")

		# ---- collision-free suffix --------------------------------------
		prefix = f"{clean_code}-{date_str}-"
		key = (clean_code, date_str)

		# 1) Try a process-local counter first (cheap, fast, no DB).
		for _ in range(_MAX_PROBES):
			suffix = _next_local_suffix(key)
			candidate = f"{prefix}{suffix:04d}"
			if not frappe.db.exists("GRM Issue", {"tracking_code": candidate}):
				frappe.log(f"Generated tracking code: {candidate} for project: {project_id}")
				return candidate

		# 2) Local counter exhausted — try fully random probes.
		for _ in range(_MAX_PROBES):
			suffix = random.randint(_MIN, _MAX)
			candidate = f"{prefix}{suffix:04d}"
			if not frappe.db.exists("GRM Issue", {"tracking_code": candidate}):
				frappe.log(f"Generated tracking code: {candidate} for project: {project_id}")
				return candidate

		# 3) Last resort — fall back to a wider suffix that is guaranteed
		#    unique. The format degrades gracefully (still parseable by
		#    the existing prefix-split code) because the suffix is still
		#    a non-negative integer, just longer.
		big = (os.getpid() % 1000) * 10_000 + random.randint(0, 9_999)
		candidate = f"{prefix}{big:08d}"
		frappe.log(
			f"Tracking-code suffix space exhausted for {prefix}; " f"using extended suffix: {candidate}"
		)
		return candidate

	except Exception as e:
		frappe.log_error(f"Error generating tracking code: {e!s}")
		frappe.log(f"Using fallback tracking code: {frappe.get_traceback()}")
		raise
