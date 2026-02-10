"""
Public Grievance Submission API
-------------------------------
Guest-safe endpoints for submitting grievances through the public portal.
Supports Cloudflare Turnstile verification and SMS OTP.
"""

import re
import secrets

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit


@frappe.whitelist(allow_guest=True)
def get_submission_config():
    """Return portal configuration so the frontend knows what verification is available."""
    try:
        sms_gateway = frappe.db.get_single_value("SMS Settings", "sms_gateway_url")
        otp_enabled = bool(sms_gateway)
        turnstile_site_key = frappe.conf.get("turnstile_site_key") or None

        return {
            "status": "success",
            "data": {
                "otp_enabled": otp_enabled,
                "turnstile_site_key": turnstile_site_key,
            },
        }
    except Exception as e:
        frappe.log_error(title="Submission Config Error", message=str(e))
        return {"status": "error", "message": _("Failed to load submission config")}


@frappe.whitelist(allow_guest=True)
def get_submission_options(project=None):
    """Return form lookup data. If project is given, returns filtered categories/types."""
    try:
        projects = frappe.db.sql(
            """
            SELECT name, title, project_code
            FROM `tabGRM Project`
            WHERE is_active = 1
            ORDER BY title
            """,
            as_dict=True,
        )

        categories = []
        issue_types = []
        admin_levels = []

        if project:
            # Validate project is active
            if not frappe.db.get_value("GRM Project", project, "is_active"):
                return {"status": "error", "message": _("Invalid or inactive project")}

            categories = frappe.db.sql(
                """
                SELECT ic.name, ic.category_name
                FROM `tabGRM Issue Category` ic
                INNER JOIN `tabGRM Project Link` pl
                    ON pl.parent = ic.name
                    AND pl.parenttype = 'GRM Issue Category'
                    AND pl.project = %s
                ORDER BY ic.category_name
                """,
                project,
                as_dict=True,
            )

            issue_types = frappe.db.sql(
                """
                SELECT it.name, it.type_name AS issue_type_name
                FROM `tabGRM Issue Type` it
                INNER JOIN `tabGRM Project Link` pl
                    ON pl.parent = it.name
                    AND pl.parenttype = 'GRM Issue Type'
                    AND pl.project = %s
                ORDER BY it.type_name
                """,
                project,
                as_dict=True,
            )

            admin_levels = frappe.db.sql(
                """
                SELECT name, level_name, level_order
                FROM `tabGRM Administrative Level Type`
                WHERE project = %s
                ORDER BY level_order
                """,
                project,
                as_dict=True,
            )

        return {
            "status": "success",
            "data": {
                "projects": projects,
                "categories": categories,
                "issue_types": issue_types,
                "admin_levels": admin_levels,
            },
        }
    except Exception as e:
        frappe.log_error(title="Submission Options Error", message=str(e))
        return {"status": "error", "message": _("Failed to load submission options")}


@frappe.whitelist(allow_guest=True)
def get_region_children(project, parent_region=None):
    """Return child regions for cascading region selection."""
    try:
        if not project:
            return {"status": "error", "message": _("Project is required")}

        if parent_region:
            regions = frappe.db.sql(
                """
                SELECT name, region_name, administrative_level
                FROM `tabGRM Administrative Region`
                WHERE project = %s AND parent_region = %s
                ORDER BY region_name
                """,
                (project, parent_region),
                as_dict=True,
            )
        else:
            # Get root-level regions (those with no parent or whose level_order = 0)
            root_level = frappe.db.get_value(
                "GRM Administrative Level Type",
                {"project": project, "level_order": 0},
                "name",
            )
            if root_level:
                # If there's only one root region, skip to its children
                root_regions = frappe.db.sql(
                    """
                    SELECT name, region_name, administrative_level
                    FROM `tabGRM Administrative Region`
                    WHERE project = %s AND administrative_level = %s
                    ORDER BY region_name
                    """,
                    (project, root_level),
                    as_dict=True,
                )
                if len(root_regions) == 1:
                    # Skip the single root, return its children directly
                    return get_region_children(project, root_regions[0]["name"])
                regions = root_regions
            else:
                # Fallback: regions with no parent
                regions = frappe.db.sql(
                    """
                    SELECT name, region_name, administrative_level
                    FROM `tabGRM Administrative Region`
                    WHERE project = %s AND (parent_region IS NULL OR parent_region = '')
                    ORDER BY region_name
                    """,
                    project,
                    as_dict=True,
                )

        return {"status": "success", "data": regions}
    except Exception as e:
        frappe.log_error(title="Region Children Error", message=str(e))
        return {"status": "error", "message": _("Failed to load regions")}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="ip", limit=3, seconds=3600)
