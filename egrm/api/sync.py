"""
EGRM API - WatermelonDB Sync Implementation
------------------------------------------
This module implements the official WatermelonDB sync protocol for synchronizing
data between the mobile app and Frappe backend.

Follows the WatermelonDB sync specification:
- pullChanges: GET endpoint that returns changes since last sync
- pushChanges: POST endpoint that accepts and processes client changes
"""

import json
import logging
import time
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, get_timestamp, now_datetime

# Import user filtering functions from lookup.py
from egrm.api.lookup import get_user_accessible_regions, get_user_region_assignments

# Configure logging
log = logging.getLogger(__name__)

# WatermelonDB sync table mappings
SYNC_TABLES = {
    "grm_issues": "GRM Issue",
    "grm_issue_categories": "GRM Issue Category",
    "grm_issue_types": "GRM Issue Type",
    "grm_issue_statuses": "GRM Issue Status",
    "grm_administrative_regions": "GRM Administrative Region",
    "grm_issue_age_groups": "GRM Issue Age Group",
    "grm_issue_citizen_groups": "GRM Issue Citizen Group",
    "grm_issue_departments": "GRM Issue Department",
    "grm_projects": "GRM Project",
    "users": "User",
    "grm_project_links": "GRM Project Link",
    "grm_issue_logs": "GRM Issue Log",
    "grm_issue_comments": "GRM Issue Comment",
    "grm_issue_attachments": "GRM Issue Attachment",
}

# Reverse mapping for table name lookup
DOCTYPE_TO_TABLE = {v: k for k, v in SYNC_TABLES.items()}


@frappe.whitelist()
def pull_changes(lastPulledAt=None):
    """
    WatermelonDB standard pullChanges endpoint - GET with query parameters

    URL: /api/method/egrm.api.sync.pull_changes?lastPulledAt=<timestamp>
    Method: GET

    Returns:
    {
        "changes": {
            "grm_issues": {
                "created": [raw_record, ...],
                "updated": [raw_record, ...],
                "deleted": ["id1", "id2", ...]
            },
            "grm_issue_categories": {
                "created": [...],
                "updated": [...],
                "deleted": [...]
            }
            // ... other tables
        },
        "timestamp": 1234567890123
    }
    """
    # Start timing the entire operation
    start_time = time.time()
    frappe.log("🔄 [SYNC_BACKEND] Starting pullChanges operation")

    try:
        # Parse timestamp parameter with detailed logging
        param_parse_start = time.time()
        last_pulled_at = (
            frappe.request.args.get("lastPulledAt")
            if frappe.request.args
            else lastPulledAt
        )

        frappe.log(
            f"📥 [SYNC_BACKEND] Received lastPulledAt parameter: {last_pulled_at} (type: {type(last_pulled_at)})"
        )

        # Validate and parse timestamp
        if last_pulled_at:
            try:
                # Handle both string and numeric timestamps
                if isinstance(last_pulled_at, (int, float)):
                    # Convert milliseconds to datetime
                    last_sync_time = datetime.fromtimestamp(last_pulled_at / 1000)
                elif isinstance(last_pulled_at, str):
                    # Handle string timestamps
                    if last_pulled_at.isdigit():
                        # String contains numeric timestamp
                        last_sync_time = datetime.fromtimestamp(
                            int(last_pulled_at) / 1000
                        )
                    else:
                        # ISO string timestamp
                        last_sync_time = get_datetime(last_pulled_at)
                else:
                    raise ValueError(
                        f"Unsupported timestamp format: {type(last_pulled_at)}"
                    )
                frappe.log(
                    f"📅 [SYNC_BACKEND] Parsed timestamp to datetime: {last_sync_time}"
                )
            except Exception as e:
                frappe.log_error(
                    f"❌ [SYNC_BACKEND] Invalid timestamp: {last_pulled_at} - {str(e)}"
                )
                frappe.throw(
                    f"Invalid lastPulledAt timestamp: {last_pulled_at} - {str(e)}"
                )
        else:
            # First sync - get all data from beginning of time
            last_sync_time = datetime.min
            frappe.log("🆕 [SYNC_BACKEND] First sync detected - fetching all data")

        param_parse_duration = time.time() - param_parse_start
        frappe.log(
            f"⏱️ [SYNC_BACKEND] Parameter parsing took: {param_parse_duration:.3f}s"
        )

        # Get all changes since last sync with timing
        changes_start = time.time()
        frappe.log("📊 [SYNC_BACKEND] Starting to fetch changes from database...")
        changes = get_changes_since(last_sync_time)
        changes_duration = time.time() - changes_start
        frappe.log(
            f"⏱️ [SYNC_BACKEND] Database changes fetch took: {changes_duration:.3f}s"
        )

        # Log detailed change statistics
        total_created = total_updated = total_deleted = 0
        for table_name, table_changes in changes.items():
            created = len(table_changes.get("created", []))
            updated = len(table_changes.get("updated", []))
            deleted = len(table_changes.get("deleted", []))
            total_created += created
            total_updated += updated
            total_deleted += deleted
            frappe.log(
                f"📋 [SYNC_BACKEND] {table_name}: +{created} ~{updated} -{deleted}"
            )

        frappe.log(
            f"📊 [SYNC_BACKEND] Total changes: +{total_created} ~{total_updated} -{total_deleted}"
        )

        # Generate timestamp with timing and validation
        timestamp_start = time.time()
        current_dt = now_datetime()
        # WatermelonDB expects timestamp as milliseconds since epoch (number, not string)
        current_timestamp = int(get_timestamp(current_dt) * 1000)

        # Validate timestamp format
        if not isinstance(current_timestamp, int) or current_timestamp <= 0:
            frappe.log_error(
                f"❌ [SYNC_BACKEND] Invalid timestamp generated: {current_timestamp} (type: {type(current_timestamp)})"
            )
            raise ValueError(f"Invalid timestamp generated: {current_timestamp}")

        timestamp_duration = time.time() - timestamp_start
        frappe.log(
            f"🕐 [SYNC_BACKEND] Generated timestamp: {current_timestamp} (type: {type(current_timestamp)})"
        )
        frappe.log(
            f"⏱️ [SYNC_BACKEND] Timestamp generation took: {timestamp_duration:.3f}s"
        )

        # Calculate total operation time
        total_duration = time.time() - start_time
        frappe.log(
            f"✅ [SYNC_BACKEND] pullChanges completed successfully in {total_duration:.3f}s"
        )

        # Log performance breakdown
        frappe.log(f"🔍 [SYNC_BACKEND] Performance breakdown:")
        frappe.log(
            f"  - Parameter parsing: {param_parse_duration:.3f}s ({param_parse_duration/total_duration*100:.1f}%)"
        )
        frappe.log(
            f"  - Database fetch: {changes_duration:.3f}s ({changes_duration/total_duration*100:.1f}%)"
        )
        frappe.log(
            f"  - Timestamp generation: {timestamp_duration:.3f}s ({timestamp_duration/total_duration*100:.1f}%)"
        )

        return {"changes": changes, "timestamp": current_timestamp}

    except Exception as e:
        total_duration = time.time() - start_time
        frappe.log_error(
            f"❌ [SYNC_BACKEND] pullChanges failed after {total_duration:.3f}s: {str(e)}"
        )
        frappe.log_error(f"Pull changes failed: {str(e)}")
        frappe.throw("Sync failed. Please try again.")


