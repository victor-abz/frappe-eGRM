# Phase 3 Implementation Plan: Notifications & SLA Tracking

**Project**: World Bank GRM Compliance - eGRM Frappe App
**Phase**: 3 of 3
**Focus**: Automated Notifications, Citizen Receipts, and SLA Tracking
**Duration**: 3 weeks
**Prerequisites**: Phase 1 (Public Transparency) and Phase 2 (Automated Reporting) completed

---

## Overview

This phase implements automated notification systems for citizen receipts and process updates, plus SLA (Service Level Agreement) tracking with automatic escalation. This addresses:

- **WB Requirement**: Automated acknowledgment receipts within 7 days
- **WB Requirement**: Process roadmap/status notifications to citizens
- **WB Requirement**: SLA tracking at administrative levels
- **WB Requirement**: Signed resolution agreements

### Key Features

1. **Notification Template System**: Reuses Frappe Email Templates with project-level configuration
2. **Multi-Channel Delivery**: Email and SMS support with Jinja2 templating
3. **SLA Configuration**: Per administrative level, configurable timeframes
4. **Auto-Escalation**: Automatic escalation to parent region when SLA expires
5. **Resolution Agreements**: File upload and tracking for signed agreements

### Architecture Decisions

- **Notification Templates**: Link to Frappe Email Template (reuse standard), store SMS as Jinja text
- **SLA Storage**: Direct fields in `GRM Administrative Level Type` (not separate DocType)
- **SLA Calculation**: Based on issue's `administrative_region.administrative_level`
- **Escalation**: Uses existing `parent_region` hierarchy in `GRM Administrative Region`
- **Multi-Project**: Each project selects its own templates and has its own SLA configurations

---

## Task 1: Create GRM Notification Template DocType

**File**: `egrm/egrm/doctype/grm_notification_template/grm_notification_template.json`

### Objective

Create a DocType to define notification templates that can be selected at the project level for different events (receipt, acknowledgment, resolution, etc.).

### Fields Structure

```json
{
  "name": "GRM Notification Template",
  "module": "eGRM",
  "naming_rule": "By fieldname",
  "autoname": "field:template_name",
  "fields": [
    {
      "fieldname": "template_name",
      "label": "Template Name",
      "fieldtype": "Data",
      "unique": 1,
      "reqd": 1,
      "description": "Unique name for this notification template"
    },
    {
      "fieldname": "template_type",
      "label": "Template Type",
      "fieldtype": "Select",
      "options": "Receipt\nAcknowledgment\nIn Progress\nResolved\nClosed\nEscalated\nSLA Reminder",
      "reqd": 1,
      "description": "Type of notification this template is for"
    },
    {
      "fieldname": "sb_email",
      "label": "Email Configuration",
      "fieldtype": "Section Break"
    },
    {
      "fieldname": "email_template",
      "label": "Email Template",
      "fieldtype": "Link",
      "options": "Email Template",
      "description": "Link to Frappe Email Template for email notifications"
    },
    {
      "fieldname": "cb_sms",
      "label": "",
      "fieldtype": "Column Break"
    },
    {
      "fieldname": "enable_sms",
      "label": "Enable SMS",
      "fieldtype": "Check",
      "default": 0
    },
    {
      "fieldname": "sms_message",
      "label": "SMS Message",
      "fieldtype": "Text",
      "depends_on": "eval:doc.enable_sms",
      "description": "SMS message template (supports Jinja2: {{ tracking_code }}, {{ status }}, etc.)"
    },
    {
      "fieldname": "sb_settings",
      "label": "Settings",
      "fieldtype": "Section Break"
    },
    {
      "fieldname": "project",
      "label": "Project",
      "fieldtype": "Link",
      "options": "GRM Project",
      "description": "Leave blank for shared templates, or select project for project-specific template"
    },
    {
      "fieldname": "active",
      "label": "Active",
      "fieldtype": "Check",
      "default": 1
    },
    {
      "fieldname": "sb_preview",
      "label": "Template Variables Reference",
      "fieldtype": "Section Break",
      "collapsible": 1
    },
    {
      "fieldname": "template_help",
      "label": "",
      "fieldtype": "HTML",
      "options": "<p>Available template variables for Jinja2:</p><ul><li><code>{{ tracking_code }}</code> - Issue tracking code</li><li><code>{{ subject }}</code> - Issue subject</li><li><code>{{ status }}</code> - Current status</li><li><code>{{ administrative_region }}</code> - Administrative region name</li><li><code>{{ created_date }}</code> - Issue creation date</li><li><code>{{ complainant_name }}</code> - Complainant name</li><li><code>{{ resolution_summary }}</code> - Resolution summary (if resolved)</li><li><code>{{ sla_acknowledgment_due }}</code> - Acknowledgment due date</li><li><code>{{ sla_resolution_due }}</code> - Resolution due date</li></ul>"
    }
  ]
}
```

### Implementation Steps

1. **Create DocType JSON**:
   ```bash
   # Location: egrm/egrm/doctype/grm_notification_template/
   touch grm_notification_template.json
   ```

2. **Create Python Controller** (`grm_notification_template.py`):
   ```python
   import frappe
   from frappe.model.document import Document

   class GRMNotificationTemplate(Document):
       def validate(self):
           """Validate template configuration"""
           # Ensure at least one channel is configured
           if not self.email_template and not self.enable_sms:
               frappe.throw(_("Please configure at least one notification channel (Email or SMS)"))

           # Validate Jinja syntax in SMS message
           if self.enable_sms and self.sms_message:
               try:
                   frappe.render_template(self.sms_message, {
                       "tracking_code": "TEST-001",
                       "subject": "Test",
                       "status": "Open"
                   })
               except Exception as e:
                   frappe.throw(_("Invalid Jinja2 syntax in SMS message: {0}").format(str(e)))

       def render_sms(self, context):
           """Render SMS message with context"""
           if not self.enable_sms or not self.sms_message:
               return None

           return frappe.render_template(self.sms_message, context)
   ```

3. **Create JS Controller** (`grm_notification_template.js`):
   ```javascript
   frappe.ui.form.on('GRM Notification Template', {
       refresh: function(frm) {
           // Show preview button
           if (!frm.is_new()) {
               frm.add_custom_button(__('Preview'), function() {
                   show_template_preview(frm);
               });
           }
       },

       enable_sms: function(frm) {
           frm.toggle_reqd('sms_message', frm.doc.enable_sms);
       }
   });

   function show_template_preview(frm) {
       // Show dialog with sample data preview
       let d = new frappe.ui.Dialog({
           title: __('Template Preview'),
           fields: [
               {
                   fieldname: 'html',
                   fieldtype: 'HTML',
                   options: `<p>Preview with sample data:</p>
                             <ul>
                               <li><strong>Tracking Code:</strong> GRM-2025-001</li>
                               <li><strong>Status:</strong> Open</li>
                               <li><strong>Subject:</strong> Road Damage Complaint</li>
                             </ul>`
               }
           ]
       });
       d.show();
   }
   ```

### Verification

- [ ] DocType appears in GRM module list
- [ ] Can create new template and link to Email Template
- [ ] SMS message validates Jinja2 syntax on save
- [ ] Template can be project-specific or shared
- [ ] All template types available in dropdown

---

## Task 2: Add Notification Configuration to GRM Project

**File**: `egrm/egrm/doctype/grm_project/grm_project.json`

### Objective

Add fields to GRM Project to allow selection of notification templates for different events.

### Fields to Add

Add these fields in a new "Notification Settings" section:

```json
{
  "fieldname": "sb_notifications",
  "label": "Notification Settings",
  "fieldtype": "Section Break",
  "collapsible": 1
},
{
  "fieldname": "enable_notifications",
  "label": "Enable Automated Notifications",
  "fieldtype": "Check",
  "default": 1,
  "description": "Send automated email/SMS notifications to citizens"
},
{
  "fieldname": "cb_notif1",
  "fieldtype": "Column Break"
},
{
  "fieldname": "receipt_template",
  "label": "Receipt Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent immediately when complaint is submitted"
},
{
  "fieldname": "acknowledgment_template",
  "label": "Acknowledgment Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent when complaint is acknowledged (status changed to Acknowledged)"
},
{
  "fieldname": "in_progress_template",
  "label": "In Progress Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent when complaint status changes to In Progress"
},
{
  "fieldname": "cb_notif2",
  "fieldtype": "Column Break"
},
{
  "fieldname": "resolved_template",
  "label": "Resolved Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent when complaint is resolved"
},
{
  "fieldname": "closed_template",
  "label": "Closed Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent when complaint is closed"
},
{
  "fieldname": "escalated_template",
  "label": "Escalated Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent when complaint is escalated to higher level"
},
{
  "fieldname": "sla_reminder_template",
  "label": "SLA Reminder Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template",
  "depends_on": "eval:doc.enable_notifications",
  "description": "Sent as reminder before SLA expires"
}
```

### Implementation Steps

1. **Update GRM Project JSON**:
   - Add fields above to existing field list
   - Place after existing project settings sections

2. **Update GRM Project Python Controller** (`grm_project.py`):
   ```python
   def validate(self):
       # Existing validation...

       # Validate notification templates
       if self.enable_notifications:
           self.validate_notification_templates()

   def validate_notification_templates(self):
       """Ensure selected templates are active and compatible"""
       template_fields = [
           'receipt_template', 'acknowledgment_template', 'in_progress_template',
           'resolved_template', 'closed_template', 'escalated_template',
           'sla_reminder_template'
       ]

       for field in template_fields:
           template_name = self.get(field)
           if template_name:
               template = frappe.get_doc("GRM Notification Template", template_name)
               if not template.active:
                   frappe.throw(_("Template {0} is not active").format(template_name))

               # Check if template is project-specific and matches
               if template.project and template.project != self.name:
                   frappe.throw(_("Template {0} belongs to another project").format(template_name))
   ```

