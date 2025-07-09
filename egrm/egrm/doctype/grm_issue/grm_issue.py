import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, now_datetime

from egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment import (
    get_user_assignments,
)
from egrm.utils.tracking_code_generator import generate_tracking_code


class GRMIssue(Document):
    def autoname(self):
        """Use WatermelonDB ID if provided, otherwise use Frappe naming series"""
        # Check if coming from sync with custom ID
        print("AutoName - checking for sync name")

        # If this document is being created from sync, use the provided sync name
        if hasattr(self, "_sync_name") and self._sync_name:
            self.name = self._sync_name
            print(f"AutoName - using sync name: {self.name}")
            return

        # If no sync name, let Frappe handle naming series/auto-generation
        # This will happen for documents created through the UI
        print("AutoName - no sync name, using default naming")

    def before_validate(self):
        try:
            print("Name during validate", self.name)
            user = frappe.session.user
            frappe.log(f"Getting regions for user: {user}")

            # Check if user is guest (not allowed)
            if user == "Guest":
                return {"status": "error", "message": _("Authentication required")}

            # Get user's project assignments and assigned regions automatically
            projects, regions = get_user_assignments(user)

            print(projects)

            # Auto-set project if not already set and user has assignments
            if not self.project and projects and len(projects) > 0:
                project_found = False

                # If user has only one project, use it
                if len(projects) == 1:
                    self.project = projects[0]
                    frappe.log(f"Auto-set project to {self.project} for user {user}")
                    project_found = True

                # Try to find project using available fields in a prioritized order
                if not project_found and self.administrative_region:
                    region_project = frappe.db.get_value(
                        "GRM Administrative Region",
                        self.administrative_region,
                        "project",
                    )
                    if region_project and region_project in projects:
                        self.project = region_project
                        frappe.log(
                            f"Auto-set project to {self.project} based on region {self.administrative_region}"
                        )
                        project_found = True

                if not project_found and self.category:
                    for project in projects:
                        category_belongs_to_project = frappe.db.exists(
                            "GRM Project Link",
                            {"parent": self.category, "project": project},
                        )
                        if category_belongs_to_project:
                            self.project = project
                            frappe.log(
                                f"Auto-set project to {self.project} based on category {self.category}"
                            )
                            project_found = True
                            break

                if not project_found and self.issue_type:
                    for project in projects:
                        issue_type_belongs_to_project = frappe.db.exists(
                            "GRM Project Link",
                            {"parent": self.issue_type, "project": project},
                        )
                        if issue_type_belongs_to_project:
                            self.project = project
                            frappe.log(
                                f"Auto-set project to {self.project} based on issue_type {self.issue_type}"
                            )
                            break

            if not self.intake_date:
                self.intake_date = getdate()

            # Set issue_date to today if not already set
            if not self.issue_date:
                self.issue_date = getdate()

            # Set default status if not already set
            if not self.status and self.project:
                # Try to find an initial status for this project
                initial_statuses = frappe.get_all(
                    "GRM Issue Status", filters={"initial_status": 1}, fields=["name"]
                )

                for status in initial_statuses:
                    status_belongs_to_project = frappe.db.exists(
                        "GRM Project Link",
                        {"parent": status.name, "project": self.project},
                    )
                    if status_belongs_to_project:
                        self.status = status.name
                        frappe.log(
                            f"Auto-set status to {self.status} for project {self.project}"
                        )
                        break

            frappe.log(f"Completed Before validate for GRM Issue {self.name}")
        except Exception as e:
            frappe.log_error(f"Error in before_validate: {str(e)}")
            raise

    def validate(self):
        try:
            # Generate tracking code if not provided (for cases where it wasn't generated in before_insert)
            if not self.tracking_code and self.project:
                frappe.log(
                    f"No tracking code found, generating during validation for project: {self.project}"
                )
                self.tracking_code = generate_tracking_code(
                    project_id=self.project, issue_date=self.issue_date
                )
                frappe.log(
                    f"Generated tracking code during validation: {self.tracking_code}"
                )

            # Validate project related fields
            self.validate_project_entities()

            # Validate dates
            self.validate_dates()

            frappe.log(f"Validating GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error validating GRM Issue: {str(e)}")
            raise

    def before_insert(self):
        try:
            # Generate auto increment ID, internal code, and tracking code
            self.generate_codes()
            frappe.log(f"Generated codes for GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error generating codes for GRM Issue: {str(e)}")
            raise

    def on_update(self):
        try:
            # Check for escalation needs
            self.check_escalation()
            frappe.log(f"Updated GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error updating GRM Issue: {str(e)}")
            raise

    def on_submit(self):
        try:
            # Add log entry for submission
            self.add_log(_("Issue submitted"), frappe.session.user)

            frappe.log(f"Submitted GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error submitting GRM Issue: {str(e)}")
            raise

    def on_cancel(self):
        try:
            # Add log entry for cancellation
            self.add_log(_("Issue cancelled"), frappe.session.user)

            frappe.log(f"Cancelled GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error cancelling GRM Issue: {str(e)}")
            raise

    def generate_codes(self):
        try:
            # Generate tracking code using consistent format: {PROJECT_CODE}-{YYMMDD}-{NNNN}
            if not self.tracking_code:
                frappe.log(f"Generating tracking code for project: {self.project}")
                self.tracking_code = generate_tracking_code(
                    project_id=self.project, issue_date=self.issue_date
                )
                frappe.log(f"Generated tracking code: {self.tracking_code}")
        except Exception as e:
            frappe.log_error(f"Error generating codes: {str(e)}")
            frappe.log_error(f"Error generating codes: {str(e)}")
            raise

    def validate_project_entities(self):
        try:
            # Check that status belongs to the project
            status_belongs_to_project = frappe.db.exists(
                "GRM Project Link", {"parent": self.status, "project": self.project}
            )

            if not status_belongs_to_project:
                frappe.throw(
                    _("Status {0} does not belong to project {1}").format(
                        self.status, self.project
                    )
                )

            # Check that category belongs to the project
            category_belongs_to_project = frappe.db.exists(
                "GRM Project Link", {"parent": self.category, "project": self.project}
            )

            if not category_belongs_to_project:
                frappe.throw(
                    _("Category {0} does not belong to project {1}").format(
                        self.category, self.project
                    )
                )

            # Check that issue type belongs to the project
            issue_type_belongs_to_project = frappe.db.exists(
                "GRM Project Link", {"parent": self.issue_type, "project": self.project}
            )

            if not issue_type_belongs_to_project:
                frappe.throw(
                    _("Issue Type {0} does not belong to project {1}").format(
                        self.issue_type, self.project
                    )
                )

            # Check that administrative region belongs to the project
            print("Validating regions", self.administrative_region, self.project)
            region_belongs_to_project = (
                frappe.db.get_value(
                    "GRM Administrative Region", self.administrative_region, "project"
                )
                == self.project
            )

            if not region_belongs_to_project:
                frappe.throw(
                    _(
                        "Administrative Region {0} does not belong to project {1}"
                    ).format(self.administrative_region, self.project)
                )

            # Check optional fields
            if self.citizen_age_group:
                age_group_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {"parent": self.citizen_age_group, "project": self.project},
                )

                if not age_group_belongs_to_project:
                    frappe.throw(
                        _("Age Group {0} does not belong to project {1}").format(
                            self.citizen_age_group, self.project
                        )
                    )

            if self.citizen_group_1:
                group1_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {"parent": self.citizen_group_1, "project": self.project},
                )

                if not group1_belongs_to_project:
                    frappe.throw(
                        _("Citizen Group {0} does not belong to project {1}").format(
                            self.citizen_group_1, self.project
                        )
                    )

            if self.citizen_group_2:
                group2_belongs_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {"parent": self.citizen_group_2, "project": self.project},
                )

                if not group2_belongs_to_project:
                    frappe.throw(
                        _("Citizen Group {0} does not belong to project {1}").format(
                            self.citizen_group_2, self.project
                        )
                    )

            # Check assignee
            if self.assignee:
                assignee_has_access = frappe.db.exists(
                    "GRM User Project Assignment",
                    {"user": self.assignee, "project": self.project, "is_active": 1},
                )

                if not assignee_has_access:
                    frappe.throw(
                        _("Assignee {0} does not have access to project {1}").format(
                            self.assignee, self.project
                        )
                    )

        except Exception as e:
            frappe.log(f"Error validating project entities: {str(e)}")
            raise

    def validate_dates(self):
        try:
            # Check that issue_date is not after intake_date
            if (
                self.issue_date
                and self.intake_date
                and getdate(self.issue_date) > getdate(self.intake_date)
            ):
                frappe.throw(_("Issue Date cannot be after Intake Date"))

            # Check that resolution_date is not before created_date
            if (
                self.resolution_date
                and self.creation
                and getdate(self.resolution_date) < getdate(self.creation)
            ):
                frappe.throw(_("Resolution Date cannot be before Created Date"))
        except Exception as e:
            frappe.log(f"Error validating dates: {str(e)}")
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
            frappe.log(f"Error adding log: {str(e)}")
            raise

    def check_escalation(self):
        try:
            # Check auto escalation conditions
            if not self.escalate_flag:
                # Get the project's auto escalation days
                auto_escalation_days = frappe.db.get_value(
                    "GRM Project", self.project, "auto_escalation_days"
                )

                if auto_escalation_days:
                    # Check if the issue has been open too long
                    status_is_open = frappe.db.get_value(
                        "GRM Issue Status", self.status, "open_status"
                    )

                    if status_is_open:
                        from datetime import datetime, timedelta

                        creation = datetime.strptime(
                            str(self.creation), "%Y-%m-%d %H:%M:%S.%f"
                        )
                        now = now_datetime()
                        days_open = (now - creation).days

                        if days_open > auto_escalation_days:
                            # Set escalate flag
                            self.db_set("escalate_flag", 1)

                            # Add log entry
                            self.add_log(
                                _(
                                    "Issue automatically escalated after {0} days"
                                ).format(days_open)
                            )

                            # Get category's escalation department
                            dept = frappe.db.get_value(
                                "GRM Issue Category",
                                self.category,
                                "assigned_escalation_department",
                            )

                            if dept:
                                # Get department head
                                head = frappe.db.get_value(
                                    "GRM Issue Department", dept, "head"
                                )

                                if head:
                                    # Assign to department head
                                    self.db_set("assignee", head)

                                    # Add log entry
                                    self.add_log(
                                        _(
                                            "Issue assigned to escalation department head {0}"
                                        ).format(head)
                                    )

                                    # Notify department head
                                    self.notify_user(
                                        head,
                                        _("Issue Escalated"),
                                        _("Issue {0} has been escalated to you").format(
                                            self.name
                                        ),
                                    )
        except Exception as e:
            frappe.log(f"Error checking escalation: {str(e)}")
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
                reference_name=self.name,
            )

            frappe.log(f"Notification sent to {user} for GRM Issue {self.name}")
        except Exception as e:
            frappe.log(f"Error sending notification: {str(e)}")
            # Don't raise exception for notification errors, just log them

    def get_citizen_name(self):
        """Get citizen name based on type"""
        return self.citizen

    def get_contact_info(self):
        """Get contact information based on type"""
        return self.contact_information

    def has_permission_to_view_sensitive_data(self):
        """Check if current user has permission to view sensitive data"""
        try:
            # System Manager and GRM Administrator always have access
            if (
                "System Manager" in frappe.get_roles()
                or "GRM Administrator" in frappe.get_roles()
            ):
                return True

            # Project Manager of this project can view
            if frappe.db.exists(
                "GRM User Project Assignment",
                {
                    "user": frappe.session.user,
                    "project": self.project,
                    "role": "GRM Project Manager",
                    "is_active": 1,
                },
            ):
                return True

            # Department Head for this category can view
            category_dept = frappe.db.get_value(
                "GRM Issue Category", self.category, "assigned_department"
            )
            if category_dept and frappe.db.exists(
                "GRM User Project Assignment",
                {
                    "user": frappe.session.user,
                    "project": self.project,
                    "role": "GRM Department Head",
                    "department": category_dept,
                    "is_active": 1,
                },
            ):
                return True

            # Current assignee can view
            if self.assignee == frappe.session.user:
                return True

            # By default, no access to sensitive data
            return False
        except Exception as e:
            frappe.log(f"Error checking sensitive data permissions: {str(e)}")
            return False