@frappe.whitelist()
def push_changes():
    """
    WatermelonDB standard pushChanges endpoint

    Method: POST
    Body: {
        "changes": {...},
        "lastPulledAt": "timestamp"
    }

    Returns: void (204 No Content) on success, HTTP error on failure
    """
    start_time = time.time()
    frappe.log("🔄 [SYNC_BACKEND] Starting pushChanges operation")

    try:
        # Parse request data with timing
        parse_start = time.time()
        data = frappe.request.get_json(silent=True) or {}
        changes = data.get("changes", {})
        last_pulled_at = data.get("lastPulledAt")

        # ------------------------------------------------------------------
        # 🔄  Accept Issue Actions sync: grm_issues (created/updated) and
        #      child tables (grm_issue_logs, grm_issue_comments, grm_issue_attachments created only)
        # ------------------------------------------------------------------
        filtered_changes = {}

        # Handle grm_issues table - accept both created and updated records
        if "grm_issues" in changes:
            issue_created = changes["grm_issues"].get("created", [])
            issue_updated = changes["grm_issues"].get("updated", [])

            if issue_created or issue_updated:
                filtered_changes["grm_issues"] = {
                    "created": issue_created,
                    "updated": issue_updated,
                    "deleted": [],
                }

        # Handle grm_issue_logs table - accept created records only
        if "grm_issue_logs" in changes:
            logs_created = changes["grm_issue_logs"].get("created", [])

            if logs_created:
                filtered_changes["grm_issue_logs"] = {
                    "created": logs_created,
                    "updated": [],
                    "deleted": [],
                }

        # Handle grm_issue_comments table - accept created records only
        if "grm_issue_comments" in changes:
            comments_created = changes["grm_issue_comments"].get("created", [])

            if comments_created:
                filtered_changes["grm_issue_comments"] = {
                    "created": comments_created,
                    "updated": [],
                    "deleted": [],
                }

        # Handle grm_issue_attachments table - accept created records only
        if "grm_issue_attachments" in changes:
            attachments_created = changes["grm_issue_attachments"].get("created", [])

            if attachments_created:
                filtered_changes["grm_issue_attachments"] = {
                    "created": attachments_created,
                    "updated": [],
                    "deleted": [],
                }

        # Replace original changes with filtered subset
        changes = filtered_changes

        if not changes:
            frappe.log(
                "📤 [SYNC_BACKEND] No Issue Actions changes to process – returning 204"
            )
            frappe.response.http_status_code = 204
            return

        parse_duration = time.time() - parse_start
        frappe.log(f"⏱️ [SYNC_BACKEND] Request parsing took: {parse_duration:.3f}s")

        # Log push statistics
        total_created = total_updated = total_deleted = 0
        for table_name, table_changes in changes.items():
            created = len(table_changes.get("created", []))
            updated = len(table_changes.get("updated", []))
            deleted = len(table_changes.get("deleted", []))
            total_created += created
            total_updated += updated
            total_deleted += deleted
            frappe.log(
                f"📋 [SYNC_BACKEND] Push {table_name}: +{created} ~{updated} -{deleted}"
            )

        frappe.log(
            f"📊 [SYNC_BACKEND] Total push changes: +{total_created} ~{total_updated} -{total_deleted}"
        )

        # Process changes in transaction with timing
        transaction_start = time.time()
        try:
            frappe.log("💾 [SYNC_BACKEND] Starting database transaction...")
            frappe.db.begin()

            # Collect file URLs for uploaded attachments
            file_url_mappings = {}

            for table_name, table_changes in changes.items():
                table_start = time.time()
                if table_name == "grm_issue_attachments":
                    # Process attachments and collect file URLs
                    file_urls = process_table_changes(table_name, table_changes)
                    if file_urls:
                        file_url_mappings[table_name] = file_urls
                else:
                    process_table_changes(table_name, table_changes)
                table_duration = time.time() - table_start
                frappe.log(
                    f"⏱️ [SYNC_BACKEND] Processing {table_name} took: {table_duration:.3f}s"
                )

            frappe.db.commit()
            transaction_duration = time.time() - transaction_start
            frappe.log(
                f"✅ [SYNC_BACKEND] Database transaction completed in {transaction_duration:.3f}s"
            )

            # Return file URLs for uploaded attachments
            if file_url_mappings:
                frappe.log(f"📤 [SYNC_BACKEND] Returning file URLs: {file_url_mappings}")
                return {"file_urls": file_url_mappings}
            else:
                # Return void - no response data needed per WatermelonDB spec
                frappe.response.http_status_code = 204

        except Exception as e:
            frappe.db.rollback()
            transaction_duration = time.time() - transaction_start
            frappe.log_error(
                f"❌ [SYNC_BACKEND] Transaction failed after {transaction_duration:.3f}s: {str(e)}"
            )
            frappe.log_error(f"Push changes failed: {str(e)}")
            frappe.throw("Failed to save changes. Please try again.")

        total_duration = time.time() - start_time
        frappe.log(
            f"✅ [SYNC_BACKEND] pushChanges completed successfully in {total_duration:.3f}s"
        )

    except Exception as e:
        total_duration = time.time() - start_time
        frappe.log_error(
            f"❌ [SYNC_BACKEND] pushChanges failed after {total_duration:.3f}s: {str(e)}"
        )
        frappe.log_error(f"Push changes failed: {str(e)}")
        frappe.throw("Failed to process push changes request.")


def get_deleted_records(doctype, since_timestamp):
    """
    Get deleted records from Frappe's deleted documents table

    Returns list of record IDs that were deleted since the given timestamp
    """
    start_time = time.time()
    frappe.log(
        f"🗑️ [SYNC_BACKEND] Fetching deleted records for {doctype} since {since_timestamp}"
    )

    try:
        # Time the actual database query
        query_start = time.time()

        # Query the Deleted Document table for records of this doctype
        # that were deleted after the given timestamp
        deleted_docs = frappe.get_list(
            "Deleted Document",
            filters={"deleted_doctype": doctype, "creation": [">", since_timestamp]},
            fields=["deleted_name as name"],
            ignore_permissions=True,  # We need to see all deleted records
        )

        query_duration = time.time() - query_start
        frappe.log(
            f"🗑️ [SYNC_BACKEND] Deleted records query took: {query_duration:.3f}s"
        )

        # Extract just the document names (IDs)
        extraction_start = time.time()
        deleted_ids = [doc.name for doc in deleted_docs]
        extraction_duration = time.time() - extraction_start

        duration = time.time() - start_time
        frappe.log(
            f"🗑️ [SYNC_BACKEND] Found {len(deleted_ids)} deleted {doctype} records in {duration:.3f}s"
        )
        frappe.log(
            f"🗑️ [SYNC_BACKEND] Breakdown - Query: {query_duration:.3f}s, Extraction: {extraction_duration:.3f}s"
        )

        return deleted_ids

    except Exception as e:
        duration = time.time() - start_time
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Failed to get deleted records for {doctype} after {duration:.3f}s: {str(e)}"
        )
        # Return empty list on error - don't fail the entire sync
        return []


def get_changes_since(last_sync_time):
    """Get all changes since last sync time with user permissions and region filtering"""
    function_start = time.time()
    user = frappe.session.user
    frappe.log(
        f"📊 [SYNC_BACKEND] Fetching changes since: {last_sync_time} for user: {user}"
    )

    # Get user accessible projects and region assignments
    user_accessible_projects = get_user_accessible_projects(user)
    user_assignments = get_user_region_assignments(user)
    assigned_region_ids = list(
        set([assignment.administrative_region for assignment in user_assignments])
    )

    frappe.log(
        f"👤 [SYNC_BACKEND] User {user} has access to projects: {user_accessible_projects}"
    )
    frappe.log(
        f"🗺️ [SYNC_BACKEND] User {user} has assigned regions: {assigned_region_ids}"
    )

    changes = {}
    total_records_processed = 0
    
    # Track issues being synced for child table filtering
    synced_issue_ids = set()

    for table_name, doctype in SYNC_TABLES.items():
        table_start = time.time()
        try:
            frappe.log(f"📋 [SYNC_BACKEND] Processing {doctype} -> {table_name}")

            # Build user-specific filters based on doctype
            user_filters = get_user_filters_for_doctype(
                doctype, user_accessible_projects, assigned_region_ids, user
            )

            # Handle child table filtering separately
            child_table_filter = user_filters.pop("_child_table_filter", None)

            # Combine time filters with user filters
            created_filters = {"creation": [">", last_sync_time]}
            updated_filters = [
                ["modified", ">", last_sync_time],
                ["creation", "<=", last_sync_time],
            ]

            # Add user-specific filters (now properly formatted)
            if user_filters:
                # For created filters (dict format), add properly formatted filters
                for key, value in user_filters.items():
                    if isinstance(value, list) and len(value) > 1:
                        created_filters[key] = ["in", value]
                    elif isinstance(value, list) and len(value) == 1:
                        created_filters[key] = value[0]
                    else:
                        created_filters[key] = value

                # For updated filters (list format), add properly formatted filters
                for key, value in user_filters.items():
                    if isinstance(value, list) and len(value) > 1:
                        updated_filters.append([key, "in", value])
                    elif isinstance(value, list) and len(value) == 1:
                        updated_filters.append([key, "=", value[0]])
                    else:
                        updated_filters.append([key, "=", value])

            # Add child table filters if present
            if child_table_filter:
                child_doctype = child_table_filter["child_doctype"]
                field = child_table_filter["field"]
                values = child_table_filter["values"]

                if len(values) > 1:
                    # Multiple values - use "in" operator
                    child_filter = [child_doctype, field, "in", values]
                else:
                    # Single value - use "=" operator
                    child_filter = [child_doctype, field, "=", values[0]]

                # Convert created_filters to list format and add child filter
                created_filters_list = [["creation", ">", last_sync_time], child_filter]
                # Replace dict format with list format for child table queries
                created_filters = created_filters_list
                updated_filters.append(child_filter)

                frappe.log(
                    f"🔗 [SYNC_BACKEND] Using child table filter for {doctype}: {child_filter}"
                )

            # Get created records with user filtering
            created_start = time.time()
            frappe.log(
                f"📝 [SYNC_BACKEND] Querying created records for {doctype} with user filters..."
            )

            created_records = frappe.get_all(
                doctype,
                filters=created_filters,
                fields=["*"],
            )

            if doctype == "GRM Project Link":
                print(created_records)

            created_duration = time.time() - created_start
            frappe.log(
                f"📝 [SYNC_BACKEND] Found {len(created_records)} created records in {created_duration:.3f}s"
            )

            # Get updated records with user filtering
            updated_start = time.time()
            frappe.log(
                f"✏️ [SYNC_BACKEND] Querying updated records for {doctype} with user filters..."
            )

            updated_records = frappe.get_list(
                doctype,
                filters=updated_filters,
                fields=["*"],
            )

            updated_duration = time.time() - updated_start
            frappe.log(
                f"✏️ [SYNC_BACKEND] Found {len(updated_records)} updated records in {updated_duration:.3f}s"
            )

            # Get deleted records from Frappe's deleted documents table
            deleted_start = time.time()
            frappe.log(f"🗑️ [SYNC_BACKEND] Querying deleted records for {doctype}...")

            deleted_ids = get_deleted_records(doctype, last_sync_time)

            deleted_duration = time.time() - deleted_start
            frappe.log(
                f"🗑️ [SYNC_BACKEND] Found {len(deleted_ids)} deleted records in {deleted_duration:.3f}s"
            )

            # Track issue IDs for child table filtering
            if doctype == "GRM Issue":
                for record in created_records + updated_records:
                    synced_issue_ids.add(record.get("name"))
                frappe.log(f"📎 [SYNC_BACKEND] Tracking {len(synced_issue_ids)} issue IDs for child table filtering")

            # Convert to WatermelonDB format with timing
            convert_start = time.time()
            frappe.log(
                f"🔄 [SYNC_BACKEND] Converting {len(created_records) + len(updated_records)} records to WatermelonDB format..."
            )

            # Time each conversion step
            created_conversion_start = time.time()
            created_raw = remove_duplicates_by_id(
                [frappe_to_watermelon_raw(rec) for rec in created_records]
            )
            created_conversion_duration = time.time() - created_conversion_start

            updated_conversion_start = time.time()
            updated_raw = remove_duplicates_by_id(
                [frappe_to_watermelon_raw(rec) for rec in updated_records]
            )
            updated_conversion_duration = time.time() - updated_conversion_start

            changes[table_name] = {
                "created": created_raw,
                "updated": updated_raw,
                "deleted": deleted_ids,
            }

            convert_duration = time.time() - convert_start
            table_duration = time.time() - table_start

            # Detailed breakdown logging
            frappe.log(f"🔄 [SYNC_BACKEND] Conversion breakdown:")
            frappe.log(
                f"  - Created conversion: {created_conversion_duration:.3f}s ({len(created_records)} records)"
            )
            frappe.log(
                f"  - Updated conversion: {updated_conversion_duration:.3f}s ({len(updated_records)} records)"
            )
            frappe.log(f"  - Total conversion: {convert_duration:.3f}s")

            frappe.log(
                f"✅ [SYNC_BACKEND] {table_name} completed in {table_duration:.3f}s"
            )
            frappe.log(f"📊 [SYNC_BACKEND] {table_name} timing breakdown:")
            frappe.log(
                f"  - Created query: {created_duration:.3f}s ({created_duration/table_duration*100:.1f}%)"
            )
            frappe.log(
                f"  - Updated query: {updated_duration:.3f}s ({updated_duration/table_duration*100:.1f}%)"
            )
            frappe.log(
                f"  - Deleted query: {deleted_duration:.3f}s ({deleted_duration/table_duration*100:.1f}%)"
            )
            frappe.log(
                f"  - Conversion: {convert_duration:.3f}s ({convert_duration/table_duration*100:.1f}%)"
            )

            total_records_processed += (
                len(created_records) + len(updated_records) + len(deleted_ids)
            )

        except Exception as e:
            table_duration = time.time() - table_start
            frappe.log_error(
                f"❌ [SYNC_BACKEND] Error processing {doctype} after {table_duration:.3f}s: {str(e)}"
            )
            frappe.log_error(f"Error getting changes for {doctype}: {str(e)}")
            # Continue with other tables even if one fails
            continue

    # Optimize attachment fetching with proper parent filtering
    if "grm_issue_attachments" in changes and synced_issue_ids:
        frappe.log(f"📎 [SYNC_BACKEND] Optimizing attachment sync for {len(synced_issue_ids)} accessible issues")
        changes["grm_issue_attachments"] = optimize_attachment_sync(
            changes["grm_issue_attachments"], 
            synced_issue_ids, 
            last_sync_time
        )

    function_duration = time.time() - function_start
    frappe.log("✅ [SYNC_BACKEND] All table changes processed successfully")
    frappe.log(
        f"📊 [SYNC_BACKEND] get_changes_since() completed in {function_duration:.3f}s"
    )
    frappe.log(f"📊 [SYNC_BACKEND] Total records processed: {total_records_processed}")
    frappe.log(
        f"📊 [SYNC_BACKEND] Average time per record: {function_duration/max(total_records_processed, 1):.4f}s"
    )

    return changes


