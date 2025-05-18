import frappe
from frappe import _
from frappe.model.document import Document
import logging
import random
import string
import json
from frappe.utils import cint, getdate, now_datetime
import re

log = logging.getLogger(__name__)

class GRMIssue(Document):
    def before_validate(self):
        try:
            # Set intake_date to today if not already set
            if not self.intake_date:
                self.intake_date = getdate()

            # Set issue_date to today if not already set
            if not self.issue_date:
                self.issue_date = getdate()

            log.info(f"Before validate for GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error in before_validate for GRM Issue: {str(e)}")
            raise

    def validate(self):
        try:
            # Validate project related fields
            self.validate_project_entities()
            
            # Validate citizen data based on type
            self.validate_citizen_data()
            
            # Validate dates
            self.validate_dates()
            
            log.info(f"Validating GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error validating GRM Issue: {str(e)}")
            raise

    def before_insert(self):
        try:
            # Generate auto increment ID, internal code, and tracking code
            self.generate_codes()
            log.info(f"Generated codes for GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error generating codes for GRM Issue: {str(e)}")
            raise

    def on_update(self):
        try:
            # Add log entry for changes
            self.add_update_log()

            # Check for escalation needs
            self.check_escalation()

            log.info(f"Updated GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error updating GRM Issue: {str(e)}")
            raise

    def on_submit(self):
        try:
            # Set confirmed flag
            self.db_set("confirmed", 1)

            # Add log entry for submission
            self.add_log(_("Issue submitted"), frappe.session.user)

            log.info(f"Submitted GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error submitting GRM Issue: {str(e)}")
            raise

    def on_cancel(self):
        try:
            # Add log entry for cancellation
            self.add_log(_("Issue cancelled"), frappe.session.user)

            log.info(f"Cancelled GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error cancelling GRM Issue: {str(e)}")
            raise

    def generate_codes(self):
        try:
            # Generate sequential ID for the project
            if not self.auto_increment_id:
                key = f"grm-issue-{self.project}"
                self.auto_increment_id = cint(frappe.db.get_global(key) or 0) + 1
                frappe.db.set_global(key, self.auto_increment_id)

            # Generate internal code based on project, category, and sequential ID
            if not self.internal_code:
                category_abbr = frappe.db.get_value("GRM Issue Category", self.category, "abbreviation") or "CAT"
                project_code = frappe.db.get_value("GRM Project", self.project, "project_code") or "PRJ"
                self.internal_code = f"{project_code}-{category_abbr}-{self.auto_increment_id:04d}"

            # Generate tracking code with some randomness for security
            if not self.tracking_code:
                project_code = frappe.db.get_value("GRM Project", self.project, "project_code") or "PRJ"
                random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                self.tracking_code = f"{project_code}-{random_suffix}"
        except Exception as e:
            log.error(f"Error generating codes: {str(e)}")
            raise

    def validate_project_entities(self):
        try:
            # Check that status belongs to the project
            status_belongs_to_project = frappe.db.exists(
                "GRM Project Link",
                {
                    "parent": self.status,
                    "project": self.project
                }
            )

            if not status_belongs_to_project:
                frappe.throw(_("Status {0} does not belong to project {1}").format(
                    self.status, self.project))

            # Check that category belongs to the project
            category_belongs_to_project = frappe.db.exists(
                "GRM Project Link",
                {
                    "parent": self.category,
                    "project": self.project
                }
            )

            if not category_belongs_to_project:
                frappe.throw(_("Category {0} does not belong to project {1}").format(
                    self.category, self.project))

            # Check that issue type belongs to the project
            issue_type_belongs_to_project = frappe.db.exists(
                "GRM Project Link",
                {
                    "parent": self.issue_type,
                    "project": self.project
                }
            )

            if not issue_type_belongs_to_project:
                frappe.throw(_("Issue Type {0} does not belong to project {1}").format(
                    self.issue_type, self.project))

            # Check that administrative region belongs to the project
            region_belongs_to_project = frappe.db.get_value(
                "GRM Administrative Region",
                self.administrative_region,
                "project"
            ) == self.project

            if not region_belongs_to_project:
                frappe.throw(_("Administrative Region {0} does not belong to project {1}").format(
                    self.administrative_region, self.project))

            # Check optional fields
            if self.citizen_age_group:
                age_group_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {
                        "parent": self.citizen_age_group,
                        "project": self.project
                    }
                )

                if not age_group_belongs_to_project:
                    frappe.throw(_("Age Group {0} does not belong to project {1}").format(
                        self.citizen_age_group, self.project))

            if self.citizen_group_1:
                group1_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {
                        "parent": self.citizen_group_1,
                        "project": self.project
                    }
                )

                if not group1_belongs_to_project:
                    frappe.throw(_("Citizen Group {0} does not belong to project {1}").format(
                        self.citizen_group_1, self.project))

            if self.citizen_group_2:
                group2_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {
                        "parent": self.citizen_group_2,
                        "project": self.project
                    }
                )

                if not group2_belongs_to_project:
                    frappe.throw(_("Citizen Group {0} does not belong to project {1}").format(
                        self.citizen_group_2, self.project))

            # Check assignee
            if self.assignee:
                assignee_has_access = frappe.db.exists(
                    "GRM User Project Assignment",
                    {
                        "user": self.assignee,
                        "project": self.project,
                        "is_active": 1
                    }
                )

                if not assignee_has_access:
                    frappe.throw(_("Assignee {0} does not have access to project {1}").format(
                        self.assignee, self.project))
        except Exception as e:
            log.error(f"Error validating project entities: {str(e)}")
            raise

    def validate_citizen_data(self):
        """Ensure the right citizen fields are filled based on type"""
        try:
            # For confidential citizens (type 1)
            if self.citizen_type == "1":
                if not self.citizen_confidential:
                    frappe.throw(_("Confidential citizen information is required"))
                # Clear non-confidential field for safety
                self.citizen = None
                
                # Handle contact information if contact medium is selected
                if self.contact_medium == "contact":
                    if not self.contact_info_confidential:
                        frappe.throw(_("Confidential contact information is required"))
                    # Clear non-confidential contact info
                    self.contact_information = None
            else:
                # For non-confidential citizens
                if not self.citizen:
                    frappe.throw(_("Citizen information is required"))
                # Clear confidential field for safety
                self.citizen_confidential = None
                
                # Handle contact information if contact medium is selected
                if self.contact_medium == "contact":
                    if not self.contact_information:
                        frappe.throw(_("Contact information is required"))
                    # Clear confidential contact info
                    self.contact_info_confidential = None
        except Exception as e:
            log.error(f"Error validating citizen data: {str(e)}")
            raise

    def validate_dates(self):
        try:
            # Check that issue_date is not after intake_date
            if self.issue_date and self.intake_date and getdate(self.issue_date) > getdate(self.intake_date):
                frappe.throw(_("Issue Date cannot be after Intake Date"))

            # Check that resolution_date is not before created_date
            if self.resolution_date and self.created_date and getdate(self.resolution_date) < getdate(self.created_date):
                frappe.throw(_("Resolution Date cannot be before Created Date"))
        except Exception as e:
            log.error(f"Error validating dates: {str(e)}")
            raise

    def add_update_log(self):
        try:
            # Get old values
            if not self.is_new():
                old_values = frappe.get_doc("GRM Issue", self.name)

                # Check for changes in important fields
                fields_to_check = [
                    "status", "assignee", "category", "issue_type", "administrative_region",
                    "escalate_flag", "resolution_accepted", "rating"
                ]

                for field in fields_to_check:
                    if self.get(field) != old_values.get(field):
                        old_value = old_values.get(field) or "None"
                        new_value = self.get(field) or "None"
                        log_text = _("Changed {0} from {1} to {2}").format(
                            frappe.meta.get_label("GRM Issue", field),
                            old_value,
                            new_value
                        )
                        self.add_log(log_text, frappe.session.user)
        except Exception as e:
            log.error(f"Error adding update log: {str(e)}")
            raise

    def add_log(self, text, user=None):
        try:
            if not user:
                user = frappe.session.user

            log_row = {}
            log_row["text"] = text
            log_row["user"] = user
            log_row["timestamp"] = now_datetime()

            self.append("grm_issue_log", log_row)

            # Save the document if it's not new
            if not self.is_new():
                self.save()
        except Exception as e:
            log.error(f"Error adding log: {str(e)}")
            raise

    def check_escalation(self):
        try:
            # Check auto escalation conditions
            if not self.escalate_flag:
                # Get the project's auto escalation days
                auto_escalation_days = frappe.db.get_value("GRM Project", self.project, "auto_escalation_days")

                if auto_escalation_days:
                    # Check if the issue has been open too long
                    status_is_open = frappe.db.get_value("GRM Issue Status", self.status, "open_status")

                    if status_is_open:
                        from datetime import datetime, timedelta

                        created_date = datetime.strptime(str(self.created_date), "%Y-%m-%d %H:%M:%S.%f")
                        now = now_datetime()
                        days_open = (now - created_date).days

                        if days_open > auto_escalation_days:
                            # Set escalate flag
                            self.db_set("escalate_flag", 1)

                            # Add log entry
                            self.add_log(_("Issue automatically escalated after {0} days").format(days_open))

                            # Get category's escalation department
                            dept = frappe.db.get_value("GRM Issue Category", self.category, "assigned_escalation_department")

                            if dept:
                                # Get department head
                                head = frappe.db.get_value("GRM Issue Department", dept, "head")

                                if head:
                                    # Assign to department head
                                    self.db_set("assignee", head)

                                    # Add log entry
                                    self.add_log(_("Issue assigned to escalation department head {0}").format(head))

                                    # Notify department head
                                    self.notify_user(head, _("Issue Escalated"),
                                                    _("Issue {0} has been escalated to you").format(self.name))
        except Exception as e:
            log.error(f"Error checking escalation: {str(e)}")
            raise

    def notify_user(self, user, subject, message):
        try:
            # Send a notification to the user
            from frappe.utils.user import get_user_fullname

            frappe.sendmail(
                recipients=[user],
                sender=frappe.session.user,
                subject=subject,
                message=message,
                reference_doctype="GRM Issue",
                reference_name=self.name
            )

            log.info(f"Notification sent to {user} for GRM Issue {self.name}")
        except Exception as e:
            log.error(f"Error sending notification: {str(e)}")
            # Don't raise exception for notification errors, just log them
    
    def get_citizen_name(self):
        """Get citizen name based on type"""
        if self.citizen_type == "1":
            # Check if user has permission to view confidential data
            if self.has_permission_to_view_sensitive_data():
                return self.citizen_confidential
            else:
                return "[Confidential]"
        else:
            return self.citizen

    def get_contact_info(self):
        """Get contact information based on type"""
        if self.contact_medium != "contact":
            return None
            
        if self.citizen_type == "1":
            # Check if user has permission to view confidential data
            if self.has_permission_to_view_sensitive_data():
                return self.contact_info_confidential
            else:
                return "[Confidential]"
        else:
            return self.contact_information
            
    def has_permission_to_view_sensitive_data(self):
        """Check if current user has permission to view sensitive data"""
        try:
            # System Manager and GRM Administrator always have access
            if "System Manager" in frappe.get_roles() or "GRM Administrator" in frappe.get_roles():
                return True
                
            # Project Manager of this project can view
            if frappe.db.exists("GRM User Project Assignment", {
                "user": frappe.session.user,
                "project": self.project,
                "role": "GRM Project Manager",
                "is_active": 1
            }):
                return True
                
            # Department Head for this category can view
            category_dept = frappe.db.get_value("GRM Issue Category", self.category, "assigned_department")
            if category_dept and frappe.db.exists("GRM User Project Assignment", {
                "user": frappe.session.user,
                "project": self.project,
                "role": "GRM Department Head",
                "department": category_dept,
                "is_active": 1
            }):
                return True
                
            # Current assignee can view
            if self.assignee == frappe.session.user:
                return True
                
            # By default, no access to sensitive data
            return False
        except Exception as e:
            log.error(f"Error checking sensitive data permissions: {str(e)}")
            return False
