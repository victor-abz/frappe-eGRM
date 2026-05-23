"""Shared role constants for egrm API endpoints.

Keeping a single source of truth for "who bypasses project scoping"
prevents drift across API entry points when roles are added or removed.
"""

# Roles that grant access to ALL projects regardless of GRM User Project
# Assignment rows. System Manager bypasses Frappe permission checks
# entirely; GRM Platform Administrator manages projects globally;
# GRM Supervise is the project-scoped supervisor role and historically
# saw all projects in the bench.
GRM_ALL_PROJECTS_ROLES: set[str] = {
    "System Manager",
    "GRM Platform Administrator",
    "GRM Supervise",
}
