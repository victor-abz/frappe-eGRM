import logging
import random
import secrets
import string
import zlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now, now_datetime

from egrm.utils.user_permissions import revoke_project_access, sync_assignment

log = logging.getLogger(__name__)


GOVERNMENT_WORKER_DUTIES: set[str] = {"Intake", "Investigate & Resolve"}


def _government_worker_role_names_for_project(project: str) -> list[str]:
    """Return Project Role names in `project` whose duty list intersects
    GOVERNMENT_WORKER_DUTIES. Used to scope activation-code exports to
    field-staff assignments under the duty-driven schema."""
    if not project:
        return []
    project_roles = frappe.get_all(
        "GRM Project Role",
        filters={"project": project, "is_active": 1},
        pluck="name",
    )
    if not project_roles:
        return []
    matching = frappe.get_all(
        "GRM Project Role Duty",
        filters={
            "parent": ["in", project_roles],
            "duty": ["in", list(GOVERNMENT_WORKER_DUTIES)],
        },
        pluck="parent",
    )
    return list(set(matching))


def _project_role_duties(project_role: str) -> list[str]:
    """Return the duty_name list for a Project Role; empty if missing."""
    if not project_role or not frappe.db.exists("GRM Project Role", project_role):
        return []
    return frappe.get_all(
        "GRM Project Role Duty",
        filters={"parent": project_role},
        pluck="duty",
    )


def _is_gov_worker_assignment(row) -> bool:
    """Does this assignment row require OTP activation?

    True when the Project Role carries an activation-gated duty AND the
    assignment is scoped to a region or department. Shared by the document
    method and the sibling lookup so both judge a row identically.
    """
    duties = set(_project_role_duties(row.get("role")))
    return bool(duties & GOVERNMENT_WORKER_DUTIES) and bool(
        row.get("administrative_region") or row.get("department")
    )


def _sibling_gov_worker_assignments(
    user: str, project: str, exclude_assignment: str | None = None
) -> list:
    """Active government-worker assignments for the same user and project.

    Activation is scoped to the (user, project) pair rather than to each
    assignment row. Since a user may hold one assignment per region, per-row
    activation would demand one OTP per region — and the activation API only
    ever resolves a single assignment per call, so the remaining rows could
    never be redeemed.
    """
    if not user or not project:
        return []
    filters = {"user": user, "project": project, "is_active": 1}
    if exclude_assignment:
        filters["name"] = ["!=", exclude_assignment]
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters=filters,
        fields=[
            "name",
            "role",
            "administrative_region",
            "department",
            "activation_status",
            "activation_code",
            "activation_expires_on",
        ],
        ignore_permissions=True,
    )
    return [row for row in rows if _is_gov_worker_assignment(row)]


def _frappe_role_for_duty(duty_name: str) -> str:
    """Convention: the Frappe Role corresponding to duty X is named 'GRM X'."""
    return f"GRM {duty_name}"


def _other_active_assignments_grant_duty(
    user: str, duty: str, exclude_assignment: str | None = None
) -> bool:
    """Does the user hold this duty via ANY other active assignment?"""
    filters = {
        "user": user,
        "is_active": 1,
        "activation_status": ["in", ("Activated", "")],
    }
    if exclude_assignment:
        filters["name"] = ["!=", exclude_assignment]
    other_assignments = frappe.get_all(
        "GRM User Project Assignment",
        filters=filters,
        pluck="role",
    )
    for project_role in other_assignments:
        if duty in _project_role_duties(project_role):
            return True
    return False


