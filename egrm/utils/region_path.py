"""
EGRM Region Path Utilities
------------------------
This module contains utilities for optimizing queries on administrative region hierarchy.
"""

import frappe
import logging

# Configure logging
log = logging.getLogger(__name__)

def get_region_path(region_id):
    """
    Get materialized path for a region
    
    Args:
        region_id (str): Region ID
        
    Returns:
        str: Materialized path (e.g., "Country:State:District:Village")
    """
    try:
        # Get region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        
        # Build path
        path = region.administrative_id
        
        # Get parent regions recursively
        current_region = region
        while current_region.parent_region:
            parent = frappe.get_doc("GRM Administrative Region", current_region.parent_region)
            path = f"{parent.administrative_id}:{path}"
            current_region = parent
        
        return path
        
    except Exception as e:
        log.error(f"Error in get_region_path: {str(e)}")
        return ""

def update_region_path(region_id):
    """
    Update materialized path for a region and its children
    
    Args:
        region_id (str): Region ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get region path
        path = get_region_path(region_id)
        if not path:
            log.warning(f"Failed to get path for region {region_id}")
            return False
        
        # Update region path
        frappe.db.set_value("GRM Administrative Region", region_id, "path", path)
        
        # Update children paths
        update_children_paths(region_id, path)
        
        return True
        
    except Exception as e:
        log.error(f"Error in update_region_path: {str(e)}")
        return False

def update_children_paths(region_id, parent_path):
    """
    Update materialized paths for all children of a region
    
    Args:
        region_id (str): Region ID
        parent_path (str): Parent region's path
        
    Returns:
        None
    """
    try:
        # Get children
        children = frappe.get_all(
            "GRM Administrative Region",
            filters={"parent_region": region_id},
            fields=["name", "administrative_id"]
        )
        
        for child in children:
            # Build child path
            child_path = f"{parent_path}:{child.administrative_id}"
            
            # Update child path
            frappe.db.set_value("GRM Administrative Region", child.name, "path", child_path)
            
            # Recursively update grandchildren
            update_children_paths(child.name, child_path)
        
    except Exception as e:
        log.error(f"Error in update_children_paths: {str(e)}")

def find_regions_by_path_prefix(path_prefix):
    """
    Find regions by path prefix
    
    Args:
        path_prefix (str): Path prefix to match
        
    Returns:
        list: List of region IDs
    """
    try:
        # Use a LIKE query to find regions with matching path prefix
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"path": ["like", f"{path_prefix}%"]},
            fields=["name"]
        )
        
        return [r.name for r in regions]
        
    except Exception as e:
        log.error(f"Error in find_regions_by_path_prefix: {str(e)}")
        return []

def get_all_children(region_id):
    """
    Get all children (recursively) for a region using path prefix
    
    Args:
        region_id (str): Region ID
        
    Returns:
        list: List of region IDs
    """
    try:
        # Get region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        
        # Get region path
        path = region.path
        if not path:
            # Path not set, calculate it
            path = get_region_path(region_id)
            if not path:
                log.warning(f"Failed to get path for region {region_id}")
                return []
        
        # Find all regions with this path as prefix
        children = find_regions_by_path_prefix(path)
        
        # Remove self from the list
        if region_id in children:
            children.remove(region_id)
        
        return children
        
    except Exception as e:
        log.error(f"Error in get_all_children: {str(e)}")
        return []

def get_all_parents(region_id):
    """
    Get all parents for a region using path
    
    Args:
        region_id (str): Region ID
        
    Returns:
        list: List of region IDs
    """
    try:
        # Get region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        
        # Get region path
        path = region.path
        if not path:
            # Path not set, calculate it
            path = get_region_path(region_id)
            if not path:
                log.warning(f"Failed to get path for region {region_id}")
                return []
        
        # Split path into components
        components = path.split(":")
        
        # Remove last component (self)
        components.pop()
        
        if not components:
            return []
        
        # Find regions matching each path component
        parents = []
        current_path = ""
        
        for i, component in enumerate(components):
            if i == 0:
                current_path = component
            else:
                current_path = f"{current_path}:{component}"
            
            # Find region with exact path
            regions = frappe.get_all(
                "GRM Administrative Region",
                filters={"path": current_path},
                fields=["name"]
            )
            
            if regions:
                parents.append(regions[0].name)
        
        return parents
        
    except Exception as e:
        log.error(f"Error in get_all_parents: {str(e)}")
        return []

def belongs_to_region(child_id, parent_id):
    """
    Check if a region belongs to another region's hierarchy
    
    Args:
        child_id (str): Child region ID
        parent_id (str): Parent region ID
        
    Returns:
        bool: True if child belongs to parent, False otherwise
    """
    try:
        # Get child region
        child = frappe.get_doc("GRM Administrative Region", child_id)
        
        # Get parent region
        parent = frappe.get_doc("GRM Administrative Region", parent_id)
        
        # Get region paths
        child_path = child.path
        if not child_path:
            child_path = get_region_path(child_id)
        
        parent_path = parent.path
        if not parent_path:
            parent_path = get_region_path(parent_id)
        
        # Check if child path starts with parent path
        return child_path.startswith(f"{parent_path}:") or child_path == parent_path
        
    except Exception as e:
        log.error(f"Error in belongs_to_region: {str(e)}")
        return False

def update_all_region_paths():
    """
    Update materialized paths for all regions
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get all top-level regions (with no parent)
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"parent_region": ["is", "null"]},
            fields=["name", "administrative_id"]
        )
        
        # Update paths for each top-level region and its children
        for region in regions:
            # Set path for top-level region
            path = region.administrative_id
            frappe.db.set_value("GRM Administrative Region", region.name, "path", path)
            
            # Update children paths
            update_children_paths(region.name, path)
        
        return True
        
    except Exception as e:
        log.error(f"Error in update_all_region_paths: {str(e)}")
        return False