def send_otp(phone):
    """Send a 6-digit OTP via SMS. Rate limited to 3 per IP per hour."""
    if not phone:
        return {"status": "error", "message": _("Phone number is required")}

    # Basic phone validation
    clean_phone = re.sub(r"[^\d+]", "", phone)
    if len(clean_phone) < 8:
        return {"status": "error", "message": _("Invalid phone number")}

    # Check SMS is configured
    sms_gateway = frappe.db.get_single_value("SMS Settings", "sms_gateway_url")
    if not sms_gateway:
        return {"status": "error", "message": _("SMS service is not configured")}

    # Generate 6-digit OTP
    otp = f"{secrets.randbelow(1000000):06d}"

    # Store in cache with 5-minute TTL
    cache_key = f"grm_otp:{clean_phone}"
    frappe.cache.setex(cache_key, 300, otp)

    # Send SMS
    try:
        from frappe.core.doctype.sms_settings.sms_settings import send_sms

        send_sms(
            receiver_list=[clean_phone],
            msg=_("Your GRM verification code is: {0}. Valid for 5 minutes.").format(otp),
            success_msg=False,
        )
    except Exception as e:
        frappe.log_error(title="OTP SMS Error", message=str(e))
        return {"status": "error", "message": _("Failed to send verification code")}

    return {"status": "success"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="ip", limit=5, seconds=86400)
