# GRM User Project Assignment Role Management Fix

**Date:** 2025-11-16
**Status:** Approved
**Author:** Claude Code

## Problem Statement

The GRM User Project Assignment DocType has three critical issues preventing proper role-based access:

1. **Role not assigned to User**: When saving an assignment, the selected role is NOT added to the User's "Has Role" child table, causing login and permission issues
2. **Role field shows all roles**: The role dropdown displays all system roles instead of only GRM-specific roles
3. **Incorrect User Permissions**: The code creates User Permissions for "Role" which doesn't grant the role—it only restricts role selection in form fields

## Solution Design

### Part 1: Assign Role Directly to User

Add role management methods to properly assign/remove roles from the User DocType:

**New Methods:**
- `assign_role_to_user()`: Add selected role to User's "Has Role" table
- `remove_role_from_user()`: Remove role only if no other active assignments use it
- `handle_role_change()`: Manage role updates when assignment is modified

**Lifecycle Integration:**
- `after_insert()`: Assign role when assignment is created
- `on_update()`: Handle role changes and is_active toggle
- `on_trash()`: Remove role if safe to do so

### Part 2: Filter Role Dropdown

**Implementation:**
- Add `get_grm_roles()` whitelisted function to filter roles by "GRM%" pattern
- Update DocType JSON to add `get_query` property to role field
- Matches existing validation in `validate_role()` (lines 47-52)

### Part 3: Clean Up User Permissions

**Changes to `validate_role()`:**
- Remove User Permission creation for "Role" (lines 57-78)
- Keep role existence and GRM role validation
- Remove duplicate entry error handling (no longer needed)

## Implementation Details

### Method: assign_role_to_user()

```python
def assign_role_to_user(self):
    """Add the selected GRM role to the user's Has Role table"""
    user_doc = frappe.get_doc("User", self.user)

    # Check if role already exists
    existing_roles = [d.role for d in user_doc.roles]

    if self.role not in existing_roles:
        user_doc.append("roles", {"role": self.role})
        user_doc.save(ignore_permissions=True)
        frappe.log(f"Added role {self.role} to user {self.user}")
```

### Method: remove_role_from_user()

```python
def remove_role_from_user(self):
    """Remove role from user if no other active assignments use it"""
    # Check if user has other active assignments with same role
    other_assignments = frappe.db.exists(
        "GRM User Project Assignment",
        {
            "user": self.user,
            "role": self.role,
            "name": ["!=", self.name],
            "is_active": 1
        }
    )

    if not other_assignments:
        user_doc = frappe.get_doc("User", self.user)
        user_doc.roles = [d for d in user_doc.roles if d.role != self.role]
        user_doc.save(ignore_permissions=True)
        frappe.log(f"Removed role {self.role} from user {self.user}")
```

### Method: handle_role_change()

```python
def handle_role_change(self, old_role):
    """Handle role updates when assignment is modified"""
    if old_role != self.role:
        # Remove old role if safe
        temp_role = self.role
        self.role = old_role
        self.remove_role_from_user()
        self.role = temp_role

        # Add new role
        self.assign_role_to_user()
```

### Query Filter Function

```python
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
```

### DocType JSON Changes

Update the `role` field configuration:

```json
{
  "fieldname": "role",
  "fieldtype": "Link",
  "in_list_view": 1,
  "label": "Role",
  "options": "Role",
  "reqd": 1,
  "get_query": "egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment.get_grm_roles"
}
```

### Updated validate_role()

Simplified version:

```python
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
            "GRM Field Officer"
        ]

        if self.role not in valid_grm_roles:
            frappe.throw(_("Role {0} is not a valid GRM role").format(self.role))

    except Exception as e:
        frappe.log_error(f"Error validating role: {str(e)}")
        raise
```

## Files to Modify

1. **grm_user_project_assignment.py**
   - Add: `assign_role_to_user()`, `remove_role_from_user()`, `handle_role_change()`
   - Add: `get_grm_roles()` whitelisted function
   - Update: `validate_role()` - remove User Permission logic
   - Update: `after_insert()` - call `assign_role_to_user()`
   - Update: `on_update()` - handle role changes and is_active toggle
   - Update: `on_trash()` - call `remove_role_from_user()`

2. **grm_user_project_assignment.json**
   - Update: `role` field - add `get_query` property

## Testing Checklist

- [ ] Create new assignment - verify role added to User
- [ ] Update assignment role - verify old role removed, new role added
- [ ] Delete assignment - verify role removed from User
- [ ] Multiple assignments with same role - verify role not removed prematurely
- [ ] Toggle is_active off - verify role removed
- [ ] Toggle is_active on - verify role added back
- [ ] Role dropdown - verify only GRM roles shown
- [ ] User login - verify permissions work correctly
- [ ] Government worker activation - verify role persists after activation

## Success Criteria

1. Users can log in and access features based on their assigned GRM role
2. Role dropdown shows only GRM-specific roles
3. Role assignment is properly managed throughout the assignment lifecycle
4. No orphaned roles remain when assignments are deleted
5. Multiple assignments with the same role don't cause issues

## Migration Notes

No database migration required. Existing assignments will work correctly once code is deployed. Administrators may need to:

1. Review existing assignments
2. Verify users have correct roles after deployment
3. Re-save assignments if roles are missing
