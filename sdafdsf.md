# Implementation Prompt for Solution 1: Enhanced GRM User Project Assignment with Native Activation

## Overview
Implement government worker activation system by enhancing the existing `GRM User Project Assignment` DocType with activation codes, email notifications, status transitions, and mobile API support. Use native Frappe features and replicate Django project's activation logic.

## Files to Create/Modify

### 1. Extend GRM User Project Assignment DocType
**Path:** `/Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json`

**Action:** MODIFY - Add new fields
- `position_title` (Data) - Job title/position
- `activation_code` (Data, Read Only) - 6-digit activation code
- `activation_status` (Select, Hidden and Readonly) - Options: "Draft", "Pending Activation", "Activated", "Expired", "Suspended"
- `activation_expires_on` (Datetime) - Code expiration date
- `code_sent_on` (Datetime) - When activation code was last sent
- `activated_on` (Datetime) - When user activated their account
- `activation_attempts` (Int, default 0) - Number of failed activation attempts


### 2. Enhanced DocType Controller
**Path:** `/Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`

**Action:** MODIFY - Add methods:
- `generate_activation_code()` - Refer to Django's zlib.adler32 logic from `/Users/victor/Documents/dev/grm-backend/src/authentication/utils.py` and adopt it for frappe standard
- `send_activation_email()` - Send email with activation code
- `activate_worker(activation_code)` - Validate and activate worker
- `resend_activation_code()` - Generate new code and resend email
- `expire_activation_code()` - Mark code as expired
- `before_insert()` - Auto-generate code for government workers
- `validate()` - Check code expiration and attempt limits
- Add workflow hooks for status transitions

### 3. Client-Side JavaScript Controller
**Path:** `/Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.js`

**Action:** MODIFY - Add:
- Custom button "Send Activation Code" (when status is Draft)
- Custom button "Resend Activation Code" (when status is Pending)
- Custom button "Activate Worker" (manual activation)
- Form refresh logic to show/hide buttons based on status
- Status indicator styling (color coding for different statuses)
- Custom button on LIST "Export Activation Codes" (exports CSV with email, code)

### 4. Email and SMS notification Template
**Path:** `to be create using frappe_mcp_server` following this guideline: `https://docs.frappe.io/erpnext/user/manual/en/email-template`

**Action:** CREATE - HTML email notification template:
- Professional government worker activation email
- Include activation code prominently
- Instructions for activation process
- Expiration notice
- Contact information for support
- Responsive design

### 5. Mobile API Endpoints
**Path:** `/Users/victor/egrm/apps/egrm/egrm/api/__init__.py`

**Action:** CREATE - API module initialization

**Path:** `/Users/victor/egrm/apps/egrm/egrm/api/activation.py`

**Action:** CREATE - API endpoints:
- `@frappe.whitelist(allow_guest=True)` decorator
- `activate_government_worker(email, activation_code, new_password)` - Validate code and activate
- `resend_activation_code(email)` - Request new activation code
- `check_activation_status(email)` - Check current activation status
- Proper error handling and response formatting
- Rate limiting for security

### 7. CSV Export Utility
**Path:** `/Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.py`

**Action:** MODIFY - Add method:
- `export_activation_codes()` - Generate CSV with columns: Email, Activation Code, Status, Employee ID, Region, Department
- Filter by project, status, administrative level
- Secure download with proper permissions
- A button on the list to export the workers

### 6. Bulk Creation Command
**Path:** `/Users/victor/egrm/apps/egrm/egrm/commands/create_government_workers.py` taking example in `/Users/victor/egrm/apps/egrm/egrm/commands/admin_regions.py`

**Action:** CREATE - Command-line utility:
- Import administrative regions and create workers per level
- Propose dynamic template based on created levels
- Progress tracking and error handling


### 8. Workflow Definition (Optional - using native DocType status instead)
**Path:** `/Users/victor/egrm/apps/egrm/egrm/egrm/doctype/grm_user_project_assignment/grm_user_project_assignment.json`

**Action:** MODIFY - Add workflow states if needed, or use simple status field transitions


## Implementation Requirements

### Email Integration
- Use Frappe's native `frappe.sendmail()`
- Template-based emails with proper styling
- Handle delivery failures gracefully
- Support both individual and bulk sending

### Status Transitions( to be create using frappe mcp server tool)
- Draft → Pending Activation (when code sent)
- Pending Activation → Activated (when user activates)
- Pending Activation → Expired (after expiration time)
- Activated → Suspended (manual action)
- Any Status → Draft (reset functionality)

### Security Considerations
- Code expiration (24-48 hours)
- Maximum activation attempts (3-5 attempts)
- Secure code generation and validation
- Input sanitization and validation

### Mobile API Response Format
```json
{
  "success": true/false,
  "message": "descriptive message",
  "data": {
    "user_id": "user_id",
    "status": "activation_status"
  },
  "errors": []
}
```

### CSV Export Format
```csv
Email,Activation_Code,Status,Position,Region,Department,Expires_On
user@domain.com,123456,Pending,Field Officer,Kigali,Health,2024-01-15
```

## Integration Points

### With Existing System
- Maintain compatibility with current `GRM User Project Assignment` functionality
- Integrate with existing permission system
- Work with current administrative region structure
- Support existing role assignments


This implementation will provide a robust, native Frappe solution for government worker activation while maintaining compatibility with existing systems and replicating the proven activation workflow.