### Verification

- [ ] Notification Settings section visible in GRM Project form
- [ ] Template fields only show when notifications enabled
- [ ] Can select templates from dropdown
- [ ] Validation prevents inactive or wrong-project templates
- [ ] Existing projects load without errors

---

## Task 3: Create Example Frappe Email Templates

**Location**: Via Frappe UI (Email Template DocType)

### Objective

Create example Frappe Email Templates that can be linked from GRM Notification Templates. These serve as starting points for projects to customize.

### Email Template 1: Receipt Template

**Name**: `GRM Receipt - Default`

**Subject**: `Receipt: Your complaint {{ doc.tracking_code }} has been received`

**Response HTML**:
```html
<p>Dear {{ doc.complainant_name or "Valued Citizen" }},</p>

<p>Thank you for submitting your complaint. This is to confirm that we have received your complaint and assigned it the tracking code:</p>

<h3 style="color: #0066cc;">{{ doc.tracking_code }}</h3>

<p><strong>Complaint Details:</strong></p>
<ul>
  <li><strong>Subject:</strong> {{ doc.subject }}</li>
  <li><strong>Category:</strong> {{ doc.complaint_category }}</li>
  <li><strong>Submitted Date:</strong> {{ frappe.utils.formatdate(doc.creation, "dd MMM yyyy") }}</li>
  <li><strong>Administrative Region:</strong> {{ doc.administrative_region }}</li>
</ul>

<p><strong>What happens next?</strong></p>
<ol>
  <li>Your complaint will be reviewed by our team within {{ doc.sla_acknowledgment_days or 7 }} business days</li>
  <li>You will receive an acknowledgment notification once the review is complete</li>
  <li>You can track your complaint status anytime using your tracking code</li>
</ol>

<p><strong>Track Your Complaint:</strong><br>
Visit: <a href="{{ frappe.utils.get_url() }}/grm-public/track-complaint?code={{ doc.tracking_code }}">{{ frappe.utils.get_url() }}/grm-public/track-complaint</a></p>

<p>Please keep your tracking code safe for future reference.</p>

<p>Best regards,<br>
{{ doc.project }} GRM Team</p>

<hr>
<p style="font-size: 0.9em; color: #666;">
This is an automated message. Please do not reply to this email.
</p>
```

### Email Template 2: Acknowledgment Template

**Name**: `GRM Acknowledgment - Default`

**Subject**: `Your complaint {{ doc.tracking_code }} has been acknowledged`

**Response HTML**:
```html
<p>Dear {{ doc.complainant_name or "Valued Citizen" }},</p>

<p>This is to inform you that your complaint has been officially acknowledged and is now being processed.</p>

<h3 style="color: #0066cc;">{{ doc.tracking_code }}</h3>

<p><strong>Complaint Status Update:</strong></p>
<ul>
  <li><strong>Status:</strong> {{ doc.status }}</li>
  <li><strong>Acknowledged Date:</strong> {{ frappe.utils.formatdate(doc.acknowledgment_date, "dd MMM yyyy") }}</li>
  <li><strong>Assigned To:</strong> {{ doc.administrative_region }}</li>
  <li><strong>Expected Resolution:</strong> {{ frappe.utils.formatdate(doc.sla_resolution_due, "dd MMM yyyy") if doc.sla_resolution_due else "To be determined" }}</li>
</ul>

<p>Our team is now actively working on addressing your concern. You will receive further updates as progress is made.</p>

<p><strong>Track Your Complaint:</strong><br>
Visit: <a href="{{ frappe.utils.get_url() }}/grm-public/track-complaint?code={{ doc.tracking_code }}">{{ frappe.utils.get_url() }}/grm-public/track-complaint</a></p>

<p>Thank you for your patience.</p>

<p>Best regards,<br>
{{ doc.project }} GRM Team</p>
```

### Email Template 3: Resolution Template

**Name**: `GRM Resolution - Default`

**Subject**: `Your complaint {{ doc.tracking_code }} has been resolved`

**Response HTML**:
```html
<p>Dear {{ doc.complainant_name or "Valued Citizen" }},</p>

<p>We are pleased to inform you that your complaint has been resolved.</p>

<h3 style="color: #28a745;">{{ doc.tracking_code }} - RESOLVED</h3>

<p><strong>Resolution Details:</strong></p>
<ul>
  <li><strong>Resolved Date:</strong> {{ frappe.utils.formatdate(doc.resolution_date, "dd MMM yyyy") }}</li>
  <li><strong>Resolution Summary:</strong> {{ doc.resolution_summary or "Please contact us for details" }}</li>
</ul>

{% if doc.resolution_agreement %}
<p><strong>Resolution Agreement:</strong> A signed agreement document has been attached to your case record.</p>
{% endif %}

<p><strong>Further Actions:</strong></p>
<ul>
  <li>If you are satisfied with the resolution, no further action is needed</li>
  <li>If you wish to appeal, you may do so within the appeal period</li>
  <li>View full details: <a href="{{ frappe.utils.get_url() }}/grm-public/track-complaint?code={{ doc.tracking_code }}">Track Complaint</a></li>
</ul>

<p>Thank you for using our Grievance Redress Mechanism.</p>

<p>Best regards,<br>
{{ doc.project }} GRM Team</p>
```

### Email Template 4: SLA Reminder Template

**Name**: `GRM SLA Reminder - Default`

**Subject**: `Reminder: Complaint {{ doc.tracking_code }} requires attention`

**Response HTML**:
```html
<p>Dear {{ doc.complainant_name or "Valued Citizen" }},</p>

<p>This is a reminder regarding your complaint:</p>

<h3 style="color: #ffc107;">{{ doc.tracking_code }}</h3>

<p><strong>Status Update:</strong></p>
<ul>
  <li><strong>Current Status:</strong> {{ doc.status }}</li>
  <li><strong>Expected Resolution Date:</strong> {{ frappe.utils.formatdate(doc.sla_resolution_due, "dd MMM yyyy") if doc.sla_resolution_due else "To be determined" }}</li>
  <li><strong>Days Remaining:</strong> {{ doc.sla_days_remaining or "Calculating..." }}</li>
</ul>

<p>We are actively working on your complaint and wanted to update you on the progress.</p>

<p><strong>Track Your Complaint:</strong><br>
Visit: <a href="{{ frappe.utils.get_url() }}/grm-public/track-complaint?code={{ doc.tracking_code }}">{{ frappe.utils.get_url() }}/grm-public/track-complaint</a></p>

<p>Thank you for your patience.</p>

<p>Best regards,<br>
{{ doc.project }} GRM Team</p>
```

### Implementation Steps

1. **Create Email Templates via UI**:
   ```
   Go to: Desk → Setup → Email → Email Template → New
   - Create each template above
   - Set Document Type: "GRM Issue"
   - Test with sample GRM Issue document
   ```

2. **Export as Fixtures** (optional, for version control):
   ```python
   # In hooks.py
   fixtures = [
       {
           "dt": "Email Template",
           "filters": [["name", "in", [
               "GRM Receipt - Default",
               "GRM Acknowledgment - Default",
               "GRM Resolution - Default",
               "GRM SLA Reminder - Default"
           ]]]
       }
   ]
   ```

3. **Create Corresponding GRM Notification Templates**:
   - Link each Email Template to a GRM Notification Template
   - Add sample SMS messages

### Verification

- [ ] All 4 Email Templates created successfully
- [ ] Preview works with sample GRM Issue
- [ ] Variables render correctly ({{ doc.tracking_code }}, etc.)
- [ ] HTML formatting displays properly
- [ ] Templates can be linked from GRM Notification Template

---

## Task 4: Add Notification Logic to GRM Issue

**File**: `egrm/egrm/doctype/grm_issue/grm_issue.py`

### Objective

Add methods to GRM Issue to send notifications at key lifecycle events using the configured templates.

### Implementation

Add the following methods to the `GRMIssue` class:

```python
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, nowdate

class GRMIssue(Document):
    # ... existing methods ...

    def after_insert(self):
        """Send receipt notification after issue creation"""
        self.send_notification('receipt')

    def on_update(self):
        """Send notifications on status changes"""
        if self.has_value_changed('status'):
            self.handle_status_change_notification()

        # Existing on_update logic...

    def handle_status_change_notification(self):
        """Send appropriate notification based on new status"""
        status_template_map = {
            'Acknowledged': 'acknowledgment',
            'In Progress': 'in_progress',
            'Resolved': 'resolved',
            'Closed': 'closed'
        }

        template_type = status_template_map.get(self.status)
        if template_type:
            self.send_notification(template_type)

    def send_notification(self, notification_type):
        """
        Send notification via configured channels

        Args:
            notification_type: Type of notification (receipt, acknowledgment, etc.)
        """
        # Check if notifications enabled for project
        project = frappe.get_doc("GRM Project", self.project)
        if not project.enable_notifications:
            return

        # Get template for this notification type
        template_field = f"{notification_type}_template"
        template_name = project.get(template_field)

        if not template_name:
            frappe.log_error(
                f"No {notification_type} template configured for project {self.project}",
                "GRM Notification Error"
            )
            return

        try:
            template = frappe.get_doc("GRM Notification Template", template_name)

            # Send email if configured
            if template.email_template:
                self.send_email_notification(template.email_template)

            # Send SMS if configured
            if template.enable_sms and template.sms_message:
                self.send_sms_notification(template)

            # Log notification sent
            self.add_comment(
                "Info",
                f"{notification_type.title()} notification sent to {self.complainant_email or self.complainant_phone}"
            )

        except Exception as e:
            frappe.log_error(
                f"Failed to send {notification_type} notification: {str(e)}",
                "GRM Notification Error"
            )

    def send_email_notification(self, email_template_name):
        """Send email using Frappe Email Template"""
        if not self.complainant_email:
            return

        try:
            from frappe.core.doctype.communication.email import make

            # Get email template
            email_template = frappe.get_doc("Email Template", email_template_name)

            # Render template with current document context
            subject = frappe.render_template(email_template.subject, {"doc": self})
            message = frappe.render_template(email_template.response_html, {"doc": self})

            # Send email
            frappe.sendmail(
                recipients=[self.complainant_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name,
                send_priority=0  # Send immediately
            )

            frappe.logger().info(f"Email sent to {self.complainant_email} for {self.name}")

        except Exception as e:
            frappe.log_error(
                f"Email send failed for {self.name}: {str(e)}",
                "GRM Email Error"
            )
            raise

    def send_sms_notification(self, template):
        """Send SMS using configured SMS provider"""
        if not self.complainant_phone:
            return

        try:
            # Render SMS message template
            context = self.get_notification_context()
            sms_message = template.render_sms(context)

            if not sms_message:
                return

            # Send via Frappe SMS integration
            from frappe.core.doctype.sms_settings.sms_settings import send_sms

            send_sms(
                receiver_list=[self.complainant_phone],
                msg=sms_message,
                success_msg=False  # Don't show success message to user
            )

            frappe.logger().info(f"SMS sent to {self.complainant_phone} for {self.name}")

        except Exception as e:
            frappe.log_error(
                f"SMS send failed for {self.name}: {str(e)}",
                "GRM SMS Error"
            )
            # Don't raise - SMS is secondary channel

    def get_notification_context(self):
        """Get context dict for template rendering"""
        return {
            'tracking_code': self.tracking_code,
            'subject': self.subject,
            'status': self.status,
            'administrative_region': self.administrative_region,
            'created_date': frappe.utils.formatdate(self.creation, "dd MMM yyyy"),
            'complainant_name': self.complainant_name,
            'resolution_summary': self.resolution_summary,
            'sla_acknowledgment_due': frappe.utils.formatdate(self.sla_acknowledgment_due, "dd MMM yyyy") if self.get('sla_acknowledgment_due') else None,
            'sla_resolution_due': frappe.utils.formatdate(self.sla_resolution_due, "dd MMM yyyy") if self.get('sla_resolution_due') else None,
            'sla_days_remaining': self.get('sla_days_remaining'),
            'project': self.project
        }

    def send_escalation_notification(self):
        """Send notification when issue is escalated"""
        self.send_notification('escalated')
```

### Additional Methods for Manual Triggers

```python
@frappe.whitelist()
def resend_notification(self, notification_type):
    """Allow manual resend of notification (from UI button)"""
    if not frappe.has_permission(self.doctype, "write", self.name):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    self.send_notification(notification_type)
    frappe.msgprint(_("Notification sent successfully"))
```

### Update JS Controller

Add resend button in `grm_issue.js`:

```javascript
frappe.ui.form.on('GRM Issue', {
    refresh: function(frm) {
        // Existing refresh logic...

        // Add resend notification button
        if (!frm.is_new() && frm.doc.complainant_email) {
            frm.add_custom_button(__('Resend Notification'), function() {
                show_resend_dialog(frm);
            }, __('Actions'));
        }
    }
});

function show_resend_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Resend Notification'),
        fields: [
            {
                fieldname: 'notification_type',
                label: __('Notification Type'),
                fieldtype: 'Select',
                options: 'Receipt\nAcknowledgment\nIn Progress\nResolved\nClosed\nEscalated',
                reqd: 1
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function(values) {
            frappe.call({
                method: 'resend_notification',
                doc: frm.doc,
                args: {
                    notification_type: values.notification_type.toLowerCase().replace(' ', '_')
                },
                callback: function(r) {
                    d.hide();
                    frm.reload_doc();
                }
            });
        }
    });
    d.show();
}
```

### Verification

- [ ] Receipt notification sent on issue creation
- [ ] Status change notifications sent automatically
- [ ] Email notifications delivered successfully
- [ ] SMS notifications sent (if SMS configured)
- [ ] Comments logged for sent notifications
- [ ] Resend button works from UI
- [ ] Error logging works for failed sends

---

## Task 5: Add SLA Fields to GRM Administrative Level Type

**File**: `egrm/egrm/doctype/grm_administrative_level_type/grm_administrative_level_type.json`

### Objective

Add SLA configuration fields directly to the Administrative Level Type DocType, so each level (Village, District, Province, etc.) can have its own SLA timeframes.

### Fields to Add

Add these fields in a new "SLA Configuration" section:

```json
{
  "fieldname": "sb_sla",
  "label": "SLA Configuration",
  "fieldtype": "Section Break",
  "collapsible": 1,
  "description": "Service Level Agreement timeframes for this administrative level"
},
{
  "fieldname": "acknowledgment_days",
  "label": "Acknowledgment Days",
  "fieldtype": "Int",
  "default": 7,
  "description": "Number of business days to acknowledge complaint (default: 7 per WB guidelines)"
},
{
  "fieldname": "resolution_days",
  "label": "Resolution Days",
  "fieldtype": "Int",
  "default": 30,
  "description": "Number of business days to resolve complaint (default: 30 per WB guidelines)"
},
{
  "fieldname": "cb_sla",
  "fieldtype": "Column Break"
},
{
  "fieldname": "reminder_before_days",
  "label": "Reminder Before (Days)",
  "fieldtype": "Int",
  "default": 2,
  "description": "Send reminder notification this many days before SLA expires"
},
{
  "fieldname": "auto_escalate",
  "label": "Auto-Escalate on SLA Breach",
  "fieldtype": "Check",
  "default": 1,
  "description": "Automatically escalate to parent level if SLA is breached"
}
```

### Implementation Steps

1. **Update JSON File**:
   ```bash
   # Edit: egrm/egrm/doctype/grm_administrative_level_type/grm_administrative_level_type.json
   # Add fields above to existing field list
   ```

2. **Update Python Controller** (`grm_administrative_level_type.py`):
   ```python
   import frappe
   from frappe.model.document import Document

   class GRMAdministrativeLevelType(Document):
       def validate(self):
           """Validate SLA configuration"""
           # Ensure acknowledgment is less than resolution
           if self.acknowledgment_days and self.resolution_days:
               if self.acknowledgment_days >= self.resolution_days:
                   frappe.throw(_("Acknowledgment days must be less than resolution days"))

           # Ensure reminder is reasonable
           if self.reminder_before_days and self.resolution_days:
               if self.reminder_before_days >= self.resolution_days:
                   frappe.throw(_("Reminder days must be less than resolution days"))

       def get_sla_config(self):
           """Get SLA configuration as dict"""
           return {
               'acknowledgment_days': self.acknowledgment_days or 7,
               'resolution_days': self.resolution_days or 30,
               'reminder_before_days': self.reminder_before_days or 2,
               'auto_escalate': self.auto_escalate
           }
   ```

3. **Add Default SLA Values** (Data Migration):
   ```python
   # Create file: egrm/egrm/patches/v1_0/set_default_sla_values.py

   import frappe

   def execute():
       """Set default SLA values for existing administrative level types"""
       level_types = frappe.get_all("GRM Administrative Level Type", pluck="name")

       for level_name in level_types:
           doc = frappe.get_doc("GRM Administrative Level Type", level_name)

           # Set defaults if not already set
           if not doc.acknowledgment_days:
               doc.acknowledgment_days = 7
           if not doc.resolution_days:
               doc.resolution_days = 30
           if not doc.reminder_before_days:
               doc.reminder_before_days = 2
           if doc.auto_escalate is None:
               doc.auto_escalate = 1

           doc.save()

       frappe.db.commit()
   ```

4. **Register Patch in hooks.py**:
   ```python
   # In hooks.py, add to patches list:
   patches = [
       # ... existing patches ...
       "egrm.patches.v1_0.set_default_sla_values"
   ]
   ```

### Verification

- [ ] SLA section appears in Administrative Level Type form
- [ ] Default values applied on new records
- [ ] Validation prevents invalid configurations
- [ ] Existing records updated with defaults (after patch)
- [ ] get_sla_config() method returns correct dict

---

## Task 6: Add SLA Tracking Fields to GRM Issue

**File**: `egrm/egrm/doctype/grm_issue/grm_issue.json`

### Objective

Add fields to GRM Issue to track SLA deadlines, status, and breach information.

### Fields to Add

Add in a new "SLA Tracking" section:

```json
{
  "fieldname": "sb_sla",
  "label": "SLA Tracking",
  "fieldtype": "Section Break",
  "collapsible": 1
},
{
  "fieldname": "sla_acknowledgment_days",
  "label": "SLA Acknowledgment (Days)",
  "fieldtype": "Int",
  "read_only": 1,
  "description": "Configured acknowledgment SLA for this administrative level"
},
{
  "fieldname": "sla_resolution_days",
  "label": "SLA Resolution (Days)",
  "fieldtype": "Int",
  "read_only": 1,
  "description": "Configured resolution SLA for this administrative level"
},
{
  "fieldname": "cb_sla1",
  "fieldtype": "Column Break"
},
{
  "fieldname": "sla_acknowledgment_due",
  "label": "Acknowledgment Due Date",
  "fieldtype": "Date",
  "read_only": 1,
  "description": "Calculated deadline for acknowledgment"
},
{
  "fieldname": "sla_resolution_due",
  "label": "Resolution Due Date",
  "fieldtype": "Date",
  "read_only": 1,
  "description": "Calculated deadline for resolution"
},
{
  "fieldname": "sb_sla_status",
  "label": "SLA Status",
  "fieldtype": "Section Break",
  "collapsible": 1
},
{
  "fieldname": "sla_acknowledgment_status",
  "label": "Acknowledgment SLA Status",
  "fieldtype": "Select",
  "options": "\nOn Time\nNearing Due\nBreached",
  "read_only": 1,
  "default": "On Time"
},
{
  "fieldname": "sla_resolution_status",
  "label": "Resolution SLA Status",
  "fieldtype": "Select",
  "options": "\nOn Time\nNearing Due\nBreached",
  "read_only": 1,
  "default": "On Time"
},
{
  "fieldname": "cb_sla2",
  "fieldtype": "Column Break"
},
{
  "fieldname": "sla_acknowledgment_breached_date",
  "label": "Acknowledgment Breached On",
  "fieldtype": "Datetime",
  "read_only": 1
},
{
  "fieldname": "sla_resolution_breached_date",
  "label": "Resolution Breached On",
  "fieldtype": "Datetime",
  "read_only": 1
},
{
  "fieldname": "sla_days_remaining",
  "label": "Days Remaining (Resolution)",
  "fieldtype": "Int",
  "read_only": 1
},
{
  "fieldname": "sb_escalation",
  "label": "Escalation Tracking",
  "fieldtype": "Section Break",
  "collapsible": 1
},
{
  "fieldname": "escalation_count",
  "label": "Escalation Count",
  "fieldtype": "Int",
  "default": 0,
  "read_only": 1,
  "description": "Number of times this issue has been escalated"
},
{
  "fieldname": "last_escalated_date",
  "label": "Last Escalated On",
  "fieldtype": "Datetime",
  "read_only": 1
},
{
  "fieldname": "cb_esc",
  "fieldtype": "Column Break"
},
{
  "fieldname": "escalation_reason",
  "label": "Last Escalation Reason",
  "fieldtype": "Small Text",
  "read_only": 1
}
```

### Implementation Steps

1. **Update GRM Issue JSON**: Add fields above

2. **Run Migrate**:
   ```bash
   bench --site [site-name] migrate
   ```

### Verification

- [ ] SLA fields visible in GRM Issue form
- [ ] All fields read-only (managed by SLA Manager)
- [ ] Fields appear in correct sections
- [ ] Existing issues load without errors

---

## Task 7: Create SLA Manager Module

**File**: `egrm/egrm/utils/sla_manager.py`

### Objective

Create a dedicated module to handle all SLA calculations, tracking, and escalation logic, keeping GRM Issue controller clean.

### Implementation

```python
"""
SLA Manager for GRM Issues

Handles:
- SLA calculation based on administrative level
- SLA status tracking (On Time, Nearing Due, Breached)
- Automatic escalation when SLA breached
- Reminder notifications before SLA expiration
"""

import frappe
from frappe import _
from frappe.utils import (
    getdate, nowdate, add_days, date_diff,
    get_datetime, now_datetime, add_to_date
)
import json


class SLAManager:
    """Manages SLA tracking and escalation for GRM Issues"""

    def __init__(self, issue_doc):
        """
        Args:
            issue_doc: GRM Issue document instance
        """
        self.issue = issue_doc
        self.level_config = None

    def initialize_sla(self):
        """
        Initialize SLA when issue is created or administrative region changes
        Called from GRM Issue.after_insert() and on region change
        """
        if not self.issue.administrative_region:
            return

        # Get SLA configuration from administrative level
        self.level_config = self.get_level_sla_config()

        if not self.level_config:
            frappe.log_error(
                f"No SLA config found for region {self.issue.administrative_region}",
                "SLA Initialization Error"
            )
            return

        # Set SLA values
        self.issue.sla_acknowledgment_days = self.level_config['acknowledgment_days']
        self.issue.sla_resolution_days = self.level_config['resolution_days']

        # Calculate due dates (business days)
        creation_date = getdate(self.issue.creation)
        self.issue.sla_acknowledgment_due = add_business_days(
            creation_date,
            self.level_config['acknowledgment_days']
        )
        self.issue.sla_resolution_due = add_business_days(
            creation_date,
            self.level_config['resolution_days']
        )

        # Initialize status
        self.issue.sla_acknowledgment_status = "On Time"
        self.issue.sla_resolution_status = "On Time"

        # Calculate days remaining
        self.update_days_remaining()

    def get_level_sla_config(self):
        """Get SLA configuration from administrative level type"""
        region = frappe.get_doc("GRM Administrative Region", self.issue.administrative_region)
        level_type = frappe.get_doc("GRM Administrative Level Type", region.administrative_level)
        return level_type.get_sla_config()

    def update_sla_status(self):
        """
        Update SLA status fields based on current dates
        Called from scheduled job and on status changes
        """
        if not self.issue.sla_acknowledgment_due or not self.issue.sla_resolution_due:
            return

        today = getdate(nowdate())

        # Update acknowledgment SLA status
        if self.issue.status not in ['Acknowledged', 'In Progress', 'Resolved', 'Closed']:
            self.issue.sla_acknowledgment_status = self._calculate_sla_status(
                self.issue.sla_acknowledgment_due,
                self.level_config.get('reminder_before_days', 2) if self.level_config else 2,
                self.issue.sla_acknowledgment_breached_date
            )

            # Record breach
            if self.issue.sla_acknowledgment_status == "Breached" and not self.issue.sla_acknowledgment_breached_date:
                self.issue.sla_acknowledgment_breached_date = now_datetime()

        # Update resolution SLA status
        if self.issue.status not in ['Resolved', 'Closed']:
            self.issue.sla_resolution_status = self._calculate_sla_status(
                self.issue.sla_resolution_due,
                self.level_config.get('reminder_before_days', 2) if self.level_config else 2,
                self.issue.sla_resolution_breached_date
            )

            # Record breach
            if self.issue.sla_resolution_status == "Breached" and not self.issue.sla_resolution_breached_date:
                self.issue.sla_resolution_breached_date = now_datetime()

        # Update days remaining
        self.update_days_remaining()

    def _calculate_sla_status(self, due_date, reminder_days, breach_date):
        """Calculate SLA status (On Time, Nearing Due, Breached)"""
        if breach_date:
            return "Breached"

        today = getdate(nowdate())
        due = getdate(due_date)
        days_until_due = date_diff(due, today)

        if days_until_due < 0:
            return "Breached"
        elif days_until_due <= reminder_days:
            return "Nearing Due"
        else:
            return "On Time"

    def update_days_remaining(self):
        """Calculate and update days remaining for resolution SLA"""
        if not self.issue.sla_resolution_due:
            return

        today = getdate(nowdate())
        due = getdate(self.issue.sla_resolution_due)
        self.issue.sla_days_remaining = date_diff(due, today)

    def check_and_escalate(self):
        """
        Check if SLA is breached and escalate if configured
        Called from scheduled job
        """
        # Only escalate if resolution SLA is breached
        if self.issue.sla_resolution_status != "Breached":
            return False

        # Check if auto-escalate is enabled
        if not self.level_config or not self.level_config.get('auto_escalate'):
            return False

        # Don't escalate if already resolved/closed
        if self.issue.status in ['Resolved', 'Closed']:
            return False

        # Perform escalation
        return self.escalate_to_parent_level()

    def escalate_to_parent_level(self):
        """
        Escalate issue to parent administrative region
        Returns True if escalated, False if no parent exists
        """
        current_region = frappe.get_doc("GRM Administrative Region", self.issue.administrative_region)

        if not current_region.parent_region:
            # Already at highest level, cannot escalate further
            frappe.log_error(
                f"Cannot escalate {self.issue.name} - already at highest level",
                "SLA Escalation Error"
            )
            return False

        # Store old region for reference
        old_region = self.issue.administrative_region

        # Update to parent region
        self.issue.administrative_region = current_region.parent_region

        # Recalculate SLA with new level's configuration
        self.initialize_sla()

        # Update escalation tracking
        self.issue.escalation_count = (self.issue.escalation_count or 0) + 1
        self.issue.last_escalated_date = now_datetime()
        self.issue.escalation_reason = f"SLA breach - escalated from {old_region} to {current_region.parent_region}"

        # Add comment
        self.issue.add_comment(
            "Info",
            f"Issue auto-escalated to {current_region.parent_region} due to SLA breach"
        )

        # Save issue
        self.issue.save(ignore_permissions=True)

        # Send escalation notification
        self.issue.send_escalation_notification()

        frappe.logger().info(f"Escalated {self.issue.name} from {old_region} to {current_region.parent_region}")

        return True

    def should_send_reminder(self):
        """
        Check if reminder notification should be sent
        Returns: (bool, str) - (should_send, reminder_type)
        """
        if not self.level_config:
            return False, None

        reminder_days = self.level_config.get('reminder_before_days', 2)
        today = getdate(nowdate())

        # Check acknowledgment reminder
        if self.issue.status not in ['Acknowledged', 'In Progress', 'Resolved', 'Closed']:
            ack_due = getdate(self.issue.sla_acknowledgment_due)
            days_until_ack = date_diff(ack_due, today)

            if days_until_ack == reminder_days:
                return True, 'acknowledgment'

        # Check resolution reminder
        if self.issue.status not in ['Resolved', 'Closed']:
            res_due = getdate(self.issue.sla_resolution_due)
            days_until_res = date_diff(res_due, today)

            if days_until_res == reminder_days:
                return True, 'resolution'

        return False, None


# Utility Functions

def add_business_days(start_date, days):
    """
    Add business days to a date (excluding weekends)

    Args:
        start_date: Starting date
        days: Number of business days to add

    Returns:
        Date after adding business days
    """
    current = getdate(start_date)
    added = 0

    while added < days:
        current = add_days(current, 1)
        # Skip weekends (5=Saturday, 6=Sunday)
        if current.weekday() not in [5, 6]:
            added += 1

    return current


@frappe.whitelist()
def get_sla_dashboard_data(project=None, filters=None):
    """
    Get SLA dashboard data for reporting

    Args:
        project: Optional project filter
        filters: Optional additional filters

    Returns:
        Dict with SLA statistics
    """
    conditions = ["1=1"]
    values = {}

    if project:
        conditions.append("project = %(project)s")
        values['project'] = project

    if filters:
        filters = json.loads(filters) if isinstance(filters, str) else filters
        # Add filter conditions as needed

    query = f"""
        SELECT
            COUNT(*) as total_issues,
            SUM(CASE WHEN sla_acknowledgment_status = 'On Time' THEN 1 ELSE 0 END) as ack_on_time,
            SUM(CASE WHEN sla_acknowledgment_status = 'Nearing Due' THEN 1 ELSE 0 END) as ack_nearing,
            SUM(CASE WHEN sla_acknowledgment_status = 'Breached' THEN 1 ELSE 0 END) as ack_breached,
            SUM(CASE WHEN sla_resolution_status = 'On Time' THEN 1 ELSE 0 END) as res_on_time,
            SUM(CASE WHEN sla_resolution_status = 'Nearing Due' THEN 1 ELSE 0 END) as res_nearing,
            SUM(CASE WHEN sla_resolution_status = 'Breached' THEN 1 ELSE 0 END) as res_breached,
            AVG(escalation_count) as avg_escalations,
            SUM(CASE WHEN escalation_count > 0 THEN 1 ELSE 0 END) as escalated_issues
        FROM `tabGRM Issue`
        WHERE {' AND '.join(conditions)}
            AND status NOT IN ('Resolved', 'Closed')
    """

    result = frappe.db.sql(query, values, as_dict=True)[0]

    return {
        "total_active_issues": result.total_issues or 0,
        "acknowledgment": {
            "on_time": result.ack_on_time or 0,
            "nearing_due": result.ack_nearing or 0,
            "breached": result.ack_breached or 0
        },
        "resolution": {
            "on_time": result.res_on_time or 0,
            "nearing_due": result.res_nearing or 0,
            "breached": result.res_breached or 0
        },
        "escalation": {
            "average_escalations": round(result.avg_escalations or 0, 2),
            "total_escalated": result.escalated_issues or 0
        }
    }
```

