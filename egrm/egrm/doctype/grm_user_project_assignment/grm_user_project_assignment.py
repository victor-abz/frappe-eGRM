import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, add_to_date, now_datetime, get_datetime
import logging
import zlib
import random
import string

log = logging.getLogger(__name__)

class GRMUserProjectAssignment(Document):
    def validate(self):
        try:
            self.validate_user()
            self.validate_role()
            self.validate_department_and_region()
            self.validate_unique_assignment()
            self.validate_activation_status()
            log.info(f"Validating GRM User Project Assignment {self.name}")
        except Exception as e:
            log.error(f"Error validating GRM User Project Assignment: {str(e)}")
            raise

    def validate_user(self):
        try:
            # Check if the user exists
            if not frappe.db.exists("User", self.user):
                frappe.throw(_("User {0} does not exist").format(self.user))

            # Check if the user is enabled
            if frappe.db.get_value("User", self.user, "enabled") != 1:
                frappe.throw(_("User {0} is not enabled").format(self.user))
        except Exception as e:
            log.error(f"Error validating user: {str(e)}")
            raise

    def validate_role(self):
        try:
            # Check if the role exists
            if not frappe.db.exists("Role", self.role):
                frappe.throw(_("Role {0} does not exist").format(self.role))

            # Check if the role is a GRM role
            valid_grm_roles = [
                "GRM Administrator",
                "GRM Project Manager",
                "GRM Department Head",
                "GRM Field Officer",
                "GRM Analyst"
            ]

            if self.role not in valid_grm_roles:
                frappe.throw(_("Role {0} is not a valid GRM role").format(self.role))

            # Assign the role to the user
            from frappe.permissions import add_user_permission
            add_user_permission("Role", self.role, self.user)
        except Exception as e:
            log.error(f"Error validating role: {str(e)}")
            raise

    def validate_department_and_region(self):
        try:
            # Department Head must have a department
            if self.role == "GRM Department Head" and not self.department:
                frappe.throw(_("Department Head must have a department assigned"))

            # Field Officer must have an administrative region
            if self.role == "GRM Field Officer" and not self.administrative_region:
                frappe.throw(_("Field Officer must have an administrative region assigned"))

            # If department is specified, check if it belongs to the project
            if self.department:
                dept_linked_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {
                        "parent": self.department,
                        "project": self.project
                    }
                )

                if not dept_linked_to_project:
                    frappe.throw(_("Department {0} is not linked to project {1}").format(
                        self.department, self.project))

            # If administrative region is specified, check if it belongs to the project
            if self.administrative_region:
                region_belongs_to_project = frappe.db.get_value(
                    "GRM Administrative Region",
                    self.administrative_region,
                    "project"
                ) == self.project

                if not region_belongs_to_project:
                    frappe.throw(_("Administrative Region {0} does not belong to project {1}").format(
                        self.administrative_region, self.project))
        except Exception as e:
            log.error(f"Error validating department and region: {str(e)}")
            raise

    def validate_unique_assignment(self):
        try:
            # Check if the user is already assigned to the project with the same role
            existing = frappe.db.exists(
                "GRM User Project Assignment",
                {
                    "user": self.user,
                    "project": self.project,
                    "role": self.role,
                    "name": ["!=", self.name]
                }
            )

            if existing:
                frappe.throw(_("User {0} is already assigned to project {1} with role {2}").format(
                    self.user, self.project, self.role))
        except Exception as e:
            log.error(f"Error validating unique assignment: {str(e)}")
            raise

    def after_insert(self):
        try:
            # Add project permission to the user
            from frappe.permissions import add_user_permission
            add_user_permission("GRM Project", self.project, self.user)

            # Add department permission if applicable
            if self.department:
                add_user_permission("GRM Issue Department", self.department, self.user)

            # Add region permission if applicable
            if self.administrative_region:
                add_user_permission("GRM Administrative Region", self.administrative_region, self.user)

            log.info(f"Added permissions for user {self.user} for project {self.project}")
        except Exception as e:
            log.error(f"Error setting up permissions: {str(e)}")
            frappe.throw(_("Error setting up permissions. Please check the logs."))

    def on_trash(self):
        try:
            # Remove project permission from the user
            from frappe.permissions import remove_user_permission
            remove_user_permission("GRM Project", self.project, self.user)

            # Remove department permission if applicable
            if self.department:
                remove_user_permission("GRM Issue Department", self.department, self.user)

            # Remove region permission if applicable
            if self.administrative_region:
                remove_user_permission("GRM Administrative Region", self.administrative_region, self.user)

            log.info(f"Removed permissions for user {self.user} for project {self.project}")
        except Exception as e:
            log.error(f"Error removing permissions: {str(e)}")
            frappe.throw(_("Error removing permissions. Please check the logs."))

    def before_insert(self):
        """Auto-generate activation code for government workers"""
        try:
            # Check if this is a government worker role
            if self.is_government_worker_role():
                if not self.activation_status:
                    self.activation_status = "Draft"

                # Generate activation code for new government workers
                if not self.activation_code:
                    self.generate_activation_code()
                    log.info(f"Generated activation code for government worker {self.user}")
            else:
                # For non-government workers, set as activated
                self.activation_status = "Activated"
                self.activated_on = now()
                log.info(f"Non-government worker {self.user} automatically activated")

        except Exception as e:
            log.error(f"Error in before_insert: {str(e)}")
            raise

    def is_government_worker_role(self):
        """Check if the role is for government workers"""
        try:
            government_worker_roles = [
                "GRM Field Officer",
                "GRM Department Head"
            ]
            return self.role in government_worker_roles
        except Exception as e:
            log.error(f"Error checking government worker role: {str(e)}")
            return False

    def generate_activation_code(self):
        """Generate 6-digit activation code using zlib.adler32 like Django implementation"""
        try:
            # Use email as seed for consistent code generation (like Django implementation)
            user_email = frappe.db.get_value("User", self.user, "email")
            if not user_email:
                frappe.throw(_("User email is required for activation code generation"))

            # Generate code using zlib.adler32 (similar to Django implementation)
            seed = f"{user_email}{self.name}{now()}"
            raw_code = str(zlib.adler32(seed.encode('utf-8')))

            # Take first 6 digits
            self.activation_code = raw_code[:6]

            # Set expiration (48 hours from now)
            self.activation_expires_on = add_to_date(now(), hours=48)

            log.info(f"Generated activation code for {user_email}")

        except Exception as e:
            log.error(f"Error generating activation code: {str(e)}")
            raise

    def send_activation_email(self):
        """Send email with activation code"""
        try:
            if not self.activation_code:
                frappe.throw(_("No activation code found. Please generate a code first."))

            user_email = frappe.db.get_value("User", self.user, "email")
            user_full_name = frappe.db.get_value("User", self.user, "full_name")

            if not user_email:
                frappe.throw(_("User email is required to send activation code"))

            # Prepare email content
            subject = _("GRM System - Government Worker Activation Code")

            # Use email template if exists, otherwise use basic template
            try:
                template = frappe.get_doc("Email Template", "GRM Government Worker Activation")
                message = frappe.render_template(template.response, {
                    "user_name": user_full_name or self.user,
                    "activation_code": self.activation_code,
                    "position_title": self.position_title or "Government Worker",
                    "expiry_date": self.activation_expires_on,
                    "project_name": frappe.db.get_value("GRM Project", self.project, "title")
                })
            except:
                # Fallback basic email template
                message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #2e86de; text-align: center;">GRM System Activation</h2>

                    <p>Dear {user_full_name or self.user},</p>

                    <p>You have been assigned as a government worker in the GRM system. Please use the following activation code to activate your account:</p>

                    <div style="background: #f1f3f4; padding: 20px; text-align: center; margin: 20px 0; border-radius: 5px;">
                        <h1 style="color: #2e86de; margin: 0; font-size: 32px; letter-spacing: 5px;">{self.activation_code}</h1>
                    </div>

                    <p><strong>Position:</strong> {self.position_title or 'Government Worker'}</p>
                    <p><strong>Code expires on:</strong> {self.activation_expires_on}</p>

                    <p>To activate your account, please use the mobile app or contact your system administrator.</p>

                    <p>If you have any questions, please contact your system administrator.</p>

                    <p>Best regards,<br>GRM System Team</p>
                </div>
                """

            # Send email
            frappe.sendmail(
                recipients=user_email,
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )

            # Update tracking fields
            self.code_sent_on = now()
            self.activation_status = "Pending Activation"

            log.info(f"Activation email sent to {user_email}")
            return True

        except Exception as e:
            log.error(f"Error sending activation email: {str(e)}")
            frappe.throw(_(f"Error sending activation email: {str(e)}"))

    def activate_worker(self, activation_code, new_password=None):
        """Validate and activate worker"""
        try:
            # Validate current status
            if self.activation_status == "Activated":
                frappe.throw(_("Worker is already activated"))

            if self.activation_status == "Expired":
                frappe.throw(_("Activation code has expired. Please request a new code."))

            if self.activation_status == "Suspended":
                frappe.throw(_("Account is suspended. Please contact administrator."))

            # Check expiration
            if self.activation_expires_on and get_datetime(self.activation_expires_on) < now_datetime():
                self.activation_status = "Expired"
                self.save()
                frappe.throw(_("Activation code has expired. Please request a new code."))

            # Check attempt limits
            if self.activation_attempts >= 5:
                self.activation_status = "Suspended"
                self.save()
                frappe.throw(_("Too many failed attempts. Account has been suspended."))

            # Validate activation code
            if self.activation_code != activation_code:
                self.activation_attempts += 1
                self.save()
                frappe.throw(_(f"Invalid activation code. Attempts remaining: {5 - self.activation_attempts}"))

            # Activate the worker
            self.activation_status = "Activated"
            self.activated_on = now()
            self.activation_attempts = 0  # Reset attempts on successful activation

            # Update user password if provided
            if new_password:
                user_doc = frappe.get_doc("User", self.user)
                user_doc.new_password = new_password
                user_doc.save()

            self.save()

            log.info(f"Government worker {self.user} activated successfully")
            return True

        except Exception as e:
            log.error(f"Error activating worker: {str(e)}")
            raise

    def resend_activation_code(self):
        """Generate new code and resend email"""
        try:
            if self.activation_status == "Activated":
                frappe.throw(_("Worker is already activated"))

            if self.activation_status == "Suspended":
                frappe.throw(_("Account is suspended. Please contact administrator."))

            # Generate new code
            self.generate_activation_code()

            # Reset attempts
            self.activation_attempts = 0

            # Send email
            self.send_activation_email()

            self.save()

            log.info(f"Activation code resent for {self.user}")
            return True

        except Exception as e:
            log.error(f"Error resending activation code: {str(e)}")
            raise

    def expire_activation_code(self):
        """Mark code as expired"""
        try:
            self.activation_status = "Expired"
            self.save()

            log.info(f"Activation code expired for {self.user}")
            return True

        except Exception as e:
            log.error(f"Error expiring activation code: {str(e)}")
            raise

    def validate_activation_status(self):
        """Check code expiration and attempt limits"""
        try:
            # Auto-expire codes if past expiration
            if (self.activation_status == "Pending Activation" and
                self.activation_expires_on and
                get_datetime(self.activation_expires_on) < now_datetime()):
                self.activation_status = "Expired"
                log.info(f"Auto-expired activation code for {self.user}")

            # Check attempt limits
            if self.activation_attempts >= 5 and self.activation_status not in ["Activated", "Suspended"]:
                self.activation_status = "Suspended"
                log.info(f"Auto-suspended account for {self.user} due to too many failed attempts")

        except Exception as e:
            log.error(f"Error validating activation status: {str(e)}")
            raise

    @frappe.whitelist()
    def export_activation_codes(self):
        """Generate CSV with activation codes"""
        try:
            # Check permissions
            if not frappe.has_permission(self.doctype, "export"):
                frappe.throw(_("No permission to export activation codes"))

            import csv
            import io

            # Get all government worker assignments for this project
            assignments = frappe.get_all(
                "GRM User Project Assignment",
                filters={
                    "project": self.project,
                    "role": ["in", ["GRM Field Officer", "GRM Department Head"]]
                },
                fields=[
                    "user", "activation_code", "activation_status",
                    "position_title", "administrative_region", "department", "activation_expires_on"
                ]
            )

            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers
            writer.writerow([
                "Email", "Activation_Code", "Status", "Position",
                "Region", "Department", "Expires_On"
            ])

            # Write data
            for assignment in assignments:
                user_email = frappe.db.get_value("User", assignment.user, "email")
                region_name = ""
                if assignment.administrative_region:
                    region_name = frappe.db.get_value("GRM Administrative Region", assignment.administrative_region, "region_name")

                department_name = ""
                if assignment.department:
                    department_name = frappe.db.get_value("GRM Issue Department", assignment.department, "department_name")

                writer.writerow([
                    user_email or "",
                    assignment.activation_code or "",
                    assignment.activation_status or "",
                    assignment.position_title or "",
                    region_name,
                    department_name,
                    assignment.activation_expires_on or ""
                ])

            csv_content = output.getvalue()
            output.close()

            log.info(f"Exported activation codes for project {self.project}")
            return csv_content

        except Exception as e:
            log.error(f"Error exporting activation codes: {str(e)}")
            frappe.throw(_(f"Error exporting activation codes: {str(e)}"))


# Static method for bulk export
@frappe.whitelist()
def export_project_activation_codes(project_code):
    """Export activation codes for a specific project"""
    try:
        # Check permissions
        if not frappe.has_permission("GRM User Project Assignment", "export"):
            frappe.throw(_("No permission to export activation codes"))

        import csv
        import tempfile
        import os
        from frappe.utils.file_manager import save_file

        # Get all government worker assignments for this project
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters={
                "project": project_code,
                "role": ["in", ["GRM Field Officer", "GRM Department Head"]]
            },
            fields=[
                "user", "activation_code", "activation_status",
                "position_title", "administrative_region", "department", "activation_expires_on"
            ]
        )

        if not assignments:
            frappe.throw(_("No government worker assignments found for this project"))

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            writer = csv.writer(tmp_file)

            # Write headers
            writer.writerow([
                "Email", "Activation_Code", "Status", "Position",
                "Region", "Department", "Expires_On"
            ])

            # Write data
            for assignment in assignments:
                user_email = frappe.db.get_value("User", assignment.user, "email")
                region_name = ""
                if assignment.administrative_region:
                    region_name = frappe.db.get_value("GRM Administrative Region", assignment.administrative_region, "region_name")

                department_name = ""
                if assignment.department:
                    department_name = frappe.db.get_value("GRM Issue Department", assignment.department, "department_name")

                writer.writerow([
                    user_email or "",
                    assignment.activation_code or "",
                    assignment.activation_status or "",
                    assignment.position_title or "",
                    region_name,
                    department_name,
                    assignment.activation_expires_on or ""
                ])

        # Read file content and create download
        with open(tmp_file.name, 'r') as f:
            content = f.read()

        # Clean up temp file
        os.unlink(tmp_file.name)

        # Save as downloadable file
        file_name = f"activation_codes_{project_code}_{frappe.utils.nowdate()}.csv"

        frappe.response.filename = file_name
        frappe.response.filecontent = content
        frappe.response.type = "download"

        log.info(f"Exported activation codes for project {project_code}")

    except Exception as e:
        log.error(f"Error exporting project activation codes: {str(e)}")
        frappe.throw(_(f"Error exporting activation codes: {str(e)}"))