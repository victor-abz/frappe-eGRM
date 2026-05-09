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
* Avoids leaking the internal globals `frappe.local.boot_cache` etc.
"""
from __future__ import annotations

import frappe
from frappe.boot import get_bootinfo as _frappe_get_bootinfo


@frappe.whitelist(allow_guest=True)
def get_bootinfo() -> dict:
    """Return Frappe bootinfo as a plain dict.

    The original `frappe.boot.get_bootinfo` mutates a Bunch-like object
    via the `boot_session` hook chain (which is where our
    `egrm.utils.boot.boot_session` injects `bootinfo.egrm`). We just call
    it through and return the resulting object.
    """
    bootinfo = _frappe_get_bootinfo()
    # bootinfo is a `frappe._dict`; cast to plain dict so JSON
    # serialization is predictable and downstream tests can call
    # `.get("egrm")` safely.
    return dict(bootinfo)