def remove_duplicates_by_id(objects):
    seen = set()
    unique_objects = []
    for obj in objects:
        if obj["id"] not in seen:
            seen.add(obj["id"])
            unique_objects.append(obj)
    return unique_objects


def get_user_filters_for_doctype(doctype, user_projects, accessible_region_ids, user):
    """
    Get user-specific filters for a given doctype based on their project assignments

    Args:
        doctype (str): The Frappe doctype to filter
        user_projects (list): List of project IDs the user has access to (not used, will get fresh)
        accessible_region_ids (list): List of region IDs the user has access to (not used, will get fresh)
        user (str): Current user email

    Returns:
        dict: Filters to apply for the doctype. Values are either single values or lists (without operator wrapping)
    """

    # Get fresh user accessible projects (this handles admin check internally)
    user_accessible_projects = get_user_accessible_projects(user)

    # If user has no project access, they get no data
    if not user_accessible_projects:
        log.warning(f"⚠️ [SYNC_BACKEND] User {user} has no project assignments")
        frappe.throw("User has no access to any project")

    filters = {}

    # Define project field mapping for each doctype
    # For child tables, we need to specify the child doctype in filters
    CHILD_TABLE_DOCTYPES = {
        "GRM Issue Category": "GRM Project Link",
        "GRM Issue Type": "GRM Project Link",
        "GRM Issue Status": "GRM Project Link",
        "GRM Issue Age Group": "GRM Project Link",
        "GRM Issue Citizen Group": "GRM Project Link",
        "GRM Issue Department": "GRM Project Link",
    }

    if doctype == "GRM Issue":
        # Special case: Filter issues by both project AND assigned regions
        filters["project"] = (
            user_accessible_projects  # Return just the list, not wrapped
        )

        # Get user's directly assigned regions for issues
        user_assignments = get_user_region_assignments(user)
        assigned_region_ids = list(
            set([assignment.administrative_region for assignment in user_assignments])
        )

        if assigned_region_ids:
            filters["administrative_region"] = (
                assigned_region_ids  # Return just the list
            )

    elif doctype == "GRM Administrative Region":
        # For regions, get user's directly assigned regions (not hierarchy)
        user_assignments = get_user_region_assignments(user)

        # Extract unique region IDs from assignments
        assigned_region_ids = list(
            set([assignment.administrative_region for assignment in user_assignments])
        )

        if assigned_region_ids:
            # Filter regions by both user-assigned regions AND projects
            filters = {
                "name": assigned_region_ids,  # Return just the list
                "project": user_accessible_projects,  # Return just the list
            }
            frappe.log(
                f"🗺️ [SYNC_BACKEND] Filtering regions by assigned regions: {assigned_region_ids} and projects: {user_accessible_projects}"
            )
        else:
            # User has no region assignments, return no regions
            filters["name"] = "NONE"
            frappe.log(f"🗺️ [SYNC_BACKEND] User {user} has no region assignments")

    elif doctype == "GRM Project":
        # Special case - filter by project name itself
        filters["name"] = user_accessible_projects
        frappe.log(
            f"📁 [SYNC_BACKEND] Filtering GRM Project by name in projects: {user_accessible_projects}"
        )

    elif doctype == "User":
        # Only return the current user's data for privacy
        filters["name"] = user
        frappe.log(f"👤 [SYNC_BACKEND] Filtering users to current user: {user}")

    elif doctype in CHILD_TABLE_DOCTYPES:
        # For doctypes with child table project links, use special child table filter
        child_doctype = CHILD_TABLE_DOCTYPES[doctype]
        # We'll handle this in get_changes_since with proper child table syntax
        filters["_child_table_filter"] = {
            "child_doctype": child_doctype,
            "field": "project",
            "values": user_accessible_projects,
        }
        frappe.log(
            f"📁 [SYNC_BACKEND] Filtering {doctype} by child table {child_doctype}.project in projects: {user_accessible_projects}"
        )

    else:
        log.warning(f"⚠️ [SYNC_BACKEND] Unknown doctype for filtering: {doctype}")
        # Default to no filtering for unknown doctypes
        return {}

    return filters