def submit_grievance(**kwargs):
    """
    Create a GRM Issue on behalf of a citizen.

    Required: project, category, issue_type, administrative_region, issue_date, description
    Optional: contact_medium, phone, otp_code, turnstile_token,
              contact_info_type, contact_information, citizen_name, gender
    """
    try:
        # Extract params
        project = kwargs.get("project")
        category = kwargs.get("category")
        issue_type = kwargs.get("issue_type")
        administrative_region = kwargs.get("administrative_region")
        issue_date = kwargs.get("issue_date")
        description = kwargs.get("description")
        contact_medium = kwargs.get("contact_medium", "anonymous")
        phone = kwargs.get("phone")
        otp_code = kwargs.get("otp_code")
        turnstile_token = kwargs.get("turnstile_token")
        contact_info_type = kwargs.get("contact_info_type")
        contact_information = kwargs.get("contact_information")
        citizen_name = kwargs.get("citizen_name")
        gender = kwargs.get("gender")

        # --- Verify Turnstile ---
        turnstile_secret = frappe.conf.get("turnstile_secret_key")
        if turnstile_secret:
            if not turnstile_token:
                return {"status": "error", "message": _("Bot verification failed")}

            resp = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": turnstile_secret, "response": turnstile_token},
                timeout=10,
            )
            result = resp.json()
            if not result.get("success"):
                return {"status": "error", "message": _("Bot verification failed")}

        # --- Verify OTP ---
        sms_gateway = frappe.db.get_single_value("SMS Settings", "sms_gateway_url")
        otp_enabled = bool(sms_gateway)
        if otp_enabled and phone:
            clean_phone = re.sub(r"[^\d+]", "", phone)
            cache_key = f"grm_otp:{clean_phone}"
            stored_otp = frappe.cache.get(cache_key)
            if not stored_otp:
                return {"status": "error", "message": _("Verification code expired. Please request a new one.")}
            # Handle bytes from Redis
            if isinstance(stored_otp, bytes):
                stored_otp = stored_otp.decode()
            if str(otp_code) != str(stored_otp):
                return {"status": "error", "message": _("Invalid verification code")}
            # Consume the OTP
            frappe.cache.delete(cache_key)

        # --- Validate required fields ---
        required = {
            "project": project,
            "category": category,
            "issue_type": issue_type,
            "administrative_region": administrative_region,
            "description": description,
        }
        for field_name, value in required.items():
            if not value:
                return {
                    "status": "error",
                    "message": _("{0} is required").format(field_name.replace("_", " ").title()),
                }

        # --- Validate project is active ---
        if not frappe.db.get_value("GRM Project", project, "is_active"):
            return {"status": "error", "message": _("Selected project is not active")}

        # --- Validate entities belong to project ---
        if not frappe.db.exists("GRM Project Link", {"parent": category, "parenttype": "GRM Issue Category", "project": project}):
            return {"status": "error", "message": _("Selected category does not belong to this project")}

        if not frappe.db.exists("GRM Project Link", {"parent": issue_type, "parenttype": "GRM Issue Type", "project": project}):
            return {"status": "error", "message": _("Selected issue type does not belong to this project")}

        region_project = frappe.db.get_value("GRM Administrative Region", administrative_region, "project")
        if region_project != project:
            return {"status": "error", "message": _("Selected region does not belong to this project")}

        # --- Sanitize description ---
        # Strip HTML tags
        clean_desc = re.sub(r"<[^>]+>", "", description)
        clean_desc = clean_desc.strip()
        if len(clean_desc) < 10:
            return {"status": "error", "message": _("Description must be at least 10 characters")}
        if len(clean_desc) > 5000:
            clean_desc = clean_desc[:5000]

        # --- Find initial status ---
        initial_status = None
        initial_statuses = frappe.get_all(
            "GRM Issue Status", filters={"initial_status": 1}, fields=["name"]
        )
        for status in initial_statuses:
            if frappe.db.exists("GRM Project Link", {"parent": status.name, "project": project}):
                initial_status = status.name
                break

        if not initial_status:
            return {"status": "error", "message": _("System configuration error. Please try again later.")}

        # --- Determine reporter ---
        # Use a system user for public submissions
        reporter = _get_public_reporter(project)

        # --- Build contact fields ---
        doc_contact_medium = "anonymous"
        doc_contact_info_type = ""
        doc_contact_information = ""
        doc_citizen = ""
        doc_gender = ""

        if contact_medium == "updates" and phone:
            doc_contact_medium = "channel-alert"
            doc_contact_info_type = contact_info_type or "phone_number"
            doc_contact_information = contact_information or phone
            doc_citizen = citizen_name or ""
            doc_gender = gender or ""

        # --- Validate issue_date ---
        today = frappe.utils.today()
        if issue_date:
            if str(issue_date) > today:
                return {"status": "error", "message": _("Issue date cannot be in the future")}
        else:
            issue_date = today

        # --- Create the issue ---
        # Use ignore_permissions instead of set_user to avoid corrupting session cookies
        doc = frappe.get_doc(
            {
                "doctype": "GRM Issue",
                "project": project,
                "category": category,
                "issue_type": issue_type,
                "administrative_region": administrative_region,
                "description": clean_desc,
                "status": initial_status,
                "reporter": reporter,
                "contact_medium": doc_contact_medium,
                "contact_info_type": doc_contact_info_type,
                "contact_information": doc_contact_information,
                "citizen": doc_citizen,
                "gender": doc_gender,
                "citizen_type": "Visible" if doc_citizen else "Confidential",
                "owner": reporter,
                "issue_date": issue_date,
                "intake_date": today,
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        doc.submit()

        return {
            "status": "success",
            "tracking_code": doc.tracking_code,
        }

    except Exception as e:
        frappe.log_error(title="Public Submission Error", message=frappe.get_traceback())
        return {"status": "error", "message": _("An error occurred. Please try again.")}


def _get_public_reporter(project):
    """Find a suitable reporter user for public submissions.

    Returns the first active GRM user assigned to the project,
    or Administrator as fallback.
    """
    assignment = frappe.db.get_value(
        "GRM User Project Assignment",
        {"project": project, "is_active": 1},
        "user",
        order_by="creation ASC",
    )
    return assignment or "Administrator"
