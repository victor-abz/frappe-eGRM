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
        # 🔄  Only accept newly-created `grm_issues` records.
        #      Ignore updates / deletes and all other tables.
        # ------------------------------------------------------------------
        filtered_changes = {}

        if "grm_issues" in changes:
            issue_created = changes["grm_issues"].get("created", [])

            if issue_created:
                filtered_changes["grm_issues"] = {
                    "created": issue_created,
                    "updated": [],
                    "deleted": [],
                }

        # Replace original changes with filtered subset
        changes = filtered_changes

        if not changes:
            frappe.log(
                "📤 [SYNC_BACKEND] No new grm_issues (created) to process – returning 204"
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

            for table_name, table_changes in changes.items():
                table_start = time.time()
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
        log.debug(
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

    log.debug(f"✅ [SYNC_BACKEND] User {user} has access to {doctype} record")
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
                create_record(doctype, raw_record)
                record_duration = time.time() - record_start
                log.debug(
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
                log.debug(
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
                log.debug(
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


def create_record(doctype, raw_record):
    """Create new record from WatermelonDB data with enhanced logging"""
    create_start = time.time()
    record_id = raw_record.get("id")
    user = frappe.session.user
    log.debug(
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
    log.debug(
        f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s"
    )

    # Check if record already exists
    existence_check_start = time.time()
    record_exists = frappe.db.exists(doctype, record_id)
    existence_check_duration = time.time() - existence_check_start
    log.debug(
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
    log.debug(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

    # Create new document
    doc_creation_start = time.time()
    doc = frappe.new_doc(doctype)
    doc_creation_duration = time.time() - doc_creation_start
    log.debug(f"📄 [SYNC_BACKEND] Document creation took: {doc_creation_duration:.4f}s")

    # Set the name to WatermelonDB ID for consistency
    doc.name = record_id

    # Set all fields
    field_setting_start = time.time()
    field_count = 0
    for field, value in frappe_data.items():
        if hasattr(doc, field) and field not in ["name", "creation", "modified"]:
            setattr(doc, field, value)
            field_count += 1
    field_setting_duration = time.time() - field_setting_start
    log.debug(
        f"🏗️ [SYNC_BACKEND] Field setting took: {field_setting_duration:.4f}s ({field_count} fields)"
    )

    # Mark as sync operation to bypass some validations if needed
    doc._from_sync = True

    # Insert the document
    insert_start = time.time()
    doc.insert(ignore_permissions=False)  # Respect permissions
    insert_duration = time.time() - insert_start
    log.debug(f"💾 [SYNC_BACKEND] Document insertion took: {insert_duration:.4f}s")

    create_duration = time.time() - create_start
    log.debug(
        f"✅ [SYNC_BACKEND] Created {doctype} record {record_id} in {create_duration:.4f}s"
    )
    log.debug(f"📊 [SYNC_BACKEND] Create breakdown:")
    log.debug(f"  - Permission validation: {validation_duration:.4f}s")
    log.debug(f"  - Existence check: {existence_check_duration:.4f}s")
    log.debug(f"  - Data conversion: {conversion_duration:.4f}s")
    log.debug(f"  - Doc creation: {doc_creation_duration:.4f}s")
    log.debug(f"  - Field setting: {field_setting_duration:.4f}s")
    log.debug(f"  - Document insert: {insert_duration:.4f}s")


def update_record(doctype, raw_record):
    """Update existing record with WatermelonDB data with enhanced logging"""
    update_start = time.time()
    record_id = raw_record.get("id")
    user = frappe.session.user
    log.debug(
        f"✏️ [SYNC_BACKEND] Updating {doctype} record with ID: {record_id} by user: {user}"
    )

    if not record_id:
        frappe.log_error(f"❌ [SYNC_BACKEND] Missing ID in raw record for {doctype}")
        raise ValueError("Missing record ID for update")

    # Validate user has permission to update this record
    validation_start = time.time()
    if not validate_user_record_access(doctype, raw_record, user):
        validation_duration = time.time() - validation_start
        frappe.log_error(
            f"❌ [SYNC_BACKEND] User {user} lacks permission to update {doctype} record {record_id} (validation took {validation_duration:.4f}s)"
        )
        raise frappe.PermissionError(f"Permission denied to update {doctype} record")
    validation_duration = time.time() - validation_start
    log.debug(
        f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s"
    )

    # Check if record exists and user has permission
    existence_check_start = time.time()
    record_exists = frappe.db.exists(doctype, record_id)
    existence_check_duration = time.time() - existence_check_start
    log.debug(
        f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s"
    )

    if not record_exists:
        frappe.log_error(f"❌ [SYNC_BACKEND] Record {record_id} not found for update")
        raise ValueError(f"Record {record_id} not found or no permission")

    # Convert WatermelonDB data to Frappe format
    conversion_start = time.time()
    frappe_data = watermelon_to_frappe_data(raw_record)
    conversion_duration = time.time() - conversion_start
    log.debug(f"🔄 [SYNC_BACKEND] Data conversion took: {conversion_duration:.4f}s")

    # Get existing document
    doc_fetch_start = time.time()
    doc = frappe.get_doc(doctype, record_id)
    doc_fetch_duration = time.time() - doc_fetch_start
    log.debug(f"📄 [SYNC_BACKEND] Document fetch took: {doc_fetch_duration:.4f}s")

    # Update fields
    field_setting_start = time.time()
    field_count = 0
    for field, value in frappe_data.items():
        if hasattr(doc, field) and field not in ["name", "creation"]:
            setattr(doc, field, value)
            field_count += 1
    field_setting_duration = time.time() - field_setting_start
    log.debug(
        f"🏗️ [SYNC_BACKEND] Field setting took: {field_setting_duration:.4f}s ({field_count} fields)"
    )

    # Mark as sync operation
    doc._from_sync = True

    # Save the document
    save_start = time.time()
    doc.save(ignore_permissions=False)
    save_duration = time.time() - save_start
    log.debug(f"💾 [SYNC_BACKEND] Document save took: {save_duration:.4f}s")

    update_duration = time.time() - update_start
    log.debug(
        f"✅ [SYNC_BACKEND] Updated {doctype} record {record_id} in {update_duration:.4f}s"
    )
    log.debug(f"📊 [SYNC_BACKEND] Update breakdown:")
    log.debug(f"  - Permission validation: {validation_duration:.4f}s")
    log.debug(f"  - Existence check: {existence_check_duration:.4f}s")
    log.debug(f"  - Data conversion: {conversion_duration:.4f}s")
    log.debug(f"  - Document fetch: {doc_fetch_duration:.4f}s")
    log.debug(f"  - Field setting: {field_setting_duration:.4f}s")
    log.debug(f"  - Document save: {save_duration:.4f}s")


def delete_record(doctype, record_id):
    """Delete record (soft delete) with enhanced logging"""
    delete_start = time.time()
    user = frappe.session.user
    log.debug(
        f"🗑️ [SYNC_BACKEND] Deleting {doctype} record: {record_id} by user: {user}"
    )

    # Check if record exists
    existence_check_start = time.time()
    record_exists = frappe.db.exists(doctype, record_id)
    existence_check_duration = time.time() - existence_check_start
    log.debug(
        f"🔍 [SYNC_BACKEND] Existence check took: {existence_check_duration:.4f}s"
    )

    if not record_exists:
        log.debug(
            f"🗑️ [SYNC_BACKEND] Record {record_id} already deleted or doesn't exist"
        )
        return

    try:
        # Get document for permission validation
        doc_fetch_start = time.time()
        doc = frappe.get_doc(doctype, record_id)
        doc_fetch_duration = time.time() - doc_fetch_start
        log.debug(f"📄 [SYNC_BACKEND] Document fetch took: {doc_fetch_duration:.4f}s")

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
        log.debug(
            f"🔒 [SYNC_BACKEND] Permission validation took: {validation_duration:.4f}s"
        )

        doc._from_sync = True

        # Delete document
        delete_operation_start = time.time()
        doc.delete()
        delete_operation_duration = time.time() - delete_operation_start
        log.debug(
            f"🗑️ [SYNC_BACKEND] Delete operation took: {delete_operation_duration:.4f}s"
        )

        delete_duration = time.time() - delete_start
        log.debug(
            f"✅ [SYNC_BACKEND] Deleted {doctype} record {record_id} in {delete_duration:.4f}s"
        )
        log.debug(f"📊 [SYNC_BACKEND] Delete breakdown:")
        log.debug(f"  - Existence check: {existence_check_duration:.4f}s")
        log.debug(f"  - Document fetch: {doc_fetch_duration:.4f}s")
        log.debug(f"  - Permission validation: {validation_duration:.4f}s")
        log.debug(f"  - Delete operation: {delete_operation_duration:.4f}s")

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
        log.debug(f"🔄 [SYNC_BACKEND] Document.as_dict() took: {dict_duration:.4f}s")
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
            log.debug(
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
            log.debug(
                f"📅 [SYNC_BACKEND] Converted {field_name} date in {timestamp_duration:.4f}s: {value} -> {timestamp_ms}"
            )
        else:
            # Direct assignment - fields already aligned
            raw_record[field_name] = value

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
        log.debug(f"🆕 [SYNC_BACKEND] Added created_at: {created_at_ms}")

    if modified_time:
        updated_at_ms = int(get_timestamp(modified_time) * 1000)
        raw_record["updated_at"] = updated_at_ms
        # Don't duplicate modified field if already processed above
        if "modified" not in raw_record:
            raw_record["modified"] = updated_at_ms
        log.debug(f"✏️ [SYNC_BACKEND] Added updated_at: {updated_at_ms}")

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

    log.debug(
        f"✅ [SYNC_BACKEND] Record conversion completed in {conversion_duration:.4f}s"
    )
    log.debug(f"🔍 [SYNC_BACKEND] Conversion breakdown:")
    log.debug(
        f"  - Field processing: {field_processing_duration:.4f}s ({processed_fields} fields)"
    )
    log.debug(f"  - Timestamp conversions: {timestamp_conversions} conversions")
    log.debug(f"  - Standard timestamps: {timestamps_duration:.4f}s")
    log.debug(f"  - Validation: {validation_duration:.4f}s")
    if removed_fields:
        log.debug(f"  - Removed prohibited fields: {removed_fields}")

    return raw_record


def watermelon_to_frappe_data(raw_record):
    """Convert WatermelonDB raw record to Frappe data - MINIMAL TRANSFORMATION"""
    conversion_start = time.time()
    log.debug(f"🔄 [SYNC_BACKEND] Converting WatermelonDB raw record to Frappe data")

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
        ]:
            if value and isinstance(value, (int, float)):
                # Convert from milliseconds to datetime
                timestamp_start = time.time()
                frappe_data[key] = datetime.fromtimestamp(value / 1000)
                timestamp_duration = time.time() - timestamp_start
                timestamp_conversions += 1
                log.debug(
                    f"🕐 [SYNC_BACKEND] Converted {key} timestamp in {timestamp_duration:.4f}s: {value} -> {frappe_data[key]}"
                )
        else:
            # Direct assignment - fields already aligned
            frappe_data[key] = value

    field_processing_duration = time.time() - field_processing_start
    conversion_duration = time.time() - conversion_start

    log.debug(
        f"✅ [SYNC_BACKEND] WatermelonDB-to-Frappe conversion completed in {conversion_duration:.4f}s"
    )
    log.debug(f"🔍 [SYNC_BACKEND] Conversion breakdown:")
    log.debug(
        f"  - Field processing: {field_processing_duration:.4f}s ({processed_fields} fields)"
    )
    log.debug(f"  - Timestamp conversions: {timestamp_conversions} conversions")

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