def validate_user_record_access(doctype, record_data, user):
    """
    Validate that a user has permission to access/modify a specific record

    Args:
        doctype (str): The Frappe doctype
        record_data (dict): The record data (for validation)
        user (str): Current user email

    Returns:
        bool: True if user has access, False otherwise
    """

    # Get fresh user accessible projects (this handles admin check internally)
    user_accessible_projects = get_user_accessible_projects(user)

    # Check if user is Administrator or has System Manager role (handled in get_user_accessible_projects)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        frappe.log(
            f"🔓 [SYNC_BACKEND] User {user} has admin access - allowing record operation"
        )
        return True

    # If user has no project access, deny access
    if not user_accessible_projects:
        log.warning(f"❌ [SYNC_BACKEND] User {user} has no project assignments")
        return False

    if doctype == "GRM Issue":
        # Check if issue belongs to user's accessible project
        issue_project = record_data.get("project")

        if issue_project not in user_accessible_projects:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot access project {issue_project}"
            )
            return False

        # Also check region access for issues
        issue_region = record_data.get("administrative_region")
        if issue_region:
            user_assignments = get_user_region_assignments(user)
            assigned_region_ids = list(
                set(
                    [
                        assignment.administrative_region
                        for assignment in user_assignments
                    ]
                )
            )

            # For issues, check if user has access to the region (direct assignment only)
            if issue_region not in assigned_region_ids:
                log.warning(
                    f"❌ [SYNC_BACKEND] User {user} cannot access region {issue_region}"
                )
                return False

    elif doctype == "GRM Administrative Region":
        # Check if region is assigned to user and project is accessible
        region_id = record_data.get("name") or record_data.get("id")
        region_project = record_data.get("project")

        # Check project access first
        if region_project not in user_accessible_projects:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot access project {region_project} for region {region_id}"
            )
            return False

        # Check region assignment
        user_assignments = get_user_region_assignments(user)
        assigned_region_ids = list(
            set([assignment.administrative_region for assignment in user_assignments])
        )

        if region_id not in assigned_region_ids:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} is not assigned to region {region_id}"
            )
            return False

    elif doctype == "GRM Project":
        # Check if project is accessible to user
        project_id = record_data.get("name") or record_data.get("id")
        if project_id not in user_accessible_projects:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot access project {project_id}"
            )
            return False

    elif doctype in [
        "GRM Issue Category",
        "GRM Issue Type",
        "GRM Issue Status",
        "GRM Issue Age Group",
        "GRM Issue Citizen Group",
        "GRM Issue Department",
    ]:
        # For lookup tables, check project access if they have a project field
        record_project = record_data.get("project")
        if record_project and record_project not in user_accessible_projects:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot access project {record_project} for {doctype}"
            )
            return False

    elif doctype == "User":
        # Only allow access to current user's own record
        record_user = record_data.get("name") or record_data.get("id")
        if record_user != user:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot access other user's record {record_user}"
            )
            return False

    elif doctype in ["GRM Issue Log", "GRM Issue Comment"]:
        # For Issue Actions child tables, validate that the user creating the record
        # is the same as the current user (Issue Actions are always performed by the current user)
        record_user = record_data.get("user")
        if record_user and record_user != user:
            log.warning(
                f"❌ [SYNC_BACKEND] User {user} cannot create {doctype} record for other user {record_user}"
            )
            return False

        # Note: Additional validation for parent issue access is handled by the mobile app
        # before sending the sync request, so we trust that the user has access to the related issue
        frappe.log(f"✅ [SYNC_BACKEND] User {user} can create {doctype} record")

    frappe.log(f"✅ [SYNC_BACKEND] User {user} has access to {doctype} record")
    return True


def process_table_changes(table_name, table_changes):
    """Process changes for a specific table with detailed logging"""
    start_time = time.time()
    frappe.log(f"📋 [SYNC_BACKEND] Processing changes for table: {table_name}")

    # Convert table name back to DocType
    doctype = SYNC_TABLES.get(table_name)
    if not doctype:
        frappe.log_error(f"❌ [SYNC_BACKEND] Unknown table name: {table_name}")
        raise ValueError(f"Unknown table name: {table_name}")

    frappe.log(f"📋 [SYNC_BACKEND] Mapped {table_name} -> {doctype}")

    # Track file URLs for attachments
    file_urls = {}

    # Process created records
    created_records = table_changes.get("created", [])
    if created_records:
        created_start = time.time()
        frappe.log(
            f"📝 [SYNC_BACKEND] Processing {len(created_records)} created records..."
        )

        for i, raw_record in enumerate(created_records):
            try:
                record_start = time.time()
                frappe.log(f"✏️ [SYNC_BACKEND] raw_record record {raw_record}")

                # Special handling for attachments to collect file URLs
                if doctype == "GRM Issue Attachment":
                    file_url = create_record(doctype, raw_record, return_file_url=True)
                    if file_url and raw_record.get("id"):
                        file_urls[raw_record["id"]] = file_url
                else:
                    create_record(doctype, raw_record)

                record_duration = time.time() - record_start
                frappe.log(
                    f"📝 [SYNC_BACKEND] Created record {i+1}/{len(created_records)} in {record_duration:.3f}s"
                )
            except Exception as e:
                frappe.log_error(
                    f"❌ [SYNC_BACKEND] Failed to create {doctype} record {i+1}: {str(e)}"
                )
                raise

        created_duration = time.time() - created_start
        frappe.log(
            f"✅ [SYNC_BACKEND] Created {len(created_records)} records in {created_duration:.3f}s"
        )

    # Process updated records
    updated_records = table_changes.get("updated", [])
    if updated_records:
        updated_start = time.time()
        frappe.log(
            f"✏️ [SYNC_BACKEND] Processing {len(updated_records)} updated records..."
        )

        for i, raw_record in enumerate(updated_records):
            try:
                record_start = time.time()
                update_record(doctype, raw_record)
                record_duration = time.time() - record_start
                frappe.log(
                    f"✏️ [SYNC_BACKEND] Updated record {i+1}/{len(updated_records)} in {record_duration:.3f}s"
                )
            except Exception as e:
                frappe.log_error(
                    f"❌ [SYNC_BACKEND] Failed to update {doctype} record {i+1}: {str(e)}"
                )
                raise

        updated_duration = time.time() - updated_start
        frappe.log(
            f"✅ [SYNC_BACKEND] Updated {len(updated_records)} records in {updated_duration:.3f}s"
        )

    # Process deleted records
    deleted_ids = table_changes.get("deleted", [])
    if deleted_ids:
        deleted_start = time.time()
        frappe.log(f"🗑️ [SYNC_BACKEND] Processing {len(deleted_ids)} deleted records...")

        for i, record_id in enumerate(deleted_ids):
            try:
                record_start = time.time()
                delete_record(doctype, record_id)
                record_duration = time.time() - record_start
                frappe.log(
                    f"🗑️ [SYNC_BACKEND] Deleted record {i+1}/{len(deleted_ids)} in {record_duration:.3f}s"
                )
            except Exception as e:
                log.warning(
                    f"⚠️ [SYNC_BACKEND] Failed to delete {doctype} record {record_id}: {str(e)}"
                )
                # Don't raise for delete failures - record might already be deleted

        deleted_duration = time.time() - deleted_start
        frappe.log(
            f"✅ [SYNC_BACKEND] Processed {len(deleted_ids)} deletions in {deleted_duration:.3f}s"
        )

    total_duration = time.time() - start_time
    total_records = len(created_records) + len(updated_records) + len(deleted_ids)
    frappe.log(
        f"✅ [SYNC_BACKEND] Completed {table_name} processing: {total_records} total records in {total_duration:.3f}s"
    )

    # Return file URLs for attachments
    if doctype == "GRM Issue Attachment" and file_urls:
        frappe.log(f"📎 [SYNC_BACKEND] Returning file URLs for {len(file_urls)} attachments")
        return file_urls

    return None


