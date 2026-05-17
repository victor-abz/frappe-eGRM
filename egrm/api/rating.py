"""
Public Rating API
Allows citizens to rate a resolved/closed complaint by tracking code.

Two paths:
  - Anonymous citizens (no contact channel on the issue): no verification
    code required. They rate by submitting tracking_code + rating + comment.
  - Identified citizens (provided phone or email in contact section): they
    must request a code, receive it via their contact channel, then submit
    with the code.

Rating is only allowed when the issue status is "Resolved" or "Closed", and
only once. Repeat submissions are rejected.
"""

import re
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime


RATING_ALLOWED_STATUSES = {"Resolved", "Closed"}
_OTP_TTL_SECONDS = 300
_OTP_CACHE_PREFIX = "grm_rate_otp:"


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


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
            "status",
            "contact_medium",
            "contact_info_type",
            "contact_information",
            "rating",
            "rating_submitted_at",
        ],
        as_dict=True,
    )


def _status_name(status_link: str) -> str:
    if not status_link:
        return ""
    return frappe.db.get_value("GRM Issue Status", status_link, "status_name") or ""


def _contact_channel(issue) -> tuple[str | None, str | None]:
    """Return (channel_type, contact_value) for an identified citizen, else (None, None).

    channel_type is "phone" or "email" depending on contact_info_type.
    """
    if not issue.contact_information:
        return None, None
    cit = (issue.contact_info_type or "").lower()
    if "phone" in cit:
        return "phone", issue.contact_information
    if "mail" in cit or "email" in cit:
        return "email", issue.contact_information
    return None, None


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="ip", limit=10, seconds=3600)
def request_rating_code(tracking_code: str):
    """Send a 6-digit code to the citizen's contact channel.

    Returns {"status": "success", "channel": "phone"|"email"} on success.
    Returns {"status": "error", ...} otherwise.
    """
    if not tracking_code:
        return {"status": "error", "message": _("Tracking code is required")}

    issue = _issue_from_code(tracking_code)
    if not issue:
        return {"status": "error", "message": _("Complaint not found.")}

    status_name = _status_name(issue.status)
    if status_name not in RATING_ALLOWED_STATUSES:
        return {
            "status": "error",
            "message": _("Rating is only available once the complaint is resolved."),
        }

    if issue.rating_submitted_at:
        return {"status": "error", "message": _("This complaint has already been rated.")}

    channel, value = _contact_channel(issue)
    if not channel:
        return {
            "status": "error",
            "message": _("This complaint has no contact channel; submit your rating without a code."),
        }

    code = f"{secrets.randbelow(1000000):06d}"
    cache_key = f"{_OTP_CACHE_PREFIX}{issue.name}"
    frappe.cache.setex(cache_key, _OTP_TTL_SECONDS, code)

    # Best-effort delivery. The OTP is already stored in cache; transport
    # failures (no SMTP / no SMS gateway configured in the environment) are
    # logged but do not cancel the request, so the user can still receive
    # the code through whichever channel is operational.
    if channel == "phone":
        clean_phone = _normalize_phone(value)
        try:
            from frappe.core.doctype.sms_settings.sms_settings import send_sms

            send_sms(
                receiver_list=[clean_phone],
                msg=_("Your GRM rating code is: {0}. Valid for 5 minutes.").format(code),
                success_msg=False,
            )
        except Exception as e:
            frappe.log_error(title="Rating SMS Error", message=str(e))
    else:
        try:
            frappe.sendmail(
                recipients=[value],
                subject=_("Your GRM rating code"),
                message=_(
                    "Your GRM rating code is: <b>{0}</b>. Valid for 5 minutes."
                ).format(code),
            )
        except Exception as e:
            frappe.log_error(title="Rating Email Error", message=str(e))

    return {"status": "success", "channel": channel}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="ip", limit=30, seconds=3600)
def submit_rating(tracking_code: str, rating, comment: str = "", code: str = ""):
    """Persist the citizen's rating on the issue.

    - Anonymous: code is ignored.
    - Identified: code must match cached OTP.
    """
    if not tracking_code:
        return {"status": "error", "message": _("Tracking code is required")}

    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        return {"status": "error", "message": _("Rating must be a number")}

    if rating_int < 1 or rating_int > 5:
        return {"status": "error", "message": _("Rating must be between 1 and 5")}

    issue = _issue_from_code(tracking_code)
    if not issue:
        return {"status": "error", "message": _("Complaint not found.")}

    status_name = _status_name(issue.status)
    if status_name not in RATING_ALLOWED_STATUSES:
        return {
            "status": "error",
            "message": _("Rating is only available once the complaint is resolved."),
        }

    if issue.rating_submitted_at:
        return {"status": "error", "message": _("This complaint has already been rated.")}

    channel, _value = _contact_channel(issue)
    if channel:
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
        if str(code) != str(stored):
            return {"status": "error", "message": _("Invalid verification code")}
        frappe.cache.delete(cache_key)

    clean_comment = (comment or "").strip()[:500]
    submitted_at = now_datetime()

    doc = frappe.get_doc("GRM Issue", issue.name)
    doc.rating = rating_int
    doc.rating_comment = clean_comment
    doc.rating_submitted_at = submitted_at
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {
        "status": "success",
        "rating": rating_int,
        "rating_submitted_at": submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
