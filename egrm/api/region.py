"""
EGRM API - Administrative Region Endpoints
----------------------------------------
This module contains API endpoints for managing administrative regions.
"""

import frappe
import json
import logging
from frappe import _
from frappe.utils import cint

# Configure logging
log = logging.getLogger(__name__)

@frappe.whitelist()
def list(project_id=None):
    """
    List administrative regions for a project
    
    Args:
        project_id (str, optional): Project ID
        
    Returns:
        dict: List of regions
    """
    try:
        user = frappe.session.user
        log.info(f"Listing regions for project {project_id} by user: {user}")
        
        # Check if project exists
        if project_id and not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if project_id and not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get regions
        filters = {}
        if project_id:
            filters["project"] = project_id
            
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters=filters,
            fields=[
                "name", "region_name", "administrative_id", "administrative_level", 
                "parent_region", "latitude", "longitude", "project"
            ]
        )
        
        # Enhance region data
        for region in regions:
            # Get level name
            if region.administrative_level:
                level_doc = frappe.get_doc("GRM Administrative Level Type", region.administrative_level)
                region.level_name = level_doc.level_name
            
            # Get parent region name
            if region.parent_region:
                parent_doc = frappe.get_doc("GRM Administrative Region", region.parent_region)
                region.parent_name = parent_doc.region_name
            
            # Get project name
            if region.project:
                project_doc = frappe.get_doc("GRM Project", region.project)
                region.project_name = project_doc.project_name
        
        log.info(f"Returning {len(regions)} regions")
        return {"status": "success", "data": regions}
        
    except Exception as e:
        log.error(f"Error in list_regions: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def hierarchy(region_id):
    """
    Get hierarchy for a region
    
    Args:
        region_id (str): Region ID
        
    Returns:
        dict: Region hierarchy
    """
    try:
        user = frappe.session.user
        log.info(f"Getting hierarchy for region {region_id} by user: {user}")
        
        # Check if region exists
        if not frappe.db.exists("GRM Administrative Region", region_id):
            log.warning(f"Region {region_id} not found")
            return {"status": "error", "message": _("Region not found")}
        
        # Check if user has permission to read the region
        if not frappe.has_permission("GRM Administrative Region", "read", region_id):
            log.warning(f"User {user} does not have permission to read region {region_id}")
            return {"status": "error", "message": _("You do not have permission to access this region")}
        
        # Get region
        region = frappe.get_doc("GRM Administrative Region", region_id)
        
        # Check if user has permission to read the project
        if not frappe.has_permission("GRM Project", "read", region.project):
            log.warning(f"User {user} does not have permission to read project {region.project}")
            return {"status": "error", "message": _("You do not have permission to access this region's project")}
        
        # Get hierarchy (parents)
        parents = get_region_parents(region_id)
        
        # Get children
        children = get_region_children(region_id)
        
        log.info(f"Returning hierarchy for region {region_id}")
        return {
            "status": "success", 
            "data": {
                "region": {
                    "id": region.name,
                    "name": region.region_name,
                    "level": region.administrative_level,
                    "project": region.project
                },
                "parents": parents,
                "children": children
            }
        }
        
    except Exception as e:
        log.error(f"Error in get_hierarchy: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def children(region_id):
    """
    Get children for a region
    
    Args:
        region_id (str): Region ID
        
    Returns:
        dict: Region children
    """
    try:
        user = frappe.session.user
        log.info(f"Getting children for region {region_id} by user: {user}")
        
        # Check if region exists
        if not frappe.db.exists("GRM Administrative Region", region_id):
            log.warning(f"Region {region_id} not found")
            return {"status": "error", "message": _("Region not found")}
        
        # Check if user has permission to read the region
        if not frappe.has_permission("GRM Administrative Region", "read", region_id):
            log.warning(f"User {user} does not have permission to read region {region_id}")
            return {"status": "error", "message": _("You do not have permission to access this region")}
        
        # Get children
        children = get_region_children(region_id)
        
        log.info(f"Returning {len(children)} children for region {region_id}")
        return {"status": "success", "data": children}
        
    except Exception as e:
        log.error(f"Error in get_children: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def top_level(project_id):
    """
    Get top-level regions for a project
    
    Args:
        project_id (str): Project ID
        
    Returns:
        dict: List of top-level regions
    """
    try:
        user = frappe.session.user
        log.info(f"Getting top-level regions for project {project_id} by user: {user}")
        
        # Check if project exists
        if not frappe.db.exists("GRM Project", project_id):
            log.warning(f"Project {project_id} not found")
            return {"status": "error", "message": _("Project not found")}
        
        # Check if user has permission to read the project
        if not frappe.has_permission("GRM Project", "read", project_id):
            log.warning(f"User {user} does not have permission to read project {project_id}")
            return {"status": "error", "message": _("You do not have permission to access this project")}
        
        # Get top-level regions (regions with no parent)
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={
                "project": project_id,
                "parent_region": ["is", "null"]
            },
            fields=[
                "name", "region_name", "administrative_id", "administrative_level", 
                "latitude", "longitude"
            ]
        )
        
        # Enhance region data
        for region in regions:
            # Get level name
            if region.administrative_level:
                level_doc = frappe.get_doc("GRM Administrative Level Type", region.administrative_level)
                region.level_name = level_doc.level_name
        
        log.info(f"Returning {len(regions)} top-level regions for project {project_id}")
        return {"status": "success", "data": regions}
        
    except Exception as e:
        log.error(f"Error in get_top_level_regions: {str(e)}")
        return {"status": "error", "message": str(e)}

# Utility functions

def get_region_parents(region_id):
    """
    Get parent regions for a region
    
    Args:
        region_id (str): Region ID
        
    Returns:
        list: List of parent regions
    """
    parents = []
    
    # Get the region
    region = frappe.get_doc("GRM Administrative Region", region_id)
    
    # Get parent regions recursively
    current_region = region
    while current_region.parent_region:
        parent = frappe.get_doc("GRM Administrative Region", current_region.parent_region)
        parents.insert(0, {
            "id": parent.name,
            "name": parent.region_name,
            "level": parent.administrative_level,
            "project": parent.project
        })
        current_region = parent
    
    return parents

def get_region_children(region_id):
    """
    Get child regions for a region
    
    Args:
        region_id (str): Region ID
        
    Returns:
        list: List of child regions
    """
    # Get direct children
    children = frappe.get_all(
        "GRM Administrative Region",
        filters={"parent_region": region_id},
        fields=[
            "name", "region_name", "administrative_id", "administrative_level", 
            "latitude", "longitude", "project"
        ]
    )
    
    # Enhance child data
    for child in children:
        # Get level name
        if child.administrative_level:
            level_doc = frappe.get_doc("GRM Administrative Level Type", child.administrative_level)
            child.level_name = level_doc.level_name
    
    return children
