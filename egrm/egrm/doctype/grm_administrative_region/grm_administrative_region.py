import frappe
from frappe import _
from frappe.model.document import Document
import logging

log = logging.getLogger(__name__)

class GRMAdministrativeRegion(Document):
    def validate(self):
        try:
            self.validate_unique_admin_id_per_project()
            self.validate_parent_region()
            self.validate_coordinates()
            log.info(f"Validating GRM Administrative Region {self.name}")
        except Exception as e:
            log.error(f"Error validating GRM Administrative Region: {str(e)}")
            raise
            
    def validate_unique_admin_id_per_project(self):
        try:
            # Check for uniqueness of administrative_id within a project
            existing = frappe.db.exists(
                "GRM Administrative Region",
                {
                    "administrative_id": self.administrative_id,
                    "project": self.project,
                    "name": ["!=", self.name]
                }
            )
            
            if existing:
                frappe.throw(_("Administrative ID must be unique within a project"))
        except Exception as e:
            log.error(f"Error validating unique administrative ID: {str(e)}")
            raise
                
    def validate_parent_region(self):
        try:
            if self.parent_region and self.parent_region == self.name:
                frappe.throw(_("A region cannot be its own parent"))
                
            # Check for circular references
            if self.parent_region:
                self.check_circular_reference(self.parent_region, [self.name])
                
            # Check that parent region belongs to the same project
            if self.parent_region:
                parent_project = frappe.db.get_value("GRM Administrative Region", self.parent_region, "project")
                if parent_project != self.project:
                    frappe.throw(_("Parent region must belong to the same project"))
        except Exception as e:
            log.error(f"Error validating parent region: {str(e)}")
            raise
                
    def check_circular_reference(self, region, visited):
        try:
            parent = frappe.db.get_value("GRM Administrative Region", region, "parent_region")
            
            if not parent:
                return
                
            if parent in visited:
                frappe.throw(_("Circular reference detected in region hierarchy"))
                
            visited.append(parent)
            self.check_circular_reference(parent, visited)
        except Exception as e:
            log.error(f"Error checking for circular reference: {str(e)}")
            raise
            
    def validate_coordinates(self):
        try:
            if self.latitude and (self.latitude < -90 or self.latitude > 90):
                frappe.throw(_("Latitude must be between -90 and 90"))
                
            if self.longitude and (self.longitude < -180 or self.longitude > 180):
                frappe.throw(_("Longitude must be between -180 and 180"))
        except Exception as e:
            log.error(f"Error validating coordinates: {str(e)}")
            raise