### Verification

- [ ] SLAManager can be imported successfully
- [ ] initialize_sla() calculates correct due dates
- [ ] update_sla_status() correctly identifies Breached/Nearing Due
- [ ] escalate_to_parent_level() moves to correct parent
- [ ] add_business_days() skips weekends correctly
- [ ] get_sla_dashboard_data() returns valid statistics

---

## Task 8: Integrate SLA Manager with GRM Issue Lifecycle

**File**: `egrm/egrm/doctype/grm_issue/grm_issue.py`

### Objective

Integrate SLA Manager into GRM Issue document lifecycle hooks to automatically manage SLA tracking.

### Implementation

Update the `GRMIssue` class:

```python
import frappe
from frappe import _
from frappe.model.document import Document
from egrm.egrm.utils.sla_manager import SLAManager

class GRMIssue(Document):

    def after_insert(self):
        """Initialize SLA and send receipt after creation"""
        # Initialize SLA tracking
        sla_manager = SLAManager(self)
        sla_manager.initialize_sla()
        self.save(ignore_permissions=True)  # Save SLA fields

        # Send receipt notification
        self.send_notification('receipt')

    def on_update(self):
        """Handle updates to issue"""
        # Check for administrative region change
        if self.has_value_changed('administrative_region'):
            sla_manager = SLAManager(self)
            sla_manager.initialize_sla()  # Recalculate SLA
            self.add_comment("Info", f"SLA recalculated due to region change to {self.administrative_region}")

        # Update SLA status
        sla_manager = SLAManager(self)
        sla_manager.update_sla_status()

        # Handle status change notifications
        if self.has_value_changed('status'):
            self.handle_status_change_notification()

            # Check if status change resolves SLA
            if self.status == 'Acknowledged' and self.sla_acknowledgment_status != 'Breached':
                self.sla_acknowledgment_status = 'Completed'

            if self.status in ['Resolved', 'Closed'] and self.sla_resolution_status != 'Breached':
                self.sla_resolution_status = 'Completed'

    def validate(self):
        """Validation before save"""
        # Existing validation...

        # Ensure resolution date is set when status is Resolved
        if self.status == 'Resolved' and not self.resolution_date:
            self.resolution_date = frappe.utils.nowdate()

        # Ensure acknowledgment date is set when status is Acknowledged
        if self.status == 'Acknowledged' and not self.acknowledgment_date:
            self.acknowledgment_date = frappe.utils.nowdate()

    # ... notification methods from Task 4 ...

    @frappe.whitelist()
    def manual_escalate(self, reason=None):
        """Allow manual escalation (called from UI)"""
        if not frappe.has_permission(self.doctype, "write", self.name):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

        sla_manager = SLAManager(self)

        if sla_manager.escalate_to_parent_level():
            if reason:
                self.escalation_reason = reason
            else:
                self.escalation_reason = "Manual escalation by user"

            self.save()
            frappe.msgprint(_("Issue escalated successfully"))
            return True
        else:
            frappe.msgprint(_("Cannot escalate - already at highest level"))
            return False
```

### Update JS Controller

Add manual escalation button in `grm_issue.js`:

```javascript
frappe.ui.form.on('GRM Issue', {
    refresh: function(frm) {
        // Existing refresh logic...

        // Add manual escalate button
        if (!frm.is_new() && frm.doc.status not in ['Resolved', 'Closed']) {
            frm.add_custom_button(__('Escalate to Higher Level'), function() {
                show_escalate_dialog(frm);
            }, __('Actions'));
        }

        // Color-code SLA status fields
        color_code_sla_status(frm);
    }
});

function show_escalate_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Escalate Issue'),
        fields: [
            {
                fieldname: 'reason',
                label: __('Escalation Reason'),
                fieldtype: 'Small Text',
                reqd: 1,
                description: __('Provide reason for manual escalation')
            }
        ],
        primary_action_label: __('Escalate'),
        primary_action: function(values) {
            frappe.call({
                method: 'manual_escalate',
                doc: frm.doc,
                args: {
                    reason: values.reason
                },
                callback: function(r) {
                    if (r.message) {
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    d.show();
}

function color_code_sla_status(frm) {
    // Color acknowledgment status
    if (frm.doc.sla_acknowledgment_status) {
        let color = get_sla_color(frm.doc.sla_acknowledgment_status);
        frm.fields_dict.sla_acknowledgment_status.$wrapper.css('color', color);
    }

    // Color resolution status
    if (frm.doc.sla_resolution_status) {
        let color = get_sla_color(frm.doc.sla_resolution_status);
        frm.fields_dict.sla_resolution_status.$wrapper.css('color', color);
    }
}

function get_sla_color(status) {
    const color_map = {
        'On Time': '#28a745',      // Green
        'Nearing Due': '#ffc107',  // Yellow
        'Breached': '#dc3545',     // Red
        'Completed': '#6c757d'     // Gray
    };
    return color_map[status] || '#000';
}
```

### Verification

- [ ] SLA initialized automatically on issue creation
- [ ] SLA recalculated when administrative region changes
- [ ] SLA status updates on each save
- [ ] Status changes trigger appropriate SLA completions
- [ ] Manual escalate button works from UI
- [ ] SLA status fields color-coded correctly
- [ ] Comments logged for escalations and region changes

---

## Task 9: Create Scheduled Job for SLA Monitoring

**File**: `egrm/egrm/scheduled_jobs/sla_monitor.py`

### Objective

Create a scheduled job that runs daily to check all active issues, update SLA status, send reminders, and trigger auto-escalation.

### Implementation

Create the scheduler module:

