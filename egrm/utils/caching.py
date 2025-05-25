"""
EGRM Caching Utilities
--------------------
This module contains utilities for caching frequently accessed data.
"""

import frappe
import json
import logging
from frappe.utils.redis_wrapper import RedisWrapper
from frappe.utils import cstr

# Configure logging
log = logging.getLogger(__name__)

# Redis connection
redis = RedisWrapper()

# Cache prefixes
CACHE_PREFIX = "egrm:"
REGION_CACHE_PREFIX = f"{CACHE_PREFIX}region:"
ISSUE_STATUS_CACHE_PREFIX = f"{CACHE_PREFIX}issue_status:"
CATEGORY_CACHE_PREFIX = f"{CACHE_PREFIX}category:"
PROJECT_CACHE_PREFIX = f"{CACHE_PREFIX}project:"

# Cache timeouts (in seconds)
DEFAULT_TIMEOUT = 3600  # 1 hour
REGION_TIMEOUT = 3600 * 24  # 24 hours
STATUS_TIMEOUT = 3600 * 12  # 12 hours
CATEGORY_TIMEOUT = 3600 * 12  # 12 hours
PROJECT_TIMEOUT = 3600 * 24  # 24 hours

def get_cached_region_hierarchy(region_id):
    """
    Get cached region hierarchy or fetch from database

    Args:
        region_id (str): Region ID

    Returns:
        dict: Region hierarchy
    """
    cache_key = f"{REGION_CACHE_PREFIX}hierarchy:{region_id}"

    # Try to get from cache
    cached_data = redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            log.error(f"Error parsing cached region hierarchy: {str(e)}")

    # Get region
    region = frappe.get_doc("GRM Administrative Region", region_id)

    # Build hierarchy
    parents = []
    children = []

    # Get parents
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

    # Get children
    child_regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"parent_region": region_id},
        fields=[
            "name", "region_name" "administrative_level",
             "project"
        ]
    )

    for child in child_regions:
        children.append({
            "id": child.name,
            "name": child.region_name,
            "level": child.administrative_level,
            "project": child.project
        })

    # Build result
    result = {
        "region": {
            "id": region.name,
            "name": region.region_name,
            "level": region.administrative_level,
            "project": region.project
        },
        "parents": parents,
        "children": children
    }

    # Cache result
    try:
        redis.setex(cache_key, REGION_TIMEOUT, json.dumps(result))
    except Exception as e:
        log.error(f"Error caching region hierarchy: {str(e)}")

    return result

def get_cached_region_children(region_id):
    """
    Get cached region children or fetch from database

    Args:
        region_id (str): Region ID

    Returns:
        list: Child regions
    """
    cache_key = f"{REGION_CACHE_PREFIX}children:{region_id}"

    # Try to get from cache
    cached_data = redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            log.error(f"Error parsing cached region children: {str(e)}")

    # Get children
    children = frappe.get_all(
        "GRM Administrative Region",
        filters={"parent_region": region_id},
        fields=[
            "name", "region_name", "administrative_level",
            "latitude", "longitude", "project"
        ]
    )

    # Enhance data
    result = []
    for child in children:
        result.append({
            "id": child.name,
            "name": child.region_name,
            "level": child.administrative_level,
            "project": child.project
        })

    # Cache result
    try:
        redis.setex(cache_key, REGION_TIMEOUT, json.dumps(result))
    except Exception as e:
        log.error(f"Error caching region children: {str(e)}")

    return result

def get_cached_issue_statuses():
    """
    Get cached issue statuses or fetch from database

    Returns:
        list: Issue statuses
    """
    cache_key = f"{ISSUE_STATUS_CACHE_PREFIX}all"

    # Try to get from cache
    cached_data = redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            log.error(f"Error parsing cached issue statuses: {str(e)}")

    # Get statuses
    statuses = frappe.get_all(
        "GRM Issue Status",
        fields=[
            "name", "status_name", "description",
            "initial_status", "open_status", "rejected_status",
            "final_status", "appealed_status", "color"
        ]
    )

    # Cache result
    try:
        redis.setex(cache_key, STATUS_TIMEOUT, json.dumps(statuses))
    except Exception as e:
        log.error(f"Error caching issue statuses: {str(e)}")

    return statuses