def create_record(doctype, raw_record, return_file_url=False):
    """Create new record from WatermelonDB data with enhanced logging"""
    create_start = time.time()
    record_id = raw_record.get("id")
    user = frappe.session.user
    frappe.log(
        f"📝 [SYNC_BACKEND] Creating {doctype} record with ID: {record_id} by user: {user}"
    )

    if not record_id:
        frappe.log_error(f"❌ [SYNC_BACKEND] Missing ID in raw record for {doctype}")
        raise ValueError("Missing record ID for creation")

    # Validate user has permission to create this record
    validation_start = time.time()
    if not validate_user_record_access(doctype, raw_record, user):
        validation_duration = time.time() - validation_start
        frappe.log_error(
            f"❌ [SYNC_BACKEND] User {user} lacks permission to create {doctype} record {record_id} (validation took {validation_duration:.4f}s)"
        )
        raise frappe.PermissionError(f"Permission denied to create {doctype} record")
    validation_duration = time.time() - validation_start
    frappe.log(
        f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s"
    )

    # Handle child table creation differently
    if doctype in ["GRM Issue Log", "GRM Issue Comment", "GRM Issue Attachment"]:
        return create_child_record(doctype, raw_record, return_file_url=return_file_url)

    # Check if record already exists
    existence_check_start = time.time()
    record_exists = frappe.db.exists(doctype, record_id)
    existence_check_duration = time.time() - existence_check_start
    frappe.log(
        f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s"
    )

    if record_exists:
        log.warning(
            f"⚠️ [SYNC_BACKEND] Record {record_id} already exists, updating instead"
        )
        return update_record(doctype, raw_record)

    # Convert WatermelonDB data to Frappe format
    conversion_start = time.time()
    frappe_data = watermelon_to_frappe_data(raw_record)
    conversion_duration = time.time() - conversion_start
    frappe.log(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

    # Create new document
    doc_creation_start = time.time()
    doc = frappe.new_doc(doctype)
    doc_creation_duration = time.time() - doc_creation_start
    frappe.log(f"Final frappe_data {frappe_data}")
    frappe.log(
        f"📄 [SYNC_BACKEND] Document creation took: {doc_creation_duration:.4f}s"
    )

    # Set the name for sync records - store the desired name in a temporary attribute
    doc._sync_name = record_id

    # Set all fields
    field_setting_start = time.time()
    field_count = 0
    for field, value in frappe_data.items():
        print("Field validation", field, hasattr(doc, field))
        if hasattr(doc, field) and field not in [
            "creation",
            "modified",
            "amended_from",
        ]:
            setattr(doc, field, value)
            field_count += 1
    field_setting_duration = time.time() - field_setting_start
    frappe.log(f"Final fields after conversion {doc.__dict__}")
    frappe.log(
        f"🏗️ [SYNC_BACKEND] Field setting took: {field_setting_duration:.4f}s ({field_count} fields)"
    )

    # Insert the document
    insert_start = time.time()
    doc.insert(ignore_permissions=False)  # Respect permissions
    # Submit the issue
    if doctype == "GRM Issue":
        if doc.docstatus == 0:
            doc.submit()
    insert_duration = time.time() - insert_start
    frappe.log(f"💾 [SYNC_BACKEND] Document insertion took: {insert_duration:.4f}s")

    create_duration = time.time() - create_start
    frappe.log(
        f"✅ [SYNC_BACKEND] Created {doctype} record {record_id} in {create_duration:.4f}s"
    )
    frappe.log(f"📊 [SYNC_BACKEND] Create breakdown:")
    frappe.log(f"  - Permission validation: {validation_duration:.4f}s")
    frappe.log(f"  - Existence check: {existence_check_duration:.4f}s")
    frappe.log(f"  - Data conversion: {conversion_duration:.4f}s")
    frappe.log(f"  - Doc creation: {doc_creation_duration:.4f}s")
    frappe.log(f"  - Field setting: {field_setting_duration:.4f}s")
    frappe.log(f"  - Document insert: {insert_duration:.4f}s")


def create_child_record(doctype, raw_record, return_file_url=False):
    """Create child table record by adding it to parent document"""
    create_start = time.time()
    record_id = raw_record.get("id")
    user = frappe.session.user
    frappe.log(
        f"📝 [SYNC_BACKEND] Creating child table {doctype} record with ID: {record_id} by user: {user}"
    )

    # Get parent issue ID from raw record
    parent_issue_id = raw_record.get("grm_issue")
    if not parent_issue_id:
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Missing parent issue ID in {doctype} record {record_id}"
        )
        raise ValueError(f"Missing parent issue ID for {doctype} child record")

    # Check if parent issue exists
    parent_exists = frappe.db.exists("GRM Issue", parent_issue_id)
    if not parent_exists:
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Parent issue {parent_issue_id} does not exist for {doctype} record {record_id}"
        )
        raise ValueError(f"Parent issue {parent_issue_id} does not exist")

    # Get parent document
    parent_doc = frappe.get_doc("GRM Issue", parent_issue_id)
    frappe.log(f"📋 [SYNC_BACKEND] Retrieved parent issue {parent_issue_id}")

    # Convert WatermelonDB data to Frappe format
    conversion_start = time.time()
    frappe_data = watermelon_to_frappe_data(raw_record)
    conversion_duration = time.time() - conversion_start
    frappe.log(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

    # Special handling for GRM Issue Attachment with file data
    created_file_url = None
    if doctype == "GRM Issue Attachment" and raw_record.get("file_data") and raw_record.get("needs_upload"):
        frappe.log(f"📎 [SYNC_BACKEND] Processing file upload for attachment {record_id}")
        frappe.log(f"📎 [SYNC_BACKEND] File details: name={raw_record.get('file_name')}, has_data={bool(raw_record.get('file_data'))}")

        file_url = create_file_from_base64(raw_record, parent_issue_id)
        if file_url:
            frappe_data["attachment"] = file_url
            created_file_url = file_url
            frappe.log(f"📎 [SYNC_BACKEND] Created file attachment: {file_url}")
        else:
            frappe.log_error(f"❌ [SYNC_BACKEND] Failed to create file for attachment {record_id}")
            frappe.log_error(f"❌ [SYNC_BACKEND] Raw record debug info: {raw_record}")
            # Don't raise error - continue without file, let attachment record be created
            frappe.log(f"⚠️ [SYNC_BACKEND] Continuing without file for attachment {record_id}")
            # Set attachment field to the original attachment value if it exists, or file_name as fallback
            if raw_record.get("attachment"):
                frappe_data["attachment"] = raw_record.get("attachment")
            else:
                frappe_data["attachment"] = raw_record.get("file_name", "unknown_file")

    # Determine the child table field name dynamically using Frappe meta
    child_table_field = get_child_table_field_name("GRM Issue", doctype)
    if not child_table_field:
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Cannot find child table field for {doctype} in GRM Issue"
        )
        raise ValueError(f"Cannot find child table field for {doctype} in GRM Issue")

    frappe.log(f"🔍 [SYNC_BACKEND] Using child table field: {child_table_field}")

    # Create child record as proper Document object
    child_doc = frappe.new_doc(doctype)
    child_doc.name = record_id  # Use WatermelonDB ID
    child_doc.parent = parent_issue_id
    child_doc.parenttype = "GRM Issue"
    child_doc.parentfield = child_table_field

    # Add all fields from frappe_data except the parent reference
    for field, value in frappe_data.items():
        if field not in ["grm_issue", "name", "parent", "parenttype", "parentfield"]:
            if hasattr(child_doc, field):
                setattr(child_doc, field, value)

    frappe.log(f"📝 [SYNC_BACKEND] Child record data: {child_doc.as_dict()}")

    # Add child record to parent document
    if not hasattr(parent_doc, child_table_field):
        # If the child table field doesn't exist, create it as empty list
        setattr(parent_doc, child_table_field, [])

    child_table = getattr(parent_doc, child_table_field, [])

    # Check if child record already exists
    existing_child = None
    for existing_record in child_table:
        if existing_record.get("name") == record_id:
            existing_child = existing_record
            break

    # Add new child record as Document object
    child_table.append(child_doc)
    frappe.log(
        f"📝 [SYNC_BACKEND] Added child record {record_id} to parent {parent_issue_id}"
    )

    # Save parent document
    save_start = time.time()
    try:
        parent_doc.save(ignore_permissions=False)
    except frappe.exceptions.UpdateAfterSubmitError as e:
        # Issue is already submitted, we need to allow updates to child table
        frappe.log(f"⚠️ [SYNC_BACKEND] Issue is submitted, allowing child table updates")
        parent_doc.flags.ignore_validate_update_after_submit = True
        parent_doc.save(ignore_permissions=False)
    save_duration = time.time() - save_start
    frappe.log(f"💾 [SYNC_BACKEND] Parent document save took: {save_duration:.4f}s")

    create_duration = time.time() - create_start
    frappe.log(
        f"✅ [SYNC_BACKEND] Created child table {doctype} record {record_id} in {create_duration:.4f}s"
    )
    frappe.log(f"📊 [SYNC_BACKEND] Child create breakdown:")
    frappe.log(f"  - Data conversion: {conversion_duration:.4f}s")
    frappe.log(f"  - Parent document save: {save_duration:.4f}s")

    # Return file URL if requested and available
    if return_file_url and created_file_url:
        return created_file_url

    return None


def update_record(doctype, raw_record):
    """
    Update existing record using WatermelonDB's _changed property for optimized field updates.
    Uses direct database updates to avoid TimestampMismatchError.
    """
    update_start = time.time()
    record_id = raw_record.get("id")
    user = frappe.session.user
    frappe.log(
        f"✏️ [SYNC_BACKEND] Updating {doctype} record with ID: {record_id} by user: {user}"
    )
    frappe.log(f"✏️ [SYNC_BACKEND] Update raw data {raw_record}")

    if not record_id:
        frappe.log_error(f"❌ [SYNC_BACKEND] Missing ID in raw record for {doctype}")
        raise ValueError("Missing record ID for update")

    # Validate user has permission to update this record
    validation_start = time.time()
    if not validate_user_record_access(doctype, raw_record, user):
        raise frappe.PermissionError(f"Permission denied to update {doctype} record")

    # Verify record exists
    if not frappe.db.exists(doctype, record_id):
        raise ValueError(f"Record {record_id} not found")

    # Parse changed fields from WatermelonDB
    changed_fields_raw = raw_record.get("_changed", "")
    if not changed_fields_raw:
        frappe.log_error(f"No _changed property in record {record_id}")
        return

    changed_fields = [
        field.strip() for field in changed_fields_raw.split(",") if field.strip()
    ]
    if not changed_fields:
        return

    # Convert and filter data
    frappe_data = watermelon_to_frappe_data(raw_record)
    fields_to_update = {
        field: frappe_data[field] for field in changed_fields if field in frappe_data
    }

    if not fields_to_update:
        return

    # Update fields directly in database
    for field_name, field_value in fields_to_update.items():
        if field_name != "updated_at":
            frappe.db.set_value(
                doctype, record_id, field_name, field_value, update_modified=False
            )

    frappe.db.commit()

    update_duration = time.time() - update_start
    frappe.log(
        f"✅ [SYNC_BACKEND] Updated {doctype} record {record_id} "
        f"with {len(fields_to_update)} fields in {update_duration:.4f}s"
    )