```python
"""
SLA Monitoring Scheduler

Runs daily to:
1. Update SLA status for all active issues
2. Send reminder notifications
3. Auto-escalate breached issues
"""

import frappe
from frappe import _
from frappe.utils import nowdate, get_datetime
from egrm.egrm.utils.sla_manager import SLAManager


def monitor_sla():
    """
    Main scheduled function to monitor SLA for all active issues
    Runs daily via hooks.py scheduler configuration
    """
    frappe.logger().info("Starting SLA monitoring job...")

    # Get all active issues (not resolved/closed)
    active_issues = frappe.get_all(
        "GRM Issue",
        filters={
            "status": ["not in", ["Resolved", "Closed"]],
            "sla_resolution_due": ["is", "set"]
        },
        pluck="name"
    )

    stats = {
        "processed": 0,
        "reminders_sent": 0,
        "escalated": 0,
        "errors": 0
    }

    for issue_name in active_issues:
        try:
            process_issue_sla(issue_name, stats)
            stats["processed"] += 1
        except Exception as e:
            stats["errors"] += 1
            frappe.log_error(
                f"SLA monitoring error for {issue_name}: {str(e)}",
                "SLA Monitor Error"
            )

    # Log summary
    frappe.logger().info(
        f"SLA monitoring completed: {stats['processed']} processed, "
        f"{stats['reminders_sent']} reminders, {stats['escalated']} escalated, "
        f"{stats['errors']} errors"
    )

    # Create summary notification for admins (optional)
    if stats["escalated"] > 0 or stats["errors"] > 0:
        notify_admins_sla_summary(stats)

    frappe.db.commit()


def process_issue_sla(issue_name, stats):
    """Process SLA for a single issue"""
    issue = frappe.get_doc("GRM Issue", issue_name)
    sla_manager = SLAManager(issue)

    # Update SLA status
    sla_manager.update_sla_status()

    # Check if reminder should be sent
    should_remind, reminder_type = sla_manager.should_send_reminder()
    if should_remind:
        issue.send_notification('sla_reminder')
        stats["reminders_sent"] += 1
        frappe.logger().info(f"SLA reminder sent for {issue_name} ({reminder_type})")

    # Check and perform escalation if needed
    if sla_manager.check_and_escalate():
        stats["escalated"] += 1
        frappe.logger().info(f"Issue {issue_name} auto-escalated due to SLA breach")

    # Save updated SLA fields
    issue.save(ignore_permissions=True)


def notify_admins_sla_summary(stats):
    """Send summary notification to GRM admins"""
    subject = f"SLA Monitoring Summary - {nowdate()}"

    message = f"""
    <h3>GRM SLA Monitoring Daily Summary</h3>
    <ul>
        <li><strong>Issues Processed:</strong> {stats['processed']}</li>
        <li><strong>Reminders Sent:</strong> {stats['reminders_sent']}</li>
        <li><strong>Auto-Escalated:</strong> {stats['escalated']}</li>
        <li><strong>Errors:</strong> {stats['errors']}</li>
    </ul>

    <p>Review issues with breached SLAs in the GRM Issue list.</p>
    """

    # Get users with GRM Administrator role
    admins = frappe.get_all(
        "Has Role",
        filters={"role": "GRM Administrator"},
        pluck="parent"
    )

    if admins:
        frappe.sendmail(
            recipients=admins,
            subject=subject,
            message=message
        )


def generate_sla_report():
    """
    Generate weekly SLA performance report
    Runs weekly via hooks.py scheduler
    """
    frappe.logger().info("Generating weekly SLA report...")

    from egrm.egrm.utils.sla_manager import get_sla_dashboard_data

    # Get all projects
    projects = frappe.get_all("GRM Project", filters={"active": 1}, pluck="name")

    report_data = []
    for project in projects:
        project_stats = get_sla_dashboard_data(project=project)
        project_stats['project'] = project
        report_data.append(project_stats)

    # Send report to project managers
    send_sla_report_email(report_data)

    frappe.db.commit()


def send_sla_report_email(report_data):
    """Send weekly SLA report to project managers"""
    subject = f"Weekly GRM SLA Performance Report - {nowdate()}"

    # Build HTML report
    message = "<h2>Weekly SLA Performance Report</h2>"

    for data in report_data:
        message += f"""
        <h3>{data['project']}</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr>
                <th>Metric</th>
                <th>On Time</th>
                <th>Nearing Due</th>
                <th>Breached</th>
            </tr>
            <tr>
                <td>Acknowledgment SLA</td>
                <td>{data['acknowledgment']['on_time']}</td>
                <td>{data['acknowledgment']['nearing_due']}</td>
                <td>{data['acknowledgment']['breached']}</td>
            </tr>
            <tr>
                <td>Resolution SLA</td>
                <td>{data['resolution']['on_time']}</td>
                <td>{data['resolution']['nearing_due']}</td>
                <td>{data['resolution']['breached']}</td>
            </tr>
        </table>
        <p><strong>Total Active Issues:</strong> {data['total_active_issues']}</p>
        <p><strong>Escalated Issues:</strong> {data['escalation']['total_escalated']}</p>
        <br>
        """

    # Get project managers
    pms = frappe.get_all(
        "Has Role",
        filters={"role": "GRM Project Manager"},
        pluck="parent"
    )

    if pms:
        frappe.sendmail(
            recipients=pms,
            subject=subject,
            message=message
        )
```

### Register Schedulers in hooks.py

Add to `egrm/hooks.py`:

```python
# Scheduled Tasks
scheduler_events = {
    # ... existing schedulers ...

    # SLA Monitoring (runs daily at 2 AM)
    "daily": [
        "egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla"
    ],

    # SLA Report (runs weekly on Monday at 8 AM)
    "weekly": [
        "egrm.egrm.scheduled_jobs.sla_monitor.generate_sla_report"
    ]
}
```

### Verification

- [ ] Scheduler registered in hooks.py
- [ ] Can manually run: `bench execute egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla`
- [ ] SLA status updated for all active issues
- [ ] Reminders sent when due
- [ ] Auto-escalation triggered for breached issues
- [ ] Error logging works
- [ ] Admin summary email sent
- [ ] Weekly report generates and sends

---

## Task 10: Configure Frappe Notifications for SLA Alerts

**Location**: Frappe UI → Settings → Notification

### Objective

Create Frappe Notification documents to alert assignees when their issues are nearing SLA deadlines or have been escalated.

### Notification 1: SLA Nearing Due Alert

**Create via UI:**

```
Notification Name: GRM SLA Nearing Due - Assignee Alert
Document Type: GRM Issue
Event: Value Change
Value Changed: sla_resolution_status

Condition: doc.sla_resolution_status == "Nearing Due"

Recipients:
  ☑ Field: assignee

Subject: SLA Alert: {{ doc.tracking_code }} nearing deadline

Message:
Your assigned complaint {{ doc.tracking_code }} is nearing the SLA deadline.

Subject: {{ doc.subject }}
Days Remaining: {{ doc.sla_days_remaining }}
Resolution Due: {{ frappe.utils.formatdate(doc.sla_resolution_due, "dd MMM yyyy") }}

Please take action to resolve before the deadline.

View Issue: {{ frappe.utils.get_url_to_form("GRM Issue", doc.name) }}

Enabled: ☑
```

### Notification 2: SLA Breached Alert

```
Notification Name: GRM SLA Breached - Escalation Alert
Document Type: GRM Issue
Event: Value Change
Value Changed: sla_resolution_status

Condition: doc.sla_resolution_status == "Breached"

Recipients:
  ☑ Field: assignee
  ☑ Role: GRM Project Manager

Subject: URGENT: SLA Breached - {{ doc.tracking_code }}

Message:
⚠️ SLA BREACH ALERT ⚠️

Complaint {{ doc.tracking_code }} has breached the resolution SLA.

Subject: {{ doc.subject }}
Resolution Due: {{ frappe.utils.formatdate(doc.sla_resolution_due, "dd MMM yyyy") }}
Days Overdue: {{ abs(doc.sla_days_remaining) }}

IMMEDIATE ACTION REQUIRED

View Issue: {{ frappe.utils.get_url_to_form("GRM Issue", doc.name) }}

Enabled: ☑
```

### Notification 3: Issue Escalated Alert

```
Notification Name: GRM Issue Escalated
Document Type: GRM Issue
Event: Value Change
Value Changed: escalation_count

Condition: doc.escalation_count > 0

Recipients:
  ☑ Field: assignee
  ☑ Role: GRM Department Head

Subject: Issue Escalated: {{ doc.tracking_code }}

Message:
Issue {{ doc.tracking_code }} has been escalated to your administrative level.

Previous Region: {{ doc.escalation_reason }}
Current Region: {{ doc.administrative_region }}
Escalation Count: {{ doc.escalation_count }}

Subject: {{ doc.subject }}
Status: {{ doc.status }}
Resolution Due: {{ frappe.utils.formatdate(doc.sla_resolution_due, "dd MMM yyyy") }}

Please review and take ownership.

View Issue: {{ frappe.utils.get_url_to_form("GRM Issue", doc.name) }}

Enabled: ☑
```

### Implementation Steps

1. **Create Notifications via UI**:
   ```
   Go to: Desk → Settings → Notification → New
   - Create each notification above
   - Test with sample GRM Issue
   ```

2. **Export as Fixtures** (optional):
   ```python
   # In hooks.py
   fixtures = [
       # ... existing fixtures ...
       {
           "dt": "Notification",
           "filters": [["name", "in", [
               "GRM SLA Nearing Due - Assignee Alert",
               "GRM SLA Breached - Escalation Alert",
               "GRM Issue Escalated"
           ]]]
       }
   ]
   ```

3. **Test Notifications**:
   - Create test issue
   - Manually update sla_resolution_status to "Nearing Due"
   - Check email sent
   - Update to "Breached"
   - Check escalation email

### Verification

- [ ] All 3 notifications created in Frappe
- [ ] Conditions trigger correctly
- [ ] Recipients receive emails
- [ ] Email formatting looks good
- [ ] Links in emails work
- [ ] Can be exported as fixtures

---

## Task 11: Add Resolution Agreement File Upload

**File**: `egrm/egrm/doctype/grm_issue/grm_issue.json`

### Objective

Add fields to upload and track signed resolution agreements (per WB requirement for documenting resolutions).

### Fields to Add

Add in the existing "Resolution Details" section:

```json
{
  "fieldname": "resolution_agreement",
  "label": "Resolution Agreement (Signed)",
  "fieldtype": "Attach",
  "depends_on": "eval:doc.status=='Resolved'",
  "description": "Upload signed resolution agreement document (PDF, image, etc.)"
},
{
  "fieldname": "resolution_agreement_date",
  "label": "Agreement Signed Date",
  "fieldtype": "Date",
  "depends_on": "eval:doc.resolution_agreement"
},
{
  "fieldname": "cb_res_agreement",
  "fieldtype": "Column Break"
},
{
  "fieldname": "resolution_agreement_parties",
  "label": "Agreement Parties",
  "fieldtype": "Small Text",
  "depends_on": "eval:doc.resolution_agreement",
  "description": "Names of parties who signed the agreement"
},
{
  "fieldname": "resolution_agreement_notes",
  "label": "Agreement Notes",
  "fieldtype": "Text",
  "depends_on": "eval:doc.resolution_agreement",
  "description": "Additional notes about the resolution agreement"
}
```

