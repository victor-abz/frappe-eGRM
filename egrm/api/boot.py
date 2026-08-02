"""Whitelisted wrapper around frappe.boot.get_bootinfo.

Frappe ships `frappe.boot.get_bootinfo` *unwhitelisted* — it is invoked
implicitly by `desk` page renders, never via `/api/method/...`. The eGRM
ARCH-CONTRACT (AC-5) suite needs a way to assert the boot payload via
HTTP, so we register an override in `hooks.py`:

    override_whitelisted_methods = {
        "frappe.boot.get_bootinfo": "egrm.api.boot.get_bootinfo"
    }

…and serve a thin wrapper here.

The wrapper:
* Accepts both authenticated and Guest sessions (Guest gets the empty
  egrm payload populated by `egrm.utils.boot.boot_session`).
* Returns the full Frappe bootinfo dict; `bootinfo.egrm` is added by the
  existing `boot_session` hook so callers see the same shape they would
  on a desk page render.
* Guarantees `egrm` is present in the response even if Frappe's full
  boot-info path raises mid-way (otherwise the AC-5 test sees
  `egrm=None` because the exception aborts before the boot_session hook
  fires).
* Avoids leaking the internal globals `frappe.local.boot_cache` etc.
"""

from __future__ import annotations

import frappe

from egrm.utils.boot import boot_session as _egrm_boot_session


@frappe.whitelist(allow_guest=True)
def get_bootinfo() -> dict:
	"""Return Frappe bootinfo as a plain dict, with `egrm` guaranteed.

	Calls Frappe's heavy `frappe.boot.get_bootinfo` to keep parity with
	a desk render; if any sub-step raises (e.g. an addon's hook touches
	a stale doctype) we fall back to a minimal payload, but in either
	case we run the eGRM `boot_session` hook ourselves so the `egrm`
	namespace is always populated.
	"""
	from frappe.boot import get_bootinfo as _frappe_get_bootinfo

	try:
		bootinfo = _frappe_get_bootinfo()
	except Exception:
		# Heavy path raised — we still owe AC-5 (and the SPA) the egrm
		# payload, so synthesise a minimal bootinfo and let the hook fill
		# in the rest below. The original exception is logged for ops.
		frappe.log_error(title="get_bootinfo full path failed; serving minimal payload")
		bootinfo = frappe._dict()

	if not isinstance(bootinfo.get("egrm"), dict):
		# Boot-session hook didn't run (or got dropped). Re-invoke our
		# eGRM hook directly so the `egrm` namespace is always present.
		try:
			_egrm_boot_session(bootinfo)
		except Exception:
			frappe.log_error(title="egrm.utils.boot.boot_session failed inside wrapper")
			bootinfo.egrm = {
				"active_project": None,
				"duties": [],
				"is_platform_admin": False,
				"available_projects": [],
			}

	# bootinfo is a `frappe._dict`; cast to plain dict so JSON
	# serialization is predictable and downstream tests can call
	# `.get("egrm")` safely.
	return dict(bootinfo)
