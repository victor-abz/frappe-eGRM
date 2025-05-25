import frappe
from frappe import _
from frappe.model.document import Document
import logging

log = logging.getLogger(__name__)

class GRMAdministrativeRegion(Document):
    def validate(self):
        try:
            self.validate_parent_region()
            self.validate_coordinates()
            log.info(f"Validating GRM Administrative Region {self.name}")
        except Exception as e:
            log.error(f"Error validating GRM Administrative Region: {str(e)}")
            raise

    def before_save(self):
        try:
            # Generate materialized path if not already set
            if not self.path:
                self.path = self.generate_materialized_path()
            log.info(f"Setting materialized path for {self.region_name}: {self.path}")
        except Exception as e:
            log.error(f"Error in before_save: {str(e)}")
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
            # Parse geolocation if it exists
            if self.location:
                # Geolocation field should be in format: {"type": "FeatureCollection", "features": [...]}
                # Basic validation - more specific validation can be added
                import json
                try:
                    if isinstance(self.location, str):
                        location_data = json.loads(self.location)
                    else:
                        location_data = self.location

                    if not isinstance(location_data, dict):
                        frappe.throw(_("Invalid location data format"))

                except (json.JSONDecodeError, TypeError):
                    frappe.throw(_("Invalid location data format"))
        except Exception as e:
            log.error(f"Error validating coordinates: {str(e)}")
            raise

    def generate_materialized_path(self):
        """
        Generate materialized path for efficient hierarchy queries.
        Path format: "Country:Province:District:Sector:Cell"
        """
        try:
            if not self.parent_region:
                # This is a root region
                return self.region_name

            # Get parent's path
            parent_path = frappe.db.get_value("GRM Administrative Region", self.parent_region, "path")

            if not parent_path:
                # Parent doesn't have a path yet, generate it
                parent_doc = frappe.get_doc("GRM Administrative Region", self.parent_region)
                parent_path = parent_doc.generate_materialized_path()

                # Update parent's path
                frappe.db.set_value("GRM Administrative Region", self.parent_region, "path", parent_path)

            # Combine parent path with current region name
            return f"{parent_path}:{self.region_name}"

        except Exception as e:
            log.error(f"Error generating materialized path: {str(e)}")
            return self.region_name  # Fallback to just the region name

    def get_children(self):
        """
        Get all direct children of this region.
        """
        try:
            return frappe.get_all(
                "GRM Administrative Region",
                filters={
                    "parent_region": self.name,
                    "project": self.project
                },
                fields=["name", "region_name", "administrative_level", "path"]
            )
        except Exception as e:
            log.error(f"Error getting children: {str(e)}")
            return []

    def get_all_descendants(self):
        """
        Get all descendants (children, grandchildren, etc.) using materialized path.
        """
        try:
            if not self.path:
                return []

            return frappe.get_all(
                "GRM Administrative Region",
                filters={
                    "path": ["like", f"{self.path}:%"],
                    "project": self.project,
                    "name": ["!=", self.name]
                },
                fields=["name", "region_name", "administrative_level", "path"],
                order_by="path"
            )
        except Exception as e:
            log.error(f"Error getting descendants: {str(e)}")
            return []

    def get_ancestors(self):
        """
        Get all ancestors (parent, grandparent, etc.) using materialized path.
        """
        try:
            if not self.path or ":" not in self.path:
                return []  # Root region has no ancestors

            path_parts = self.path.split(":")
            ancestors = []

            # Build paths for each ancestor level
            for i in range(len(path_parts) - 1):
                ancestor_path = ":".join(path_parts[:i + 1])

                ancestor = frappe.get_all(
                    "GRM Administrative Region",
                    filters={
                        "path": ancestor_path,
                        "project": self.project
                    },
                    fields=["name", "region_name", "administrative_level", "path"],
                    limit=1
                )

                if ancestor:
                    ancestors.append(ancestor[0])

            return ancestors

        except Exception as e:
            log.error(f"Error getting ancestors: {str(e)}")
            return []

    def get_hierarchy_level(self):
        """
        Get the hierarchy level (depth) of this region.
        Root level = 0, children = 1, etc.
        """
        try:
            if not self.path:
                return 0
            return self.path.count(":")
        except Exception as e:
            log.error(f"Error getting hierarchy level: {str(e)}")
            return 0

    def is_ancestor_of(self, other_region_name):
        """
        Check if this region is an ancestor of another region.
        """
        try:
            other_path = frappe.db.get_value("GRM Administrative Region", other_region_name, "path")

            if not other_path or not self.path:
                return False

            return other_path.startswith(f"{self.path}:")

        except Exception as e:
            log.error(f"Error checking ancestor relationship: {str(e)}")
            return False

    def is_descendant_of(self, other_region_name):
        """
        Check if this region is a descendant of another region.
        """
        try:
            other_path = frappe.db.get_value("GRM Administrative Region", other_region_name, "path")

            if not other_path or not self.path:
                return False

            return self.path.startswith(f"{other_path}:")

        except Exception as e:
            log.error(f"Error checking descendant relationship: {str(e)}")
            return False