def delete_record(doctype, record_id):
    """Delete record (soft delete) with enhanced logging"""
    delete_start = time.time()
    user = frappe.session.user
    frappe.log(
        f"🗑️ [SYNC_BACKEND] Deleting {doctype} record: {record_id} by user: {user}"
    )

    # Check if record exists
    existence_check_start = time.time()
    record_exists = frappe.db.exists(doctype, record_id)
    existence_check_duration = time.time() - existence_check_start
    frappe.log(
        f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s"
    )

    if not record_exists:
        frappe.log(
            f"🗑️ [SYNC_BACKEND] Record {record_id} already deleted or doesn't exist"
        )
        return

    try:
        # Get document for permission validation
        doc_fetch_start = time.time()
        doc = frappe.get_doc(doctype, record_id)
        doc_fetch_duration = time.time() - doc_fetch_start
        frappe.log(f"📄 [SYNC_BACKEND] Document fetch took: {doc_fetch_duration:.4f}s")

        # Validate user has permission to delete this record
        validation_start = time.time()
        record_data = doc.as_dict()
        if not validate_user_record_access(doctype, record_data, user):
            validation_duration = time.time() - validation_start
            frappe.log_error(
                f"❌ [SYNC_BACKEND] User {user} lacks permission to delete {doctype} record {record_id} (validation took {validation_duration:.4f}s)"
            )
            return  # Don't raise exception, just skip this delete
        validation_duration = time.time() - validation_start
        frappe.log(
            f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s"
        )

        # Delete document
        delete_operation_start = time.time()
        doc.delete()
        delete_operation_duration = time.time() - delete_operation_start
        frappe.log(
            f"🗑️ [SYNC_BACKEND] Delete operation took: {delete_operation_duration:.4f}s"
        )

        delete_duration = time.time() - delete_start
        frappe.log(
            f"✅ [SYNC_BACKEND] Deleted {doctype} record {record_id} in {delete_duration:.4f}s"
        )
        frappe.log(f"📊 [SYNC_BACKEND] Delete breakdown:")
        frappe.log(f"  - Existence check: {existence_check_duration:.4f}s")
        frappe.log(f"  - Document fetch: {doc_fetch_duration:.4f}s")
        frappe.log(f"  - Permission validation: {validation_duration:.4f}s")
        frappe.log(f"  - Delete operation: {delete_operation_duration:.4f}s")

    except frappe.PermissionError:
        delete_duration = time.time() - delete_start
        log.warning(
            f"⚠️ [SYNC_BACKEND] No permission to delete {doctype} {record_id} (took {delete_duration:.4f}s)"
        )
        # Don't raise - just log the issue
    except Exception as e:
        delete_duration = time.time() - delete_start
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Failed to delete {doctype} {record_id} after {delete_duration:.4f}s: {str(e)}"
        )
        # Don't raise - continue with other operations


def frappe_to_watermelon_raw(frappe_doc):
    """
    Convert Frappe document to WatermelonDB raw format

    CRITICAL: WatermelonDB raw records MUST NOT contain _status or _changed fields.
    These are internal WatermelonDB fields managed by the mobile app only.

    According to WatermelonDB docs:
    - Records MUST have an 'id' field (mapped from Frappe's 'name' field)
    - Records MUST NOT have '_status' or '_changed' fields
    """
    conversion_start = time.time()

    # Handle both dict and Document objects
    if isinstance(frappe_doc, Document):
        dict_start = time.time()
        doc_dict = frappe_doc.as_dict()
        dict_duration = time.time() - dict_start
        frappe.log(f"🔄 [SYNC_BACKEND] Document.as_dict() took: {dict_duration:.4f}s")
    else:
        doc_dict = frappe_doc

    # CRITICAL: Start with clean record - NO _status or _changed fields
    raw_record = {
        "id": doc_dict.get(
            "name"
        ),  # Map Frappe's 'name' field to WatermelonDB's 'id' field
    }

    # Validate that we have a valid ID
    if not raw_record["id"]:
        frappe.log_error(
            f"❌ [SYNC_BACKEND] Missing 'name' field in Frappe document: {doc_dict}"
        )
        raise ValueError(
            "Frappe document missing 'name' field - cannot create WatermelonDB record"
        )

    # Field processing timing
    field_processing_start = time.time()
    processed_fields = 0
    timestamp_conversions = 0

    # Direct field copy - no transformation needed after schema alignment
    for field_name, value in doc_dict.items():
        # Skip internal fields and the name field (already mapped to id)
        if field_name.startswith("_") or field_name == "name":
            continue

        processed_fields += 1

        # Only convert timestamps - everything else copies directly
        if field_name in ["creation", "modified"] and value:
            # Convert to milliseconds timestamp for WatermelonDB
            timestamp_start = time.time()
            timestamp_ms = int(get_timestamp(value) * 1000)
            timestamp_duration = time.time() - timestamp_start
            timestamp_conversions += 1

            raw_record[field_name] = timestamp_ms
            frappe.log(
                f"🕐 [SYNC_BACKEND] Converted {field_name} timestamp in {timestamp_duration:.4f}s: {value} -> {timestamp_ms}"
            )
        elif (
            field_name
            in [
                "issue_date",
                "intake_date",
                "resolution_date",
                "accepted_date",
                "rejected_date",
                "escalated_date",
                "rated_date",
                "appeal_date",
            ]
            and value
        ):
            # Convert date fields to milliseconds
            timestamp_start = time.time()
            timestamp_ms = int(get_timestamp(value) * 1000)
            timestamp_duration = time.time() - timestamp_start
            timestamp_conversions += 1

            raw_record[field_name] = timestamp_ms
            frappe.log(
                f"📅 [SYNC_BACKEND] Converted {field_name} date in {timestamp_duration:.4f}s: {value} -> {timestamp_ms}"
            )
        else:
            # Direct assignment - fields already aligned
            raw_record[field_name] = value

    # Special field mapping for attachments: map 'parent' to 'grm_issue'
    if doc_dict.get("doctype") == "GRM Issue Attachment" and doc_dict.get("parent"):
        raw_record["grm_issue"] = doc_dict.get("parent")
        frappe.log(f"📎 [SYNC_BACKEND] Mapped parent field to grm_issue: {doc_dict.get('parent')}")
    # Also handle the case where we don't have doctype but can infer it's an attachment
    elif doc_dict.get("parent") and doc_dict.get("parenttype") == "GRM Issue":
        raw_record["grm_issue"] = doc_dict.get("parent")
        frappe.log(f"📎 [SYNC_BACKEND] Mapped parent field to grm_issue: {doc_dict.get('parent')}")

    field_processing_duration = time.time() - field_processing_start

    # Add standard timestamps for WatermelonDB and sync tracking
    timestamps_start = time.time()
    creation_time = doc_dict.get("creation")
    modified_time = doc_dict.get("modified")

    if creation_time:
        created_at_ms = int(get_timestamp(creation_time) * 1000)
        raw_record["created_at"] = created_at_ms
        # Don't duplicate creation field if already processed above
        if "creation" not in raw_record:
            raw_record["creation"] = created_at_ms
        frappe.log(f"🆕 [SYNC_BACKEND] Added created_at: {created_at_ms}")

    if modified_time:
        updated_at_ms = int(get_timestamp(modified_time) * 1000)
        raw_record["updated_at"] = updated_at_ms
        # Don't duplicate modified field if already processed above
        if "modified" not in raw_record:
            raw_record["modified"] = updated_at_ms
        frappe.log(f"✏️ [SYNC_BACKEND] Added updated_at: {updated_at_ms}")

    timestamps_duration = time.time() - timestamps_start

    # Final validation - ensure no WatermelonDB internal fields
    validation_start = time.time()
    prohibited_fields = ["_status", "_changed"]
    removed_fields = []
    for field in prohibited_fields:
        if field in raw_record:
            frappe.log_error(
                f"❌ [SYNC_BACKEND] CRITICAL: Found prohibited field '{field}' in raw record!"
            )
            del raw_record[field]
            removed_fields.append(field)
            log.warning(
                f"⚠️ [SYNC_BACKEND] Removed prohibited field '{field}' from raw record"
            )

    validation_duration = time.time() - validation_start
    conversion_duration = time.time() - conversion_start

    frappe.log(
        f"✅ [SYNC_BACKEND] Record conversion completed in {conversion_duration:.4f}s"
    )
    frappe.log(f"🔍 [SYNC_BACKEND] Conversion breakdown:")
    frappe.log(
        f"  - Field processing: {field_processing_duration:.4f}s ({processed_fields} fields)"
    )
    frappe.log(f"  - Timestamp conversions: {timestamp_conversions} conversions")
    frappe.log(f"  - Standard timestamps: {timestamps_duration:.4f}s")
    frappe.log(f"  - Validation: {validation_duration:.4f}s")
    if removed_fields:
        frappe.log(f"  - Removed prohibited fields: {removed_fields}")

    return raw_record