class GRMUserProjectAssignment(Document):
    def validate(self):
        try:
            self.validate_creator_permissions()
            self.validate_user()
            self.validate_role()
            self.validate_department_and_region()
            self.validate_unique_assignment()
            self.validate_activation_status()
            frappe.log(f"Validating GRM User Project Assignment {self.name}")
        except Exception as e:
            frappe.log_error(f"Error validating GRM User Project Assignment: {str(e)}")
            raise

    def validate_creator_permissions(self):
        """Block PM-tier users from assigning users to projects they don't manage.

        - Administrator / System Manager / GRM Platform Administrator: unrestricted.
        - Anyone else: must hold an active assignment for THIS project whose
          Project Role includes the Supervise duty.
        """
        user = frappe.session.user
        if user in ("Administrator", "Guest"):
            return
        creator_roles = set(frappe.get_roles(user))
        if creator_roles & {"System Manager", "GRM Platform Administrator"}:
            return

        # Look for any active assignment whose Project Role includes 'Supervise'
        # for the same project the new assignment targets.
        my_assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters={
                "user": user,
                "project": self.project,
                "is_active": 1,
                "activation_status": ["in", ("Activated", "")],
            },
            pluck="role",
        )
        for project_role in my_assignments:
            if frappe.db.exists(
                "GRM Project Role Duty",
                {"parent": project_role, "duty": "Supervise"},
            ):
                return

        frappe.throw(
            frappe._(
                "You can only assign users to projects where you hold a Supervise duty."
            ),
            frappe.PermissionError,
        )

    def validate_user(self):
        try:
            # Check if the user exists
            if not frappe.db.exists("User", self.user):
                frappe.throw(_("User {0} does not exist").format(self.user))

            # Check if the user is enabled
            if frappe.db.get_value("User", self.user, "enabled") != 1:
                frappe.throw(_("User {0} is not enabled").format(self.user))
        except Exception as e:
            frappe.log_error(f"Error validating user: {str(e)}")
            raise

    def validate_role(self):
        """Ensure ``role`` points to an active Project Role for this project.

        Under the duty-driven schema (post-migration), ``role`` is a Link to
        ``GRM Project Role`` whose names are project-scoped (e.g.
        ``RDAP-District GRM Officer``). The Frappe Link constraint already
        enforces the row exists; here we additionally:

          - Require the role belongs to the same project as the assignment
            (prevents cross-project role pollution).
          - Require the role is active (``is_active = 1``).
        """
        try:
            if not self.role:
                frappe.throw(_("Project Role is required"))

            if not frappe.db.exists("GRM Project Role", self.role):
                frappe.throw(
                    _("Project Role {0} does not exist").format(self.role)
                )

            role_project, role_active = frappe.db.get_value(
                "GRM Project Role", self.role, ["project", "is_active"]
            )
            if role_project != self.project:
                frappe.throw(
                    _(
                        "Project Role {0} belongs to project {1}, not {2}"
                    ).format(self.role, role_project, self.project)
                )
            if not role_active:
                frappe.throw(
                    _("Project Role {0} is not active").format(self.role)
                )
        except Exception as e:
            frappe.log_error(f"Error validating role: {str(e)}")
            raise

    def validate_department_and_region(self):
        """Cross-doctype consistency for ``department`` / ``administrative_region``.

        Two responsibilities:

        1. **Duty-aware requirement** — if the project role's duties include
           any government-worker duty (``Intake``, ``Investigate & Resolve``),
           the assignment must be scoped to a region OR a department.

        2. **Project-scope consistency** — the department (if set) must be
           linked to the project via ``GRM Project Link``, and the region
           (if set) must belong to the same project.
        """
        try:
            duties = set(_project_role_duties(self.role))
            if duties & GOVERNMENT_WORKER_DUTIES and not (
                self.administrative_region or self.department
            ):
                frappe.throw(
                    _(
                        "A government-worker assignment (duties: Intake / "
                        "Investigate & Resolve) requires either an "
                        "administrative region or a department."
                    )
                )

            if self.department:
                dept_linked_to_project = frappe.db.exists(
                    "GRM Project Link",
                    {"parent": self.department, "project": self.project},
                )
                if not dept_linked_to_project:
                    frappe.throw(
                        _("Department {0} is not linked to project {1}").format(
                            self.department, self.project
                        )
                    )

            if self.administrative_region:
                region_belongs_to_project = (
                    frappe.db.get_value(
                        "GRM Administrative Region",
                        self.administrative_region,
                        "project",
                    )
                    == self.project
                )
                if not region_belongs_to_project:
                    frappe.throw(
                        _(
                            "Administrative Region {0} does not belong to project {1}"
                        ).format(self.administrative_region, self.project)
                    )
        except Exception as e:
            frappe.log_error(f"Error validating department and region: {str(e)}")
            raise

    def validate_unique_assignment(self):
        try:
            # A user may hold the same role in multiple regions, but not the
            # same (project, role, region) twice — region is part of the key.
            existing = frappe.db.exists(
                "GRM User Project Assignment",
                {
                    "user": self.user,
                    "project": self.project,
                    "role": self.role,
                    "administrative_region": self.administrative_region,
                    "name": ["!=", self.name],
                },
            )

            if existing:
                frappe.throw(
                    _(
                        "User {0} is already assigned to project {1} with role {2} in region {3}"
                    ).format(
                        self.user,
                        self.project,
                        self.role,
                        self.administrative_region or _("(no region)"),
                    )
                )
        except Exception as e:
            frappe.log_error(f"Error validating unique assignment: {str(e)}")
            raise

    def assign_role_to_user(self) -> None:
        """Grant each Frappe duty-role mapped to this assignment's Project Role."""
        duties = _project_role_duties(self.role)
        if not duties:
            return
        user = frappe.get_doc("User", self.user)
        existing = {r.role for r in user.roles}
        changed = False
        for duty in duties:
            target = _frappe_role_for_duty(duty)
            if target not in existing and frappe.db.exists("Role", target):
                user.append("roles", {"role": target})
                changed = True
        if changed:
            user.flags.ignore_permissions = True
            user.save()

    def remove_role_from_user(self) -> None:
        """Strip duty-roles granted by this assignment, but only those no
        other active assignment of the same user still requires."""
        duties = _project_role_duties(self.role)
        if not duties:
            return
        user = frappe.get_doc("User", self.user)
        my_duty_roles = {_frappe_role_for_duty(d) for d in duties}
        kept_rows = []
        any_removed = False
        for role_row in user.roles:
            if role_row.role not in my_duty_roles:
                kept_rows.append(role_row)
                continue
            duty_name = role_row.role.removeprefix("GRM ")
            if _other_active_assignments_grant_duty(self.user, duty_name, exclude_assignment=self.name):
                kept_rows.append(role_row)
            else:
                any_removed = True
        if any_removed:
            user.set("roles", [{"role": k.role} for k in kept_rows])
            user.flags.ignore_permissions = True
            user.save()

    def handle_role_change(self, old_role):
        """Handle role updates when assignment is modified"""
        try:
            if old_role != self.role:
                # Remove old role if safe (no other active assignments use it)
                temp_role = self.role
                self.role = old_role
                self.remove_role_from_user()
                self.role = temp_role

                # Add new role if assignment is active and activated
                if self.is_active and self.activation_status == "Activated":
                    self.assign_role_to_user()

                frappe.log(f"Changed role from {old_role} to {self.role} for user {self.user}")
        except Exception as e:
            frappe.log_error(f"Error handling role change: {str(e)}")
            raise

    def on_update(self):
        """Handle role changes and is_active toggles"""
        try:
            # Get the old document from DB to compare changes
            if self.is_new():
                return

            old_doc = self.get_doc_before_save()
            if not old_doc:
                return

            # Handle role change
            if old_doc.role != self.role:
                self.handle_role_change(old_doc.role)

            # Handle is_active toggle
            if old_doc.is_active != self.is_active:
                if self.is_active and self.activation_status == "Activated":
                    # Reactivated - assign role
                    self.assign_role_to_user()
                    frappe.log(f"Reactivated assignment - assigned role {self.role} to user {self.user}")
                elif not self.is_active:
                    # Deactivated - remove role
                    self.remove_role_from_user()
                    frappe.log(f"Deactivated assignment - removed role {self.role} from user {self.user}")

            # Handle activation status change
            if old_doc.activation_status != self.activation_status:
                if self.activation_status == "Activated" and self.is_active:
                    # Just got activated - assign role
                    self.assign_role_to_user()
                    frappe.log(f"Worker activated - assigned role {self.role} to user {self.user}")
                elif old_doc.activation_status == "Activated" and self.activation_status != "Activated":
                    # Lost activation - remove role
                    self.remove_role_from_user()
                    frappe.log(f"Worker deactivated - removed role {self.role} from user {self.user}")

            # IMPORTANT: Ensure role is assigned if user is active and activated
            # This handles existing assignments created before this feature was added
            if self.is_active and self.activation_status == "Activated":
                # Check if user actually has the role
                user_doc = frappe.get_doc("User", self.user)
                existing_roles = [d.role for d in user_doc.roles]
                if self.role not in existing_roles:
                    frappe.log(f"Assigning missing role {self.role} to user {self.user} (migration fix)")
                    self.assign_role_to_user()

            sync_assignment(self)

        except Exception as e:
            frappe.log_error(f"Error in on_update: {str(e)}")
            raise

    def after_insert(self):
        """Assign role to user after creating assignment"""
        try:
            # For non-government workers, activate immediately and assign role
            if not self.is_government_worker_role():
                self.assign_role_to_user()
                frappe.log(f"Assigned role {self.role} to non-government worker {self.user}")
            sync_assignment(self)
        except Exception as e:
            frappe.log_error(f"Error in after_insert: {str(e)}")
            raise
        # try:
        #     # Get user's existing permissions
        #     from frappe.permissions import add_user_permission, get_user_permissions

        #     user_permissions = get_user_permissions(self.user)

        #     # Add project permission to the user if not exists
        #     has_project_permission = any(
        #         perm.get("allow") == "GRM Project"
        #         and perm.get("for_value") == self.project
        #         for perm in user_permissions
        #     )
        #     if not has_project_permission:
        #         add_user_permission("GRM Project", self.project, self.user)
        #         frappe.log(
        #             f"Added project permission {self.project} to user {self.user}"
        #         )
        #     else:
        #         frappe.log(
        #             f"User {self.user} already has project permission for {self.project}"
        #         )

        #     # Add department permission if applicable and not exists
        #     if self.department:
        #         has_department_permission = any(
        #             perm.get("allow") == "GRM Issue Department"
        #             and perm.get("for_value") == self.department
        #             for perm in user_permissions
        #         )
        #         if not has_department_permission:
        #             add_user_permission(
        #                 "GRM Issue Department", self.department, self.user
        #             )
        #             frappe.log(
        #                 f"Added department permission {self.department} to user {self.user}"
        #             )
        #         else:
        #             frappe.log(
        #                 f"User {self.user} already has department permission for {self.department}"
        #             )

        #     # Add region permission if applicable and not exists
        #     if self.administrative_region:
        #         has_region_permission = any(
        #             perm.get("allow") == "GRM Administrative Region"
        #             and perm.get("for_value") == self.administrative_region
        #             for perm in user_permissions
        #         )
        #         if not has_region_permission:
        #             add_user_permission(
        #                 "GRM Administrative Region",
        #                 self.administrative_region,
        #                 self.user,
        #             )
        #             frappe.log(
        #                 f"Added region permission {self.administrative_region} to user {self.user}"
        #             )
        #         else:
        #             frappe.log(
        #                 f"User {self.user} already has region permission for {self.administrative_region}"
        #             )

        #     frappe.log(
        #         f"Permissions setup completed for user {self.user} for project {self.project}"
        #     )
        # except Exception as e:
        #     frappe.log_error(f"Error setting up permissions: {str(e)}")
        #     frappe.throw(_("Error setting up permissions. Please check the logs."))

    def on_trash(self):
        try:
            # Remove role from user if no other active assignments use it
            self.remove_role_from_user()

            frappe.log(
                f"Removed assignment for user {self.user} for project {self.project}"
            )
            revoke_project_access(self.user, self.project, exclude_assignment=self.name)
        except Exception as e:
            frappe.log_error(f"Error removing assignment: {str(e)}")
            frappe.throw(_("Error removing assignment. Please check the logs."))

    def before_insert(self):
        """Set the activation state for a newly created assignment.

        Government-worker assignments activate once per (user, project), not
        once per row: a user assigned to five regions inherits whatever
        activation state the project already established for them rather than
        minting a fifth independent code.
        """
        try:
            if not self.is_government_worker_role():
                # For non-government workers, set as activated
                self.activation_status = "Activated"
                self.activated_on = now()
                frappe.log(f"Non-government worker {self.user} automatically activated")
                return

            if self.inherit_project_activation():
                return

            # First government-worker assignment on this project for the user.
            if not self.activation_code:
                self.generate_activation_code()
                # Set status to Pending Activation immediately when code is generated
                self.activation_status = "Pending Activation"
                frappe.log(
                    f"Generated activation code for government worker {self.user}"
                )
            elif not self.activation_status:
                # If code exists but no status, set to Pending Activation
                self.activation_status = "Pending Activation"

        except Exception as e:
            frappe.log_error(f"Error in before_insert: {str(e)}")
            raise

    def inherit_project_activation(self) -> bool:
        """Adopt the activation state already held for this user and project.

        Returns True when state was inherited, meaning this row must not
        generate an activation code of its own.
        """
        siblings = _sibling_gov_worker_assignments(self.user, self.project)
        if not siblings:
            return False

        if any(s.activation_status == "Activated" for s in siblings):
            # The user already proved ownership of this account on this
            # project; adding a region does not warrant a second OTP.
            self.activation_status = "Activated"
            self.activated_on = now()
            self.activation_code = None
            self.activation_expires_on = None
            frappe.log(
                f"Inherited activated state for {self.user} on {self.project}"
            )
            return True

        if any(s.activation_status == "Suspended" for s in siblings):
            # Suspension is an account-level state for the project. Issuing a
            # fresh code on a new region would sidestep it.
            self.activation_status = "Suspended"
            frappe.log(
                f"Inherited suspended state for {self.user} on {self.project}"
            )
            return True

        live = next(
            (
                s
                for s in siblings
                if s.activation_status == "Pending Activation"
                and s.activation_code
                and s.activation_expires_on
                and get_datetime(s.activation_expires_on) > now_datetime()
            ),
            None,
        )
        if live:
            # Share the one outstanding code so the user redeems a single OTP.
            self.activation_code = live.activation_code
            self.activation_expires_on = live.activation_expires_on
            self.activation_status = "Pending Activation"
            frappe.log(
                f"Reused pending activation code for {self.user} on {self.project}"
            )
            return True

        return False

    def is_government_worker_role(self) -> bool:
        """An assignment is "government worker" (needs activation) if any of
        its Project Role duties is in the activation-required set AND the
        assignment has a region or department to scope to."""
        return _is_gov_worker_assignment(
            {
                "role": self.role,
                "administrative_region": getattr(self, "administrative_region", None),
                "department": getattr(self, "department", None),
            }
        )

    def generate_activation_code(self):
        """Generate a cryptographically-secure 6-digit activation code.

        The previous implementation used ``zlib.adler32(email|name|now)`` —
        a non-cryptographic checksum with low entropy, easily predictable
        given the seed shape. Switched to ``secrets.randbelow`` per
        review fix A2.
        """
        try:
            # Validate user has an email (still required so the code can be
            # delivered downstream by ``send_activation_email``).
            user_email = frappe.db.get_value("User", self.user, "email")
            if not user_email:
                frappe.throw(_("User email is required for activation code generation"))

            # CSPRNG-backed 6-digit code (zero-padded; 1 in 10**6 collision
            # space — fine given the rate-limited /activate endpoint and
            # 48 h TTL).
            self.activation_code = f"{secrets.randbelow(10**6):06d}"

            # Set expiration (48 hours from now)
            self.activation_expires_on = add_to_date(now(), hours=48)

            frappe.log(f"Generated activation code for {user_email}")

        except Exception as e:
            frappe.log_error(f"Error generating activation code: {str(e)}")
            raise

    def send_activation_email(self):
        """Send email with activation code"""
        try:
            if not self.activation_code:
                frappe.throw(
                    _("No activation code found. Please generate a code first.")
                )

            user_email = frappe.db.get_value("User", self.user, "email")
            user_full_name = frappe.db.get_value("User", self.user, "full_name")

            if not user_email:
                frappe.throw(_("User email is required to send activation code"))

            # Prepare email content
            subject = _("GRM System - Government Worker Activation Code")

            # Use email template if exists, otherwise use basic template
            try:
                template = frappe.get_doc(
                    "Email Template", "GRM Government Worker Activation"
                )
                message = frappe.render_template(
                    template.response,
                    {
                        "user_name": user_full_name or self.user,
                        "activation_code": self.activation_code,
                        "position_title": self.position_title or "Government Worker",
                        "expiry_date": self.activation_expires_on,
                        "project_name": frappe.db.get_value(
                            "GRM Project", self.project, "title"
                        ),
                    },
                )
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
                reference_name=self.name,
            )

            # Update tracking fields
            self.code_sent_on = now()
            # Only set to Pending Activation if not already set
            if not self.activation_status or self.activation_status == "Draft":
                self.activation_status = "Pending Activation"

            frappe.log(f"Activation email sent to {user_email}")
            return True

        except Exception as e:
            frappe.log_error(f"Error sending activation email: {str(e)}")
            frappe.throw(_("Error sending activation email: {0}").format(str(e)))

    @frappe.whitelist()
    def activate_worker(self, activation_code, new_password=None):
        """Validate and activate worker"""
        try:
            # Validate current status
            if self.activation_status == "Activated":
                frappe.throw(_("Worker is already activated"))

            if self.activation_status == "Expired":
                frappe.throw(
                    _("Activation code has expired. Please request a new code.")
                )

            if self.activation_status == "Suspended":
                frappe.throw(_("Account is suspended. Please contact administrator."))

            # Check expiration
            if (
                self.activation_expires_on
                and get_datetime(self.activation_expires_on) < now_datetime()
            ):
                self.activation_status = "Expired"
                self.save()
                frappe.throw(
                    _("Activation code has expired. Please request a new code.")
                )

            # Check attempt limits
            if self.activation_attempts >= 5:
                self.activation_status = "Suspended"
                self.save()
                frappe.throw(_("Too many failed attempts. Account has been suspended."))

            # Validate activation code
            if self.activation_code != activation_code:
                self.activation_attempts += 1
                self.save()
                frappe.throw(
                    _(
                        f"Invalid activation code. Attempts remaining: {5 - self.activation_attempts}"
                    )
                )

            # Activate the worker
            self.activation_status = "Activated"
            self.activated_on = now()
            self.activation_attempts = 0  # Reset attempts on successful activation

            # Update user password if provided. Activation is a Guest-callable
            # flow (the activation code itself is the auth token), so bypass
            # User doctype's role-based write permission.
            if new_password:
                user_doc = frappe.get_doc("User", self.user)
                user_doc.new_password = new_password
                user_doc.flags.ignore_permissions = True
                user_doc.save(ignore_permissions=True)

            self.save()

            cascaded = self.cascade_activation()

            frappe.log(
                f"Government worker {self.user} activated successfully "
                f"({len(cascaded) + 1} assignment(s) on {self.project})"
            )
            return True

        except Exception as e:
            frappe.log_error(f"Error activating worker: {str(e)}")
            raise

    def cascade_activation(self) -> list[str]:
        """Activate the user's other assignments on this same project.

        One OTP exchange covers the whole (user, project) pair. Without this
        a multi-region user would be left with rows the activation API can
        never reach, since it resolves exactly one assignment per call — and
        every project-scoped query (mobile sync, region lookup, issue
        filtering) requires ``activation_status = 'Activated'``.

        Returns the names of the assignments that were activated.
        """
        activated: list[str] = []
        for sibling in _sibling_gov_worker_assignments(
            self.user, self.project, exclude_assignment=self.name
        ):
            if sibling.activation_status in ("Activated", "Suspended"):
                continue
            try:
                doc = frappe.get_doc("GRM User Project Assignment", sibling.name)
                doc.activation_status = "Activated"
                doc.activated_on = now()
                doc.activation_attempts = 0
                doc.flags.ignore_permissions = True
                doc.save(ignore_permissions=True)
                activated.append(sibling.name)
            except Exception as e:
                # A failed sibling must not roll back the activation the user
                # just completed; log and continue.
                frappe.log_error(
                    f"Error cascading activation to {sibling.name}: {str(e)}"
                )
        return activated

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

            self.propagate_activation_code()

            frappe.log(f"Activation code resent for {self.user}")
            return True

        except Exception as e:
            frappe.log_error(f"Error resending activation code: {str(e)}")
            raise

    def propagate_activation_code(self) -> list[str]:
        """Copy this row's code and expiry onto the user's other pending
        assignments for the same project.

        The activation API resolves whichever pending assignment it finds
        first, so leaving siblings on a stale code would make the freshly
        emailed code fail validation. Keeping one live code per
        (user, project) keeps any resolved row redeemable.

        Returns the names of the assignments that were updated.
        """
        updated: list[str] = []
        for sibling in _sibling_gov_worker_assignments(
            self.user, self.project, exclude_assignment=self.name
        ):
            if sibling.activation_status in ("Activated", "Suspended"):
                continue
            try:
                doc = frappe.get_doc("GRM User Project Assignment", sibling.name)
                doc.activation_code = self.activation_code
                doc.activation_expires_on = self.activation_expires_on
                doc.activation_status = "Pending Activation"
                doc.activation_attempts = 0
                doc.flags.ignore_permissions = True
                doc.save(ignore_permissions=True)
                updated.append(sibling.name)
            except Exception as e:
                frappe.log_error(
                    f"Error propagating activation code to {sibling.name}: {str(e)}"
                )
        return updated

    def expire_activation_code(self):
        """Mark code as expired"""
        try:
            self.activation_status = "Expired"
            self.save()

            frappe.log(f"Activation code expired for {self.user}")
            return True

        except Exception as e:
            frappe.log_error(f"Error expiring activation code: {str(e)}")
            raise

    def validate_activation_status(self):
        """Check code expiration and attempt limits"""
        try:
            # Auto-expire codes if past expiration
            if (
                self.activation_status == "Pending Activation"
                and self.activation_expires_on
                and get_datetime(self.activation_expires_on) < now_datetime()
            ):
                self.activation_status = "Expired"
                frappe.log(f"Auto-expired activation code for {self.user}")

            # Check attempt limits
            if self.activation_attempts >= 5 and self.activation_status not in [
                "Activated",
                "Suspended",
            ]:
                self.activation_status = "Suspended"
                frappe.log(
                    f"Auto-suspended account for {self.user} due to too many failed attempts"
                )

        except Exception as e:
            frappe.log_error(f"Error validating activation status: {str(e)}")
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
            government_worker_roles = _government_worker_role_names_for_project(
                self.project
            )
            if government_worker_roles:
                assignments = frappe.get_all(
                    "GRM User Project Assignment",
                    filters={
                        "project": self.project,
                        "role": ["in", government_worker_roles],
                    },
                    fields=[
                        "user",
                        "activation_code",
                        "activation_status",
                        "position_title",
                        "administrative_region",
                        "department",
                        "activation_expires_on",
                    ],
                )
            else:
                assignments = []

            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers
            writer.writerow(
                [
                    "Email",
                    "Activation_Code",
                    "Status",
                    "Position",
                    "Region",
                    "Department",
                    "Expires_On",
                ]
            )

            # Write data
            for assignment in assignments:
                user_email = frappe.db.get_value("User", assignment.user, "email")
                region_name = ""
                if assignment.administrative_region:
                    region_name = frappe.db.get_value(
                        "GRM Administrative Region",
                        assignment.administrative_region,
                        "region_name",
                    )

                department_name = ""
                if assignment.department:
                    department_name = frappe.db.get_value(
                        "GRM Issue Department", assignment.department, "department_name"
                    )

                writer.writerow(
                    [
                        user_email or "",
                        assignment.activation_code or "",
                        assignment.activation_status or "",
                        assignment.position_title or "",
                        region_name,
                        department_name,
                        assignment.activation_expires_on or "",
                    ]
                )

            csv_content = output.getvalue()
            output.close()

            frappe.log(f"Exported activation codes for project {self.project}")
            return csv_content

        except Exception as e:
            frappe.log_error(f"Error exporting activation codes: {str(e)}")
            frappe.throw(_("Error exporting activation codes: {0}").format(str(e)))