### Update Python Controller

Add validation for resolution agreements in `grm_issue.py`:

```python
def validate(self):
    # Existing validation...

    # Validate resolution agreement
    if self.status == 'Resolved':
        if self.resolution_agreement and not self.resolution_agreement_date:
            # Auto-set agreement date to today if not provided
            self.resolution_agreement_date = frappe.utils.nowdate()

    # Ensure agreement fields only populated when resolved
    if self.status != 'Resolved':
        if self.resolution_agreement:
            frappe.throw(_("Resolution agreement can only be uploaded for Resolved issues"))
```

### Update JS Controller

Add file upload helper in `grm_issue.js`:

```javascript
frappe.ui.form.on('GRM Issue', {
    refresh: function(frm) {
        // Existing refresh logic...

        // Show resolution agreement section when resolved
        if (frm.doc.status == 'Resolved' && !frm.doc.resolution_agreement) {
            frm.add_custom_button(__('Upload Resolution Agreement'), function() {
                show_agreement_upload_dialog(frm);
            }, __('Actions'));
        }
    },

    resolution_agreement: function(frm) {
        // Auto-populate agreement date when file uploaded
        if (frm.doc.resolution_agreement && !frm.doc.resolution_agreement_date) {
            frm.set_value('resolution_agreement_date', frappe.datetime.get_today());
        }
    }
});

function show_agreement_upload_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Upload Resolution Agreement'),
        fields: [
            {
                fieldname: 'agreement_file',
                label: __('Agreement Document'),
                fieldtype: 'Attach',
                reqd: 1
            },
            {
                fieldname: 'agreement_date',
                label: __('Signed Date'),
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'parties',
                label: __('Signing Parties'),
                fieldtype: 'Small Text',
                description: __('List the names of all parties who signed')
            },
            {
                fieldname: 'notes',
                label: __('Notes'),
                fieldtype: 'Text'
            }
        ],
        primary_action_label: __('Upload'),
        primary_action: function(values) {
            frm.set_value('resolution_agreement', values.agreement_file);
            frm.set_value('resolution_agreement_date', values.agreement_date);
            frm.set_value('resolution_agreement_parties', values.parties);
            frm.set_value('resolution_agreement_notes', values.notes);
            frm.save();
            d.hide();
        }
    });
    d.show();
}
```

### Verification

- [ ] Resolution agreement fields appear when status is Resolved
- [ ] Can upload file via Attach field
- [ ] Agreement date auto-populated on upload
- [ ] Validation prevents agreement on non-Resolved issues
- [ ] Upload dialog helper works
- [ ] Uploaded file accessible and downloadable

---

## Task 12: Documentation and Admin Guides

**Files**: Create comprehensive documentation for Phase 3 features

### Documentation Files to Create

#### 1. Admin Guide: Notification Configuration

**File**: `egrm/docs/admin-guides/notification-configuration.md`

```markdown
# GRM Notification Configuration Guide

## Overview

This guide explains how to configure automated notifications for your GRM project.

## Prerequisites

- GRM Project created
- Email/SMS settings configured in Frappe
- Email Templates created

## Step 1: Create Notification Templates

1. Go to **eGRM → GRM Notification Template → New**
2. Fill in:
   - **Template Name**: Unique identifier (e.g., "Project A Receipt")
   - **Template Type**: Select type (Receipt, Acknowledgment, etc.)
   - **Email Template**: Link to Frappe Email Template
   - **Enable SMS**: Check if SMS needed
   - **SMS Message**: Enter Jinja2 template (e.g., `Your complaint {{ tracking_code }} received`)
   - **Project**: Leave blank for shared, or select project for project-specific

3. Save

### Available Template Variables

Use these in SMS messages:
- `{{ tracking_code }}` - Issue tracking code
- `{{ subject }}` - Issue subject
- `{{ status }}` - Current status
- `{{ administrative_region }}` - Region name
- `{{ complainant_name }}` - Complainant name
- `{{ sla_acknowledgment_due }}` - Acknowledgment deadline
- `{{ sla_resolution_due }}` - Resolution deadline

## Step 2: Configure Project Notifications

1. Go to **GRM Project → [Your Project] → Edit**
2. Expand **Notification Settings** section
3. Check **Enable Automated Notifications**
4. Select templates for each event:
   - Receipt Template
   - Acknowledgment Template
   - In Progress Template
   - Resolved Template
   - Closed Template
   - Escalated Template
   - SLA Reminder Template

5. Save

## Step 3: Test Notifications

1. Create a test complaint
2. Check email/SMS received
3. Change status to Acknowledged
4. Verify acknowledgment notification received

## Troubleshooting

**No emails sent:**
- Check Email Account configured in Frappe
- Check Email Queue for errors
- Verify template is active
- Ensure complainant_email field populated

**SMS not working:**
- Check SMS Settings in Frappe
- Verify SMS provider credentials
- Check SMS Log for errors

## Best Practices

- Create project-specific templates for custom messaging
- Test templates with sample data before going live
- Monitor Email Queue and Communication logs
- Keep SMS messages under 160 characters
```

#### 2. Admin Guide: SLA Configuration

**File**: `egrm/docs/admin-guides/sla-configuration.md`

```markdown
# GRM SLA Configuration Guide

## Overview

This guide explains how to configure Service Level Agreements (SLAs) for your administrative hierarchy.

## Prerequisites

- Administrative Level Types created
- Administrative Regions created
- Projects configured

## Step 1: Configure SLA per Administrative Level

1. Go to **eGRM → GRM Administrative Level Type → [Level] → Edit**
2. Expand **SLA Configuration** section
3. Set timeframes:
   - **Acknowledgment Days**: Business days to acknowledge (default: 7)
   - **Resolution Days**: Business days to resolve (default: 30)
   - **Reminder Before (Days)**: Days before deadline to send reminder (default: 2)
   - **Auto-Escalate on SLA Breach**: Check to enable automatic escalation

4. Save

### Example Configuration

**Village Level:**
- Acknowledgment: 7 days
- Resolution: 30 days
- Reminder: 2 days before
- Auto-Escalate: Yes

**District Level:**
- Acknowledgment: 5 days
- Resolution: 45 days
- Reminder: 3 days before
- Auto-Escalate: Yes

**Province Level:**
- Acknowledgment: 3 days
- Resolution: 60 days
- Reminder: 5 days before
- Auto-Escalate: No (highest level)

## Step 2: Monitor SLA Compliance

### View SLA Status

1. Go to **GRM Issue List**
2. Add filters:
   - SLA Resolution Status: "Breached"
   - Status: Not in ["Resolved", "Closed"]

3. Review list of breached issues

### SLA Dashboard

Access SLA dashboard data via:
```python
bench execute egrm.egrm.utils.sla_manager.get_sla_dashboard_data --kwargs "{'project': 'Project Name'}"
```

## Step 3: Handle Escalations

### Automatic Escalation

When SLA is breached and auto-escalate is enabled:
1. Issue moves to parent administrative region
2. SLA recalculated based on new level
3. Escalation notification sent
4. Comment added to issue

### Manual Escalation

1. Open GRM Issue
2. Click **Actions → Escalate to Higher Level**
3. Enter reason
4. Click **Escalate**

## Scheduled Jobs

SLA monitoring runs daily at 2 AM:
- Updates all SLA statuses
- Sends reminder notifications
- Triggers auto-escalation

To run manually:
```bash
bench execute egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla
```

## Reports

Weekly SLA report sent every Monday at 8 AM to:
- GRM Project Managers
- GRM Administrators

## Best Practices

- Set realistic SLA timeframes based on capacity
- Enable auto-escalate for all levels except highest
- Monitor breached issues daily
- Review weekly SLA reports
- Adjust timeframes based on actual performance
```

#### 3. Developer Guide: Extending Notifications

**File**: `egrm/docs/developer-guides/extending-notifications.md`

```markdown
# Extending GRM Notifications - Developer Guide

## Adding Custom Notification Types

### 1. Update Template Type Options

Edit `grm_notification_template.json`:

```json
{
  "fieldname": "template_type",
  "options": "Receipt\nAcknowledgment\n...\nYour Custom Type"
}
```

### 2. Add Template Field to GRM Project

Edit `grm_project.json`:

```json
{
  "fieldname": "your_custom_template",
  "label": "Your Custom Template",
  "fieldtype": "Link",
  "options": "GRM Notification Template"
}
```

### 3. Trigger Notification in Code

In `grm_issue.py`:

```python
def your_custom_event_handler(self):
    """Handle your custom event"""
    # Your logic...
    self.send_notification('your_custom')  # Uses 'your_custom_template' from project
```

## Custom SMS Providers

To integrate a custom SMS provider:

### 1. Create SMS Provider Module

```python
# egrm/egrm/utils/custom_sms.py

import frappe
import requests

def send_custom_sms(phone, message):
    """Send SMS via custom provider"""
    settings = frappe.get_single("Your SMS Settings")

    response = requests.post(
        settings.api_url,
        headers={"Authorization": f"Bearer {settings.api_key}"},
        json={"to": phone, "message": message}
    )

    if response.status_code != 200:
        raise Exception(f"SMS send failed: {response.text}")

    return response.json()