def watermelon_to_frappe_data(raw_record):
    """Convert WatermelonDB raw record to Frappe data - MINIMAL TRANSFORMATION"""
    conversion_start = time.time()
    frappe.log(f"🔄 [SYNC_BACKEND] Converting WatermelonDB raw record to Frappe data")

    frappe_data = {}
    processed_fields = 0
    timestamp_conversions = 0

    # Direct field copy - no complex transformation needed
    field_processing_start = time.time()

    for key, value in raw_record.items():
        if key.startswith("_"):  # Skip WatermelonDB internal fields
            continue

        processed_fields += 1

        # Only convert timestamp fields back to datetime
        if key in [
            "creation",
            "modified",
            "issue_date",
            "intake_date",
            "resolution_date",
            "accepted_date",
            "rejected_date",
            "escalated_date",
            "rated_date",
            "appeal_date",
            "timestamp",
        ]:
            if value and isinstance(value, (int, float)):
                # Convert from milliseconds to datetime
                timestamp_start = time.time()
                frappe_data[key] = datetime.fromtimestamp(value / 1000)
                timestamp_duration = time.time() - timestamp_start
                timestamp_conversions += 1
                frappe.log(
                    f"🕐 [SYNC_BACKEND] Converted {key} timestamp in {timestamp_duration:.4f}s: {value} -> {frappe_data[key]}"
                )
        else:
            # Direct assignment - fields already aligned
            frappe_data[key] = value

    # Special field mapping for attachments: map 'grm_issue' back to 'parent'
    if raw_record.get("grm_issue"):
        frappe_data["parent"] = raw_record.get("grm_issue")
        frappe.log(f"📎 [SYNC_BACKEND] Mapped grm_issue field to parent: {raw_record.get('grm_issue')}")

    frappe_data["name"] = raw_record["id"]

    field_processing_duration = time.time() - field_processing_start
    conversion_duration = time.time() - conversion_start

    frappe.log(
        f"✅ [SYNC_BACKEND] WatermelonDB-to-Frappe conversion completed in {conversion_duration:.4f}s"
    )
    frappe.log(f"🔍 [SYNC_BACKEND] Conversion breakdown:")
    frappe.log(
        f"  - Field processing: {field_processing_duration:.4f}s ({processed_fields} fields)"
    )
    frappe.log(f"  - Timestamp conversions: {timestamp_conversions} conversions")

    return frappe_data


def get_user_accessible_projects(user):
    """Get projects a user can access based on their active assignments"""
    # Check if user is Administrator or has System Manager role (full access)
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        projects = frappe.get_all(
            "GRM Project", fields=["name"], filters={"is_active": 1}
        )
        return [p.name for p in projects]

    # Get projects assigned to the user (using same logic as lookup.py)
    assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters={"user": user, "is_active": 1, "activation_status": "Activated"},
        fields=["project"],
    )

    # Get unique projects
    user_projects = list(set([a.project for a in assignments]))

    # Filter projects that are still active
    active_projects = []
    for project_id in user_projects:
        if frappe.db.get_value("GRM Project", project_id, "is_active"):
            active_projects.append(project_id)

    return active_projects


# Legacy endpoint compatibility (optional - can be removed later)
@frappe.whitelist()
def get_user_data(project_id=None):
    """
    Legacy compatibility endpoint - delegates to WatermelonDB sync
    This can be removed once all clients are updated to use WatermelonDB sync
    """
    try:
        # Trigger a full sync by calling pullChanges with no timestamp
        result = pull_changes(lastPulledAt=None)

        # Transform the response to match legacy format if needed
        legacy_data = {}
        if result and result.get("changes"):
            for table_name, table_changes in result["changes"].items():
                # Combine created and updated records
                all_records = table_changes.get("created", []) + table_changes.get(
                    "updated", []
                )
                legacy_data[table_name] = all_records

        return {
            "status": "success",
            "data": legacy_data,
            "timestamp": result.get("timestamp"),
        }

    except Exception as e:
        frappe.log_error(f"Legacy get_user_data failed: {str(e)}")
        return {"status": "error", "message": str(e)}


def get_child_table_field_name(parent_doctype, child_doctype):
    """
    Dynamically determine the field name for a child table in the parent DocType

    Args:
        parent_doctype (str): The parent DocType name (e.g., "GRM Issue")
        child_doctype (str): The child DocType name (e.g., "GRM Issue Log")

    Returns:
        str: Field name in parent DocType, or None if not found
    """
    try:
        # Get parent DocType meta
        parent_meta = frappe.get_meta(parent_doctype)

        # Find table fields that link to the child doctype
        for field in parent_meta.fields:
            if field.fieldtype == "Table" and field.options == child_doctype:
                frappe.log(
                    f"🔍 [SYNC_BACKEND] Found child table field: {field.fieldname} for {child_doctype}"
                )
                return field.fieldname

        frappe.log_error(
            f"❌ [SYNC_BACKEND] No table field found for {child_doctype} in {parent_doctype}"
        )
        return None

    except Exception as e:
        frappe.log_error(f"❌ [SYNC_BACKEND] Error finding child table field: {str(e)}")
        return None


def create_file_from_base64(raw_record, parent_issue_id):
    """
    Create a Frappe File record from Base64 data sent by mobile app

    Args:
        raw_record (dict): Raw record containing file data
        parent_issue_id (str): Parent issue ID for file organization

    Returns:
        str: File URL if successful, None if failed
    """
    try:
        file_data = raw_record.get("file_data")
        file_name = raw_record.get("file_name")

        if not file_data or not file_name:
            frappe.log_error(f"❌ [SYNC_BACKEND] Missing file data or filename")
            return None

        frappe.log(f"📎 [SYNC_BACKEND] Creating file from Base64 data: {file_name}")

        # Import necessary modules
        import base64
        import os
        from frappe.utils.file_manager import save_file

        # Validate file name and extension
        frappe.log(f"📎 [SYNC_BACKEND] Validating file name: {file_name}")
        if not validate_file_name(file_name):
            frappe.log_error(f"❌ [SYNC_BACKEND] Invalid file name: {file_name}")
            return None
        frappe.log(f"📎 [SYNC_BACKEND] File name validation passed")

        # Decode Base64 data
        frappe.log(f"📎 [SYNC_BACKEND] Decoding Base64 data (length: {len(file_data)})")
        try:
            file_content = base64.b64decode(file_data)
        except Exception as decode_error:
            frappe.log_error(f"❌ [SYNC_BACKEND] Invalid Base64 data: {str(decode_error)}")
            return None
        frappe.log(f"📎 [SYNC_BACKEND] Base64 decoding successful")

        # Validate file size
        file_size = len(file_content)
        max_size = get_max_file_size()
        frappe.log(f"📎 [SYNC_BACKEND] File size check: {file_size} bytes (max: {max_size} bytes)")
        if file_size > max_size:
            frappe.log_error(f"❌ [SYNC_BACKEND] File too large: {file_size} bytes > {max_size} bytes")
            return None
        frappe.log(f"📎 [SYNC_BACKEND] File size validation passed")

        # Validate file type
        frappe.log(f"📎 [SYNC_BACKEND] Validating file type for: {file_name}")
        if not validate_file_type(file_name, file_content):
            frappe.log_error(f"❌ [SYNC_BACKEND] Invalid file type: {file_name}")
            return None
        frappe.log(f"📎 [SYNC_BACKEND] File type validation passed")

        frappe.log(f"📎 [SYNC_BACKEND] File validation passed: {file_name} ({file_size} bytes)")

        # Create file using Frappe's file manager
        frappe.log(f"📎 [SYNC_BACKEND] Calling save_file with fname={file_name}, dt=GRM Issue, dn={parent_issue_id}")
        try:
            file_doc = save_file(
                fname=file_name,
                content=file_content,
                dt="GRM Issue",
                dn=parent_issue_id,
                folder=None,
                is_private=0  # Public files for issue attachments
            )
            frappe.log(f"📎 [SYNC_BACKEND] save_file returned: {file_doc}")
            frappe.log(f"📎 [SYNC_BACKEND] File doc type: {type(file_doc)}")
            frappe.log(f"📎 [SYNC_BACKEND] File doc attributes: {dir(file_doc) if file_doc else 'None'}")

            if file_doc and hasattr(file_doc, 'file_url'):
                file_url = file_doc.file_url
                frappe.log(f"📎 [SYNC_BACKEND] Successfully created file: {file_url}")
                return file_url
            else:
                frappe.log_error(f"❌ [SYNC_BACKEND] save_file returned invalid result: {file_doc}")
                return None
        except Exception as save_error:
            frappe.log_error(f"❌ [SYNC_BACKEND] save_file failed: {str(save_error)}")
            return None

    except Exception as e:
        frappe.log_error(f"❌ [SYNC_BACKEND] Error creating file from Base64: {str(e)}")
        return None