def get_cached_categories(project_id=None):
    """
    Get cached categories or fetch from database

    Args:
        project_id (str, optional): Project ID

    Returns:
        list: Categories
    """
    cache_key = f"{CATEGORY_CACHE_PREFIX}{project_id or 'all'}"

    # Try to get from cache
    cached_data = redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            log.error(f"Error parsing cached categories: {str(e)}")

    # Get categories
    filters = {}
    if project_id:
        filters["project"] = project_id

    categories = frappe.get_all(
        "GRM Issue Category",
        filters=filters,
        fields=["name", "category_name", "description", "department", "auto_assign", "active"]
    )

    # Enhance data
    for category in categories:
        if category.department:
            department_doc = frappe.get_doc("GRM Issue Department", category.department)
            category.department_name = department_doc.department_name

    # Cache result
    try:
        redis.setex(cache_key, CATEGORY_TIMEOUT, json.dumps(categories))
    except Exception as e:
        log.error(f"Error caching categories: {str(e)}")

    return categories

def get_cached_project(project_id):
    """
    Get cached project or fetch from database

    Args:
        project_id (str): Project ID

    Returns:
        dict: Project data
    """
    cache_key = f"{PROJECT_CACHE_PREFIX}{project_id}"

    # Try to get from cache
    cached_data = redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception as e:
            log.error(f"Error parsing cached project: {str(e)}")

    # Get project
    project = frappe.get_doc("GRM Project", project_id)

    # Build result
    result = {
        "name": project.name,
        "project_name": project.project_name,
        "description": project.description,
        "active": project.active,
        "auto_submit_issues": project.auto_submit_issues
    }

    # Cache result
    try:
        redis.setex(cache_key, PROJECT_TIMEOUT, json.dumps(result))
    except Exception as e:
        log.error(f"Error caching project: {str(e)}")

    return result

def clear_region_cache(region_id=None):
    """
    Clear region cache

    Args:
        region_id (str, optional): Region ID

    Returns:
        None
    """
    if region_id:
        # Clear specific region cache
        cache_keys = [
            f"{REGION_CACHE_PREFIX}hierarchy:{region_id}",
            f"{REGION_CACHE_PREFIX}children:{region_id}"
        ]

        # Also clear parent region's children cache
        region = frappe.get_doc("GRM Administrative Region", region_id)
        if region.parent_region:
            cache_keys.append(f"{REGION_CACHE_PREFIX}children:{region.parent_region}")

        # Delete each key
        for key in cache_keys:
            try:
                redis.delete(key)
            except Exception as e:
                log.error(f"Error clearing region cache: {str(e)}")
    else:
        # Clear all region caches
        try:
            keys = redis.keys(f"{REGION_CACHE_PREFIX}*")
            if keys:
                redis.delete(*keys)
        except Exception as e:
            log.error(f"Error clearing all region caches: {str(e)}")

def clear_status_cache():
    """
    Clear status cache

    Returns:
        None
    """
    try:
        keys = redis.keys(f"{ISSUE_STATUS_CACHE_PREFIX}*")
        if keys:
            redis.delete(*keys)
    except Exception as e:
        log.error(f"Error clearing status cache: {str(e)}")

def clear_category_cache(project_id=None):
    """
    Clear category cache

    Args:
        project_id (str, optional): Project ID

    Returns:
        None
    """
    if project_id:
        # Clear specific project category cache
        try:
            redis.delete(f"{CATEGORY_CACHE_PREFIX}{project_id}")
        except Exception as e:
            log.error(f"Error clearing category cache for project {project_id}: {str(e)}")
    else:
        # Clear all category caches
        try:
            keys = redis.keys(f"{CATEGORY_CACHE_PREFIX}*")
            if keys:
                redis.delete(*keys)
        except Exception as e:
            log.error(f"Error clearing all category caches: {str(e)}")

def clear_project_cache(project_id=None):
    """
    Clear project cache

    Args:
        project_id (str, optional): Project ID

    Returns:
        None
    """
    if project_id:
        # Clear specific project cache
        try:
            redis.delete(f"{PROJECT_CACHE_PREFIX}{project_id}")
        except Exception as e:
            log.error(f"Error clearing project cache for {project_id}: {str(e)}")
    else:
        # Clear all project caches
        try:
            keys = redis.keys(f"{PROJECT_CACHE_PREFIX}*")
            if keys:
                redis.delete(*keys)
        except Exception as e:
            log.error(f"Error clearing all project caches: {str(e)}")
