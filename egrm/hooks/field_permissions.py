"""
EGRM Field Permission Hooks
-------------------------
This module contains hooks for field-level permissions.
"""

import logging

import frappe
from frappe import _

# Configure logging
log = logging.getLogger(__name__)

# Role-to-Field Permission Mapping
ROLE_FIELD_PERMISSIONS = {
    "GRM Field Officer": {
        "GRM Issue": {
            "read": [
                "name",
                "title",
                "tracking_code",
                "status",
                "project",
                "category",
                "issue_type",
                "description",
                "assignee",
                "administrative_region",
                "intake_date",
                "issue_date",
                "created_date",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "resolution_days",
                "resolution_date",
                "resolution_accepted",
                "rating",
                "escalate_flag",
                "confirmed",
            ],
            "write": [
                "title",
                "description",
                "category",
                "issue_type",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
            ],
            "hide": ["contact_information"],  # Sensitive data
        }
    },
    "GRM Department Head": {
        "GRM Issue": {
            "read": [
                "name",
                "title",
                "tracking_code",
                "status",
                "project",
                "category",
                "issue_type",
                "description",
                "assignee",
                "administrative_region",
                "intake_date",
                "issue_date",
                "created_date",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "contact_information",
                "resolution_days",
                "resolution_date",
                "resolution_accepted",
                "rating",
                "escalate_flag",
                "confirmed",
            ],
            "write": [
                "title",
                "description",
                "category",
                "issue_type",
                "assignee",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "status",
                "escalate_flag",
            ],
            "hide": [],
        }
    },
    "GRM Project Manager": {
        "GRM Issue": {
            "read": [
                "name",
                "title",
                "tracking_code",
                "status",
                "project",
                "category",
                "issue_type",
                "description",
                "assignee",
                "administrative_region",
                "intake_date",
                "issue_date",
                "created_date",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "contact_information",
                "resolution_days",
                "resolution_date",
                "resolution_accepted",
                "rating",
                "escalate_flag",
                "confirmed",
            ],
            "write": [
                "title",
                "description",
                "category",
                "issue_type",
                "assignee",
                "administrative_region",
                "citizen",
                "citizen_type",
                "gender",
                "contact_medium",
                "citizen_age_group",
                "citizen_group_1",
                "citizen_group_2",
                "status",
                "escalate_flag",
                "confirmed",
            ],
            "hide": [],
        }
    }
}


def get_doc_perms(doc):
    """
    Get field permissions for a document based on user role

    Args:
        doc (Document): Document to check permissions for

    Returns:
        dict: Field permissions
    """
    try:
        user = frappe.session.user

        # System manager and administrator have full access
        if user == "Administrator" or "System Manager" in frappe.get_roles(user):
            return {"read": None, "write": None, "hide": []}  # All fields  # All fields

        # Initialize permissions
        read_fields = []
        write_fields = []
        hide_fields = []

        # Get user roles
        roles = frappe.get_roles(user)

        # Check role-specific permissions
        for role in roles:
            if role in ROLE_FIELD_PERMISSIONS:
                role_perms = ROLE_FIELD_PERMISSIONS[role]

                if doc.doctype in role_perms:
                    doctype_perms = role_perms[doc.doctype]

                    # Add read fields
                    if "read" in doctype_perms:
                        read_fields.extend(doctype_perms["read"])

                    # Add write fields
                    if "write" in doctype_perms:
                        write_fields.extend(doctype_perms["write"])

                    # Add hide fields
                    if "hide" in doctype_perms:
                        hide_fields.extend(doctype_perms["hide"])

        # Remove duplicates
        read_fields = list(set(read_fields))
        write_fields = list(set(write_fields))
        hide_fields = list(set(hide_fields))

        return {
            "read": read_fields if read_fields else None,
            "write": write_fields if write_fields else None,
            "hide": hide_fields,
        }

    except Exception as e:
        frappe.log_error(f"Error in get_doc_perms: {str(e)}")
        return {"read": None, "write": None, "hide": []}


def apply_field_permissions(doc, event=None):
    """
    Apply field-level permissions when a document is loaded

    Args:
        doc (Document): Document being loaded
        event (str, optional): Event name

    Returns:
        None
    """
    try:
        # Skip for system user
        if frappe.session.user == "Administrator":
            return

        # Get permissions
        perms = get_doc_perms(doc)

        # Apply hide permissions
        for field in perms["hide"]:
            if hasattr(doc, field):
                doc.set(field, None)

    except Exception as e:
        frappe.log_error(f"Error in apply_field_permissions: {str(e)}")


def validate_field_permissions(doc, event=None):
    """
    Validate field-level permissions when a document is saved

    Args:
        doc (Document): Document being saved
        event (str, optional): Event name

    Returns:
        None
    """
    try:
        # Skip for system user
        if frappe.session.user == "Administrator":
            return

        # Get old document for comparison
        if doc.name:
            old_doc = frappe.get_doc(doc.doctype, doc.name)
        else:
            old_doc = None

        # Get permissions
        perms = get_doc_perms(doc)

        # Check if user can write to fields
        if perms["write"] is not None:
            for field in doc.meta.fields:
                field_name = field.fieldname

                # Skip read-only and computed fields
                if field.read_only or field.fetch_from or field.formula:
                    continue

                # Check if field was changed
                if (
                    old_doc
                    and hasattr(old_doc, field_name)
                    and hasattr(doc, field_name)
                ):
                    old_value = old_doc.get(field_name)
                    new_value = doc.get(field_name)

                    if old_value != new_value and field_name not in perms["write"]:
                        frappe.throw(
                            _("You don't have permission to change {0}").format(
                                field.label or field_name
                            )
                        )

    except Exception as e:
        frappe.log_error(f"Error in validate_field_permissions: {str(e)}")
        frappe.throw(_("Error validating field permissions: {0}").format(str(e)))