def validate_file_name(file_name):
    """
    Validate file name for security and compatibility

    Args:
        file_name (str): File name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    import re
    import os

    # Check for empty or None
    if not file_name or not file_name.strip():
        return False

    # Check length
    if len(file_name) > 255:
        return False

    # Check for dangerous characters
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    for char in dangerous_chars:
        if char in file_name:
            frappe.log_error(f"❌ [SYNC_BACKEND] File name contains dangerous character '{char}': {file_name}")
            return False

    # Check for valid extension
    allowed_extensions = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',  # Images
        '.pdf', '.doc', '.docx', '.txt', '.rtf',          # Documents
        '.3gp', '.mp3', '.wav', '.ogg', '.aac', '.flac',          # Audio
        '.mp4', '.avi', '.mov', '.wmv', '.mkv'            # Video
    ]

    file_ext = os.path.splitext(file_name)[1].lower()
    frappe.log(f"📎 [SYNC_BACKEND] File extension: '{file_ext}' (allowed: {allowed_extensions})")
    if file_ext not in allowed_extensions:
        frappe.log_error(f"❌ [SYNC_BACKEND] File extension '{file_ext}' not allowed for file: {file_name}")
        return False

    frappe.log(f"📎 [SYNC_BACKEND] File name validation successful: {file_name}")
    return True


def validate_file_type(file_name, file_content):
    """
    Validate file type based on content (magic bytes)

    Args:
        file_name (str): File name
        file_content (bytes): File content

    Returns:
        bool: True if valid, False otherwise
    """
    import os

    # Get file extension
    file_ext = os.path.splitext(file_name)[1].lower()

    # Check minimum file size
    if len(file_content) < 4:
        return False

    # Magic byte signatures for common file types
    magic_bytes = {
        '.jpg': [b'\xFF\xD8\xFF'],
        '.jpeg': [b'\xFF\xD8\xFF'],
        '.png': [b'\x89PNG\r\n\x1a\n'],
        '.gif': [b'GIF87a', b'GIF89a'],
        '.pdf': [b'%PDF'],
        '.mp3': [b'ID3', b'\xFF\xFB'],
        '.mp4': [b'ftyp'],
        '.3gp': [b'ftyp3g'],  # 3GP files have 'ftyp3g' signature
        '.avi': [b'RIFF'],
        '.wav': [b'RIFF'],
    }

    # Check if file has expected magic bytes
    if file_ext in magic_bytes:
        expected_signatures = magic_bytes[file_ext]
        file_header = file_content[:16]  # Check first 16 bytes

        frappe.log(f"📎 [SYNC_BACKEND] Checking magic bytes for {file_ext}")
        frappe.log(f"📎 [SYNC_BACKEND] File header: {file_header.hex()}")
        frappe.log(f"📎 [SYNC_BACKEND] Expected signatures: {[sig.hex() for sig in expected_signatures]}")

        for signature in expected_signatures:
            if file_header.startswith(signature):
                frappe.log(f"📎 [SYNC_BACKEND] Magic bytes match for {file_ext}")
                return True

        # Check if it's actually a different image type with wrong extension
        all_image_signatures = {
            'PNG': b'\x89PNG\r\n\x1a\n',
            'JPEG': b'\xFF\xD8\xFF',
            'GIF87a': b'GIF87a',
            'GIF89a': b'GIF89a',
        }

        detected_type = None
        for img_type, signature in all_image_signatures.items():
            if file_header.startswith(signature):
                detected_type = img_type
                break

        if detected_type and file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            frappe.log(f"⚠️ [SYNC_BACKEND] File extension mismatch: {file_name} has {file_ext} extension but is actually {detected_type}")
            frappe.log(f"⚠️ [SYNC_BACKEND] Allowing image with mismatched extension")
            return True

        # For audio files, be more lenient with validation
        audio_extensions = ['.3gp', '.mp3', '.wav', '.ogg', '.aac', '.flac']
        if file_ext in audio_extensions:
            frappe.log(f"📎 [SYNC_BACKEND] Audio file with potential signature mismatch, allowing: {file_name}")
            return True
        
        # If no magic bytes match for non-audio files, it's suspicious
        frappe.log_error(f"❌ [SYNC_BACKEND] File type mismatch: {file_name} does not match expected signature")
        return False

    # For file types without magic byte checking, allow them
    frappe.log(f"📎 [SYNC_BACKEND] No magic byte check for {file_ext}, allowing")
    return True


def get_max_file_size():
    """
    Get maximum allowed file size in bytes

    Returns:
        int: Maximum file size in bytes
    """
    # Default to 25MB, can be configured in site config
    default_size = 25 * 1024 * 1024  # 25MB

    try:
        # Check if configured in site settings
        max_size = frappe.conf.get("max_file_size", default_size)
        return int(max_size)
    except:
        return default_size


def optimize_attachment_sync(attachment_changes, accessible_issue_ids, last_sync_time):
    """
    Optimize attachment sync using Frappe QB for better performance
    
    Args:
        attachment_changes (dict): Current attachment changes from regular sync
        accessible_issue_ids (set): Set of issue IDs user has access to
        last_sync_time (datetime): Last sync timestamp
    
    Returns:
        dict: Optimized attachment changes with file data
    """
    start_time = time.time()
    frappe.log(f"📎 [SYNC_BACKEND] Starting optimized attachment sync")
    
    try:
        # Get all accessible issues that user can see (including existing ones)
        all_accessible_issues = get_user_accessible_issues(accessible_issue_ids)
        
        if not all_accessible_issues:
            frappe.log(f"⚠️ [SYNC_BACKEND] No accessible issues found for attachment filtering")
            return {"created": [], "updated": [], "deleted": attachment_changes.get("deleted", [])}
        
        # Use Frappe QB for efficient attachment querying
        attachment_table = frappe.qb.DocType("GRM Issue Attachment")
        
        # Query for created attachments
        created_query = (
            frappe.qb.from_(attachment_table)
            .select("*")
            .where(attachment_table.parent.isin(all_accessible_issues))
            .where(attachment_table.creation > last_sync_time)
        )
        
        # Query for updated attachments  
        updated_query = (
            frappe.qb.from_(attachment_table)
            .select("*")
            .where(attachment_table.parent.isin(all_accessible_issues))
            .where(attachment_table.modified > last_sync_time)
            .where(attachment_table.creation <= last_sync_time)
        )
        
        # Execute queries
        created_attachments = created_query.run(as_dict=True)
        updated_attachments = updated_query.run(as_dict=True)
        
        frappe.log(f"📎 [SYNC_BACKEND] Found {len(created_attachments)} created, {len(updated_attachments)} updated attachments")
        
        # Process created attachments with file data
        processed_created = []
        for attachment in created_attachments:
            raw_record = frappe_to_watermelon_raw(attachment)
            
            # Always add file data for created attachments
            if attachment.get("attachment"):
                file_data = get_attachment_file_data(attachment.get("attachment"))
                if file_data:
                    raw_record["file_data"] = file_data
                    frappe.log(f"📎 [SYNC_BACKEND] Added file data for created attachment: {attachment.get('name')}")
            
            processed_created.append(raw_record)
        
        # Process updated attachments with file data  
        processed_updated = []
        for attachment in updated_attachments:
            raw_record = frappe_to_watermelon_raw(attachment)
            
            # Add file data for updated attachments to ensure mobile app has the file
            if attachment.get("attachment"):
                file_data = get_attachment_file_data(attachment.get("attachment"))
                if file_data:
                    raw_record["file_data"] = file_data
                    frappe.log(f"📎 [SYNC_BACKEND] Added file data for updated attachment: {attachment.get('name')}")
            
            processed_updated.append(raw_record)
        
        duration = time.time() - start_time
        frappe.log(f"📎 [SYNC_BACKEND] Optimized attachment sync completed in {duration:.3f}s")
        
        return {
            "created": processed_created,
            "updated": processed_updated,
            "deleted": attachment_changes.get("deleted", [])
        }
        
    except Exception as e:
        frappe.log_error(f"❌ [SYNC_BACKEND] Error in optimized attachment sync: {str(e)}")
        # Fallback to original data
        return attachment_changes


def get_user_accessible_issues(synced_issue_ids):
    """
    Get all issues that user has access to (both synced and existing)
    
    Args:
        synced_issue_ids (set): Set of issue IDs being synced
    
    Returns:
        list: List of all accessible issue IDs
    """
    try:
        user = frappe.session.user
        
        # Start with synced issues
        all_accessible = set(synced_issue_ids)
        
        # Get user's accessible projects and regions for additional issues
        user_accessible_projects = get_user_accessible_projects(user)
        user_assignments = get_user_region_assignments(user)
        assigned_region_ids = [assignment.administrative_region for assignment in user_assignments]
        
        if user_accessible_projects and assigned_region_ids:
            # Use Frappe QB for efficient querying
            issue_table = frappe.qb.DocType("GRM Issue")
            
            additional_issues_query = (
                frappe.qb.from_(issue_table)
                .select(issue_table.name)
                .where(issue_table.project.isin(user_accessible_projects))
                .where(issue_table.administrative_region.isin(assigned_region_ids))
            )
            
            additional_issues = additional_issues_query.run(as_dict=True)
            all_accessible.update([issue.name for issue in additional_issues])
            
            frappe.log(f"📎 [SYNC_BACKEND] User has access to {len(all_accessible)} total issues")
        
        return list(all_accessible)
        
    except Exception as e:
        frappe.log_error(f"❌ [SYNC_BACKEND] Error getting accessible issues: {str(e)}")
        return list(synced_issue_ids)


def get_attachment_file_data(file_url):
    """
    Get file data as base64 from Frappe file system
    
    Args:
        file_url (str): File URL from Frappe (e.g., '/files/filename.ext')
    
    Returns:
        str: Base64 encoded file data, or None if file not found/error
    """
    if not file_url:
        return None
        
    try:
        import base64
        import os
        
        # Get the file path from Frappe's file system
        if file_url.startswith('/files/'):
            # Remove the '/files/' prefix to get the actual filename
            filename = file_url[7:]  # Remove '/files/' (7 characters)
            
            # Get the full file path using Frappe's file utilities
            file_path = frappe.get_site_path('public', 'files', filename)
            
            frappe.log(f"📎 [SYNC_BACKEND] Reading file from path: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                frappe.log(f"⚠️ [SYNC_BACKEND] File not found: {file_path}")
                return None
                
            # Read file and encode as base64
            with open(file_path, 'rb') as file:
                file_content = file.read()
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                frappe.log(f"📎 [SYNC_BACKEND] Successfully read file: {filename} ({len(file_content)} bytes)")
                return file_base64
                
        else:
            frappe.log(f"⚠️ [SYNC_BACKEND] Unsupported file URL format: {file_url}")
            return None
            
    except Exception as e:
        frappe.log_error(f"❌ [SYNC_BACKEND] Error reading file {file_url}: {str(e)}")
        return None
