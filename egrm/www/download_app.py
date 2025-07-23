import frappe
from frappe import _

def get_context(context):
    """
    Fetches the latest Android app download link and adds it to the context
    for rendering on the web page.
    """
    # Initialize context variables
    context.download_url = None
    context.version_name = None
    context.error_message = None
    context.release_notes = None

    try:
        frappe.log("Attempting to fetch latest Android app version")

        # Log the current request details
        frappe.log({
            "event": "download_app_request",
            "request_path": frappe.request.path,
            "user": frappe.session.user
        })

        # Query the 'Android App Version' DocType for latest version
        # Get all relevant fields in one query
        try:
            # First check if we have any records at all
            total_records = frappe.db.count("Android App Version")
            frappe.log({
                "event": "checking_total_records",
                "count": total_records
            })

            if total_records == 0:
                frappe.log("No Android App Version records found in database")
                context.error_message = _("No app versions have been uploaded yet. Please contact support.")
                return

            # Try to find version marked as latest
            filters = {"is_latest": 1}
            fields = ["version_name", "apk_file"]  # Only fetch essential fields that exist
        except Exception as db_error:
            frappe.log({
                "event": "database_error",
                "error": str(db_error),
                "traceback": frappe.get_traceback()
            })
            raise

        frappe.log({
            "event": "fetching_app_version",
            "filters": filters,
            "fields": fields
        })

        latest_version = frappe.get_all(
            "Android App Version",
            filters=filters,
            fields=fields,
            limit=1
        )

        frappe.log({
            "event": "query_result",
            "found_versions": len(latest_version) if latest_version else 0,
            "latest_version": latest_version
        })

        if latest_version and len(latest_version) > 0:
            version = latest_version[0]
            frappe.log({
                "event": "processing_version",
                "version_name": version.get("version_name"),
                "has_apk": bool(version.get("apk_file")),
                "apk_file_value": version.get("apk_file"),
                "all_fields": version
            })

            if version.get("apk_file"):
                # Generate the file URL using Frappe's get_url function
                file_url = frappe.utils.get_url(version.get("apk_file"))
                frappe.log({
                    "event": "generated_download_url",
                    "file_url": file_url
                })

                context.download_url = file_url
                context.version_name = version.get("version_name")
                # Don't set release notes since the column doesn't exist yet
                context.release_notes = None

                frappe.log({
                    "event": "context_set",
                    "download_url": context.download_url,
                    "version_name": context.version_name,
                    "has_release_notes": bool(context.release_notes)
                })
            else:
                frappe.log("No APK file found for the latest version")
                context.error_message = _("The APK file for the latest version is not available. Please contact support.")
        else:
            frappe.log("No version marked as latest, trying to get most recent version")

            # If no version is marked as latest, try to get the most recent version
            latest_version = frappe.get_all(
                "Android App Version",
                fields=fields,
                limit=1
            )

            frappe.log({
                "event": "fallback_query_result",
                "found_versions": len(latest_version) if latest_version else 0,
                "latest_version": latest_version
            })

            if latest_version and len(latest_version) > 0:
                version = latest_version[0]
                frappe.log({
                    "event": "processing_fallback_version",
                    "version_name": version.get("version_name"),
                    "has_apk": bool(version.get("apk_file")),
                    "apk_file_value": version.get("apk_file"),
                    "all_fields": version
                })

                if version.get("apk_file"):
                    file_url = frappe.utils.get_url(version.get("apk_file"))
                    frappe.log({
                        "event": "generated_fallback_download_url",
                        "file_url": file_url
                    })

                    context.download_url = file_url
                    context.version_name = version.get("version_name")
                    # Don't set release notes since the column doesn't exist yet
                    context.release_notes = None
                else:
                    frappe.log("No APK file found for the most recent version")
                    context.error_message = _("The APK file for the latest version is not available. Please contact support.")
            else:
                frappe.log("No versions found at all")
                context.error_message = _("No app versions are available for download. Please contact support.")

    except Exception as e:
        # Log the full exception details
        frappe.log({
            "event": "error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": frappe.get_traceback()
        })
        frappe.log_error("Error in download_app.get_context", str(e))
        context.error_message = _("An error occurred while fetching the app. Please try again later.")
