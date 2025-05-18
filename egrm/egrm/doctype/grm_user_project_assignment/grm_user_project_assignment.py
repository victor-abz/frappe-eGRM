import frappe
from frappe import _
from frappe.model.document import Document
import logging

log = logging.getLogger(__name__)

class GRMUserProjectAssignment(Document):
    def validate(self):
        try:
            self.validate_user()
            self.validate_role()
            self.validate_department_and_region()
            self.validate_unique_assignment()
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