# Utility functions for working with administrative regions

def get_regions_by_level(project, level_name):
    """
    Get all regions at a specific administrative level for a project.
    """
    try:
        return frappe.get_all(
            "GRM Administrative Region",
            filters={
                "project": project,
                "administrative_level": level_name
            },
            fields=["name", "region_name", "path"],
            order_by="path"
        )
    except Exception as e:
        log.error(f"Error getting regions by level: {str(e)}")
        return []

def get_region_hierarchy_tree(project, root_region=None):
    """
    Get the complete hierarchy tree for a project.
    Returns a nested dictionary structure.
    """
    try:
        # Get all regions for the project
        filters = {"project": project}
        if root_region:
            root_path = frappe.db.get_value("GRM Administrative Region", root_region, "path")
            if root_path:
                filters["path"] = ["like", f"{root_path}%"]

        regions = frappe.get_all(
            "GRM Administrative Region",
            filters=filters,
            fields=["name", "region_name", "path", "parent_region", "administrative_level"],
            order_by="path"
        )

        # Build tree structure
        tree = {}
        for region in regions:
            path_parts = region.path.split(":") if region.path else [region.region_name]
            current_level = tree

            for part in path_parts:
                if part not in current_level:
                    current_level[part] = {"_data": None, "_children": {}}
                current_level = current_level[part]["_children"]

            # Store region data at the final level
            path_parts[-1] if path_parts else region.region_name
            if path_parts:
                final_part = path_parts[-1]
                if final_part in tree:
                    # Navigate to the correct position
                    current_level = tree
                    for part in path_parts[:-1]:
                        current_level = current_level[part]["_children"]
                    current_level[final_part]["_data"] = region

        return tree

    except Exception as e:
        log.error(f"Error building hierarchy tree: {str(e)}")
        return {}

def find_regions_by_name(project, region_name, exact_match=True):
    """
    Find regions by name within a project.
    """
    try:
        if exact_match:
            filters = {
                "project": project,
                "region_name": region_name
            }
        else:
            filters = {
                "project": project,
                "region_name": ["like", f"%{region_name}%"]
            }

        return frappe.get_all(
            "GRM Administrative Region",
            filters=filters,
            fields=["name", "region_name", "path", "administrative_level"],
            order_by="path"
        )

    except Exception as e:
        log.error(f"Error finding regions by name: {str(e)}")
        return []

def get_region_path_parts(region_name):
    """
    Get the path parts for a region as a list.
    """
    try:
        path = frappe.db.get_value("GRM Administrative Region", region_name, "path")
        if path:
            return path.split(":")
        return []
    except Exception as e:
        log.error(f"Error getting region path parts: {str(e)}")
        return []

def validate_region_hierarchy_integrity(project):
    """
    Validate the integrity of the region hierarchy for a project.
    Returns a list of issues found.
    """
    issues = []

    try:
        # Get all regions for the project
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": project},
            fields=["name", "region_name", "path", "parent_region"]
        )

        for region in regions:
            # Check if path matches parent-child relationship
            if region.parent_region:
                parent_path = frappe.db.get_value("GRM Administrative Region", region.parent_region, "path")
                expected_path = f"{parent_path}:{region.region_name}" if parent_path else region.region_name

                if region.path != expected_path:
                    issues.append({
                        "region": region.name,
                        "issue": "Path mismatch",
                        "expected": expected_path,
                        "actual": region.path
                    })

            # Check for orphaned regions (parent doesn't exist)
            if region.parent_region and not frappe.db.exists("GRM Administrative Region", region.parent_region):
                issues.append({
                    "region": region.name,
                    "issue": "Orphaned region - parent doesn't exist",
                    "parent": region.parent_region
                })

        return issues

    except Exception as e:
        log.error(f"Error validating hierarchy integrity: {str(e)}")
        return [{"error": str(e)}]

def repair_region_paths(project):
    """
    Repair materialized paths for all regions in a project.
    """
    try:
        # Get all regions ordered by hierarchy (root first)
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": project},
            fields=["name", "region_name", "parent_region"],
            order_by="ifnull(parent_region, '') asc"  # Root regions first
        )

        repaired = 0

        for region in regions:
            doc = frappe.get_doc("GRM Administrative Region", region.name)
            old_path = doc.path
            new_path = doc.generate_materialized_path()

            if old_path != new_path:
                doc.path = new_path
                doc.save()
                repaired += 1
                log.info(f"Repaired path for {region.region_name}: {old_path} -> {new_path}")

        return repaired

    except Exception as e:
        log.error(f"Error repairing region paths: {str(e)}")
        return 0