# Static method for bulk export
@frappe.whitelist()
def export_project_activation_codes(project_code):
    """Export activation codes for a specific project"""
    try:
        # Check permissions
        if not frappe.has_permission("GRM User Project Assignment", "export"):
            frappe.throw(_("No permission to export activation codes"))

        import csv
        import os
        import tempfile

        from frappe.utils.file_manager import save_file

        # Get all government worker assignments for this project
        government_worker_roles = _government_worker_role_names_for_project(
            project_code
        )
        if not government_worker_roles:
            frappe.throw(_("No government worker roles configured for this project"))
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            filters={
                "project": project_code,
                "role": ["in", government_worker_roles],
            },
            fields=[
                "user",
                "activation_code",
                "activation_status",
                "position_title",
                "administrative_region",
                "department",
                "activation_expires_on",
            ],
        )

        if not assignments:
            frappe.throw(_("No government worker assignments found for this project"))

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            writer = csv.writer(tmp_file)

            # Write headers
            writer.writerow(
                [
                    "Email",
                    "Activation_Code",
                    "Status",
                    "Position",
                    "Region",
                    "Department",
                    "Expires_On",
                ]
            )

            # Write data
            for assignment in assignments:
                user_email = frappe.db.get_value("User", assignment.user, "email")
                region_name = ""
                if assignment.administrative_region:
                    region_name = frappe.db.get_value(
                        "GRM Administrative Region",
                        assignment.administrative_region,
                        "region_name",
                    )

                department_name = ""
                if assignment.department:
                    department_name = frappe.db.get_value(
                        "GRM Issue Department", assignment.department, "department_name"
                    )

                writer.writerow(
                    [
                        user_email or "",
                        assignment.activation_code or "",
                        assignment.activation_status or "",
                        assignment.position_title or "",
                        region_name,
                        department_name,
                        assignment.activation_expires_on or "",
                    ]
                )

        # Read file content and create download
        with open(tmp_file.name, "r") as f:
            content = f.read()

        # Clean up temp file
        os.unlink(tmp_file.name)

        # Save as downloadable file
        file_name = f"activation_codes_{project_code}_{frappe.utils.nowdate()}.csv"

        frappe.response.filename = file_name
        frappe.response.filecontent = content
        frappe.response.type = "download"

        frappe.log(f"Exported activation codes for project {project_code}")

    except Exception as e:
        frappe.log_error(f"Error exporting project activation codes: {str(e)}")
        frappe.throw(_("Error exporting activation codes: {0}").format(str(e)))