```

### 2. Update send_sms_notification

In `grm_issue.py`:

```python
def send_sms_notification(self, template):
    """Send SMS using custom provider"""
    if not self.complainant_phone:
        return

    from egrm.egrm.utils.custom_sms import send_custom_sms

    context = self.get_notification_context()
    sms_message = template.render_sms(context)

    send_custom_sms(self.complainant_phone, sms_message)
```

## Email Customization

### Using Custom Email Templates

Create your own Email Template in Frappe:

```html
<!-- Subject -->
Custom Template: {{ doc.tracking_code }}

<!-- Response HTML -->
<div style="font-family: Arial;">
  <h2>Your Custom Design</h2>
  <p>{{ doc.subject }}</p>

  {% if doc.custom_field %}
    <p>Custom Field: {{ doc.custom_field }}</p>
  {% endif %}
</div>
```

Link from GRM Notification Template → Email Template field.

## Notification Hooks

Add custom logic before/after notification send:

```python
# hooks.py
doc_events = {
    "GRM Issue": {
        "before_notification": "egrm.custom.before_notification_hook",
        "after_notification": "egrm.custom.after_notification_hook"
    }
}
```

```python
# egrm/custom.py
def before_notification_hook(doc, method, notification_type):
    """Called before sending notification"""
    # Custom logic
    pass

def after_notification_hook(doc, method, notification_type):
    """Called after sending notification"""
    # Custom logic (e.g., log to external system)
    pass
```

## Testing Notifications

### Unit Test Example

```python
# egrm/egrm/doctype/grm_issue/test_grm_issue.py

def test_receipt_notification():
    """Test receipt notification sent on issue creation"""

    # Create test project with notification config
    project = frappe.get_doc({
        "doctype": "GRM Project",
        "project_name": "Test Project",
        "enable_notifications": 1,
        "receipt_template": "Test Receipt Template"
    }).insert()

    # Create issue
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": project.name,
        "subject": "Test Issue",
        "complainant_email": "test@example.com"
    }).insert()

    # Check communication created
    comms = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "GRM Issue",
            "reference_name": issue.name
        }
    )

    assert len(comms) > 0, "No communication created"
```

## API Reference

### SLAManager Methods

```python
from egrm.egrm.utils.sla_manager import SLAManager

# Initialize
sla = SLAManager(issue_doc)

# Calculate SLA
sla.initialize_sla()

# Update status
sla.update_sla_status()

# Escalate
sla.escalate_to_parent_level()

# Check reminder
should_send, reminder_type = sla.should_send_reminder()
```

### GRM Issue Notification Methods

```python
# Send specific notification
issue.send_notification('receipt')

# Resend notification
issue.resend_notification('acknowledgment')

# Get context for templates
context = issue.get_notification_context()
```
```

### Verification Checklist

Create `docs/checklists/phase3-admin-checklist.md`:

```markdown
# Phase 3 Admin Setup Checklist

## Email/SMS Configuration
- [ ] Email Account configured in Frappe
- [ ] SMTP settings verified
- [ ] SMS Settings configured (if using SMS)
- [ ] Test email/SMS sent successfully

## Notification Templates
- [ ] Created at least 4 Email Templates (Receipt, Acknowledgment, Resolved, SLA Reminder)
- [ ] Created GRM Notification Templates linking to Email Templates
- [ ] Tested template preview with sample data
- [ ] SMS messages added (if using SMS)

## Project Configuration
- [ ] Enabled notifications for all projects
- [ ] Selected templates for all notification types
- [ ] Verified template selection saved

## SLA Configuration
- [ ] Set SLA timeframes for all Administrative Level Types
- [ ] Configured reminder days
- [ ] Enabled auto-escalate (except highest level)
- [ ] Verified SLA values saved

## Scheduled Jobs
- [ ] Verified scheduler is running (`bench doctor`)
- [ ] Manually triggered SLA monitor job
- [ ] Checked Error Log for scheduler errors

## Frappe Notifications
- [ ] Created "SLA Nearing Due" notification
- [ ] Created "SLA Breached" notification
- [ ] Created "Issue Escalated" notification
- [ ] Tested notifications with sample issue

## Testing
- [ ] Created test issue and verified receipt sent
- [ ] Changed status and verified status notifications
- [ ] Manually escalated issue and verified escalation notification
- [ ] Set issue to breached and verified breach alert
- [ ] Checked Communication and Email Queue logs

## Documentation
- [ ] Read notification configuration guide
- [ ] Read SLA configuration guide
- [ ] Shared guides with team
```

---

## Implementation Timeline

### Week 1: Notification System
- **Days 1-2**: Tasks 1-3 (DocTypes, Templates)
- **Days 3-4**: Task 4 (Notification logic in GRM Issue)
- **Day 5**: Testing and bug fixes

### Week 2: SLA Tracking
- **Days 1-2**: Tasks 5-7 (SLA fields, SLA Manager module)
- **Days 3-4**: Task 8 (Integration with GRM Issue)
- **Day 5**: Task 9 (Scheduled jobs)

### Week 3: Finalization
- **Days 1-2**: Tasks 10-11 (Frappe Notifications, Resolution Agreements)
- **Days 3-4**: Task 12 (Documentation)
- **Day 5**: End-to-end testing and deployment prep

---

## Testing Strategy

Testing covered separately as requested by user.

---

## Dependencies

- **Frappe Framework**: v15+
- **Python**: 3.10+
- **MariaDB**: 10.6+

### Python Libraries
- Standard library only (no additional dependencies)

### Frappe DocTypes Required
- Email Template (core)
- Email Account (core)
- SMS Settings (core)
- Notification (core)
- Communication (core)

---

## Deployment Checklist

### Pre-Deployment
- [ ] All code reviewed and tested
- [ ] Database migrations tested
- [ ] Scheduler jobs tested
- [ ] Email/SMS configured
- [ ] Documentation complete

### Deployment Steps
1. **Backup database**: `bench --site [site] backup`
2. **Pull latest code**: `git pull origin main`
3. **Install dependencies**: `bench setup requirements`
4. **Migrate database**: `bench --site [site] migrate`
5. **Clear cache**: `bench --site [site] clear-cache`
6. **Restart services**: `bench restart`
7. **Verify scheduler**: `bench doctor`

### Post-Deployment
- [ ] Create Email Templates via UI
- [ ] Create GRM Notification Templates
- [ ] Configure projects with templates
- [ ] Set SLA values for administrative levels
- [ ] Create Frappe Notifications
- [ ] Test end-to-end with sample issue
- [ ] Monitor Error Log for 24 hours

---

## Admin Configuration Guide

### Step 1: Email/SMS Setup (One-time)

```bash
# Verify email configured
bench --site [site] console
>>> frappe.get_doc("Email Account", "Notifications").email_id
```

If not configured:
1. Go to **Settings → Email Account → New**
2. Configure SMTP settings
3. Test with "Send Test Email"

### Step 2: Create Email Templates (Per Project)

1. Go to **Setup → Email → Email Template → New**
2. Create templates for:
   - Receipt
   - Acknowledgment
   - Resolution
   - SLA Reminder
3. Use samples from Task 3

### Step 3: Create Notification Templates

1. Go to **eGRM → GRM Notification Template → New**
2. Link Email Templates
3. Add SMS messages if needed

### Step 4: Configure Projects

1. Edit each GRM Project
2. Enable notifications
3. Select templates for each event

### Step 5: Set SLA Values

1. Edit each Administrative Level Type
2. Set acknowledgment/resolution days
3. Enable auto-escalate

### Step 6: Create System Notifications

1. Go to **Settings → Notification → New**
2. Create 3 notifications from Task 10

---

## Success Criteria

Phase 3 is complete when:

✅ **Notification System**
- Automated email/SMS sent on issue creation (receipt)
- Status change notifications sent automatically
- Templates configurable per project
- Multi-channel delivery (email + SMS)

✅ **SLA Tracking**
- SLA calculated based on administrative level
- SLA status tracked (On Time, Nearing Due, Breached)
- Reminders sent before deadline
- Auto-escalation on breach
- Manual escalation available

✅ **Resolution Agreements**
- File upload for signed agreements
- Agreement metadata tracked
- Agreements linked to resolved issues

✅ **Documentation**
- Admin guides complete
- Developer guides complete
- Setup checklists available
- Troubleshooting guides included

✅ **Testing**
- All notification types tested
- SLA calculation verified
- Escalation logic tested
- Scheduled jobs running
- End-to-end workflow validated

---

## Support and Troubleshooting

### Common Issues

**Issue**: Notifications not sending
- **Solution**: Check Email Queue (`Communication` doctype), verify Email Account settings

**Issue**: SLA not calculating
- **Solution**: Check Administrative Level Type has SLA values set, verify region assigned to issue

**Issue**: Auto-escalation not working
- **Solution**: Verify scheduler running (`bench doctor`), check auto_escalate enabled on level

**Issue**: SMS not sending
- **Solution**: Check SMS Settings, verify SMS provider credentials, check SMS Log

### Logs to Check

- **Error Log**: Desktop → Error Log
- **Email Queue**: Desktop → Communication (filter by Status)
- **Scheduler Log**: `bench --site [site] show-log scheduler`
- **SLA Monitor Log**: Check Error Log for "SLA Monitor Error"

### Getting Help

- Review documentation in `egrm/docs/`
- Check Error Log for detailed stack traces
- Run manual tests with sample data
- Contact development team with Error Log excerpts

---

**End of Phase 3 Implementation Plan**

**Next Steps**: Review all three phase plans, prepare development environment, begin Phase 1 execution.
