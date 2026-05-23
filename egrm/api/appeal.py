"""
Public Appeal API
Allows citizens to submit an appeal ("not satisfied") on a resolved/closed
complaint by tracking code.

Verification model (mirrors egrm.api.rating):
  - Anonymous citizens (no contact channel on the issue): no code required.
  - Identified citizens (phone or email on file):
      * If they have already rated the issue, the prior OTP exchange is
        accepted as proof of verification — no fresh code is required.
      * Otherwise they must provide a valid OTP from the shared cache
        (same key used by request_rating_code).

Appeal is only allowed when the issue status is "Resolved" or "Closed",
and only once per issue (appeal_submitted gates repeat submissions).
"""

import hmac

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime


APPEAL_ALLOWED_STATUSES = {"Resolved", "Closed"}
_OTP_CACHE_PREFIX = "grm_rate_otp:"


def _issue_from_code(tracking_code: str):
    issue_name = frappe.db.get_value(
        "GRM Issue", {"tracking_code": tracking_code}, "name"
    )
    if not issue_name:
        return None
    return frappe.db.get_value(
        "GRM Issue",
        issue_name,
        [
            "name",
            "project",
            "status",
            "contact_medium",
            "contact_info_type",
            "contact_information",
            "rating_submitted_at",
            "appeal_submitted",
        ],
        as_dict=True,
    )


def _status_name(status_link: str) -> str:
    if not status_link:
        return ""
    return frappe.db.get_value("GRM Issue Status", status_link, "status_name") or ""


def _has_contact_channel(issue) -> bool:
    if not issue.contact_information:
        return False
    cit = (issue.contact_info_type or "").lower()
    return ("phone" in cit) or ("mail" in cit) or ("email" in cit)


def _get_open_status(project: str) -> str | None:
    rows = frappe.db.sql(
        """
        SELECT s.name
        FROM `tabGRM Issue Status` s
        INNER JOIN `tabGRM Project Link` p ON p.parent = s.name
        WHERE p.project = %s AND s.open_status = 1
        LIMIT 1
        """,
        project,
        as_dict=1,
    )
    return rows[0].name if rows else None


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="ip", limit=20, seconds=3600)
def submit_appeal(tracking_code: str, comment: str, code: str = ""):
    """Submit a citizen appeal on a resolved/closed complaint.

    Returns {"status": "success", "appeal_date": "..."} on success.
    """
    if not tracking_code:
        return {"status": "error", "message": _("Tracking code is required")}

    clean_comment = (comment or "").strip()
    if not clean_comment:
        return {"status": "error", "message": _("Appeal reason is required")}
    clean_comment = clean_comment[:1000]

    issue = _issue_from_code(tracking_code)
    if not issue:
        return {"status": "error", "message": _("Complaint not found.")}

    status_name = _status_name(issue.status)
    if status_name not in APPEAL_ALLOWED_STATUSES:
        return {
            "status": "error",
            "message": _("Appeal is only available once the complaint is resolved."),
        }

    if issue.appeal_submitted:
        return {
            "status": "error",
            "message": _("An appeal has already been submitted for this complaint."),
        }

    identified = _has_contact_channel(issue)
    already_rated = bool(issue.rating_submitted_at)

    if identified and not already_rated:
        if not code:
            return {"status": "error", "message": _("Verification code is required")}
        cache_key = f"{_OTP_CACHE_PREFIX}{issue.name}"
        stored = frappe.cache.get(cache_key)
        if not stored:
            return {
                "status": "error",
                "message": _("Verification code expired. Please request a new one."),
            }
        if isinstance(stored, bytes):
            stored = stored.decode()
        # Review fix B3: hmac.compare_digest() for constant-time OTP
        # comparison (defeats timing-side-channel inference of the OTP).
        if not hmac.compare_digest(str(code), str(stored)):
            return {"status": "error", "message": _("Invalid verification code")}
        frappe.cache.delete(cache_key)

    open_status = _get_open_status(issue.project)
    if not open_status:
        return {
            "status": "error",
            "message": _("No open status configured for this project"),
        }

    submitted_at = now_datetime()

    doc = frappe.get_doc("GRM Issue", issue.name)
    doc.appeal_submitted = 1
    doc.appeal_date = submitted_at
    doc.appeal_reason = clean_comment
    doc.status = open_status
    doc.append(
        "grm_issue_comment",
        {
            "user": "Administrator",
            "comment": _("Citizen appeal: {0}").format(clean_comment),
        },
    )
    doc.append(
        "grm_issue_log",
        {
            "text": _("Appeal submitted by citizen via public portal"),
            "user": "Administrator",
            "timestamp": submitted_at,
        },
    )
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {
        "status": "success",
        "appeal_date": submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