@frappe.whitelist()
def get_grm_roles(doctype, txt, searchfield, start, page_len, filters):
    """Return only GRM-specific roles for the role field dropdown"""
    return frappe.db.sql("""
        SELECT name
        FROM `tabRole`
        WHERE name LIKE 'GRM%%'
        AND (name LIKE %(txt)s OR %(txt)s = '')
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """, {
        'txt': f'%{txt}%',
        'start': start,
        'page_len': page_len
    })


@frappe.whitelist()
def role_query(doctype, txt, searchfield, start, page_len, filters):
    """Filter Project Role suggestions to roles in the selected project.

    Used by the GRM User Project Assignment.role field's get_query
    callback. Restricts visible Project Roles to the project the form is
    currently bound to and to active roles only.
    """
    if not frappe.has_permission("GRM Project Role", "read"):
        return []

    # Filters may arrive as a JSON string when called over HTTP.
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    project = (filters or {}).get("project")
    if not project:
        return []

    # Whitelist searchfield to prevent SQL injection — only allow columns
    # we expect Frappe's link picker to query against.
    allowed_searchfields = {"name", "role_name"}
    safe_searchfield = searchfield if searchfield in allowed_searchfields else "name"

    return frappe.db.sql(
        f"""SELECT name, role_name FROM `tabGRM Project Role`
            WHERE project = %s AND is_active = 1
              AND ({safe_searchfield} LIKE %s OR role_name LIKE %s)
            ORDER BY role_name LIMIT %s, %s""",
        (project, f"%{txt}%", f"%{txt}%", start, page_len),
    )


def get_user_assignments(user):
    """
    Get user's region assignments from GRM User Project Assignment
    Automatically gets all active assignments for the user across all projects

    Args:
        user (str): User email (from session)

    Returns:
        list: List of user assignments with region details
    """
    try:
        # Build filters for user assignments - get all active assignments
        assignment_filters = {
            "user": user,
            "is_active": 1,
            "activation_status": "Activated",
        }

        # Get user assignments that have administrative regions
        assignments = frappe.get_all(
            "GRM User Project Assignment",
            fields=[
                "name",
                "user",
                "project",
                "role",
                "administrative_region",
                "department",
            ],
            filters=assignment_filters,
        )

        # Filter out assignments without regions
        region_assignments = [a for a in assignments if a.administrative_region]

        frappe.log(
            f"Found {len(region_assignments)} region assignments for user {user}"
        )

        # Log the projects and regions for debugging
        projects = list(set([a.project for a in region_assignments]))
        regions = list(set([a.administrative_region for a in region_assignments]))
        frappe.log(f"User {user} has access to projects: {projects}")
        frappe.log(f"User {user} is assigned to regions: {regions}")

        return projects, regions

    except Exception as e:
        frappe.log_error(f"Error getting user region assignments: {str(e)}")
        return []
