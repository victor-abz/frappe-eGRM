"""Public mobile-app metadata endpoint.

Exposes the latest published Android APK so the citizen-facing portal
SPA can render a download page without requiring authentication. Web
templates would otherwise force a separate Jinja surface; this endpoint
keeps the download page inside the React portal alongside /track and
/submit.
"""

from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_latest_app():
    """Return the most recent published Android App Version, if any.

    Lookup order:
    1. The row with ``is_latest = 1`` (operator-curated "latest").
    2. The most recently modified row, as a fallback.

    Returns a dict with ``version_name``, ``download_url`` (absolute URL
    so the SPA can use it as-is for an ``<a download href=...>``),
    ``release_notes`` (HTML), and ``available`` (boolean — false when no
    APK has been uploaded yet, surfaced to the UI for the empty-state).
    """
    fields = ["name", "version_name", "apk_file", "release_notes", "modified"]
    rows = frappe.get_all(
        "Android App Version",
        filters={"is_latest": 1},
        fields=fields,
        limit=1,
    )
    if not rows:
        rows = frappe.get_all(
            "Android App Version",
            fields=fields,
            order_by="modified desc",
            limit=1,
        )

    if not rows or not rows[0].get("apk_file"):
        return {
            "available": False,
            "version_name": None,
            "download_url": None,
            "release_notes": None,
            "message": _("No mobile app version is published yet."),
        }

    row = rows[0]
    return {
        "available": True,
        "version_name": row.get("version_name"),
        "download_url": frappe.utils.get_url(row.get("apk_file")),
        "release_notes": row.get("release_notes") or "",
    }
