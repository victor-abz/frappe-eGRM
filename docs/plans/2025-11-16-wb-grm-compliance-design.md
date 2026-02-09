# World Bank GRM Compliance - Implementation Design

**Project:** eGRM Electronic Grievance Redress Mechanism
**Design Date:** 2025-11-16
**Based On:** World Bank GRM Customization Questionnaire + WB Approach to Grievance Redress
**QA Assessment:** docs/qa-reports/2025-11-16-wb-grm-compliance-assessment.md
**Version:** 1.0

---

## Executive Summary

This design addresses the **critical compliance gaps** identified in the QA assessment to meet World Bank GRM standards. The implementation focuses on four key areas:

1. **Public Transparency & Reporting** (CRITICAL - 20% compliance gap)
2. **Automated Public Reporting** (CRITICAL)
3. **Citizen Receipt & Process Roadmap** (HIGH)
4. **SLA Tracking & Workflow Enhancements** (MEDIUM)

**Design Principles:**
- Leverage Frappe's standard features (Notifications, Auto Email Reports, www/ pages)
- Minimal custom code - reuse existing infrastructure
- Multi-project support - each project configures independently
- Clean separation of concerns - dedicated modules for complex logic
- No redundant data structures - use existing fields where possible

**Current Compliance:** 68%
**Target After Phase 1:** 85%+
**Estimated Effort:** 6-8 weeks with 2 developers

---

## 1. Public Transparency Architecture

### Problem Statement

**WB Requirement (WB Approach p.4):**
> "All complaints are logged in writing and maintained in a database—either a simple Excel file or **a publicly accessible web site** (with appropriate steps taken to preserve anonymity)."

**Current Gap:** All APIs require authentication. No public-facing dashboard or data access.

### Solution Overview

Create public web pages and guest-accessible APIs using Frappe's `www/` directory and `@frappe.whitelist(allow_guest=True)`.

### Components

#### 1.1 Public Metrics API

**File:** `egrm/api/public_metrics.py`

**Purpose:** Provide anonymized aggregate statistics without authentication

**Features:**
- `@frappe.whitelist(allow_guest=True)` for guest access
- Returns only aggregate data (no PII)
- Filters: project, date range, region
- Reuses existing stats logic from `stats.py` with anonymization wrapper

**Example Endpoint:**
```python
@frappe.whitelist(allow_guest=True)
def get_public_dashboard(project_id=None, date_range=None):
    """
    Returns anonymized public metrics
    - Total complaints received/resolved/pending
    - Breakdown by category (anonymized)
    - Regional distribution (aggregate only)
    - Monthly/quarterly trends
    """
```

**Security:**
- No citizen names, contact info, or assignee details
- No individual complaint data
- Only aggregate counts and percentages

#### 1.2 Public Tracking API

**File:** `egrm/api/public_tracking.py`

**Purpose:** Allow citizens to track complaints by tracking code

**Features:**
- Lookup by tracking code only (no auth required)
- Returns: status, submission date, expected resolution date, current workflow stage
- Does NOT expose: contact info, assignee, internal notes

**Example Endpoint:**
```python
@frappe.whitelist(allow_guest=True)
def track_complaint(tracking_code):
    """
    Returns public complaint status
    - Status name
    - Submission date
    - Expected resolution date
    - Appeal status (if applicable)
    """
```

#### 1.3 Public Web Pages

**Structure:**
```
egrm/www/grm-public/
├── index.html                  # Public GRM homepage
├── index.py                    # Dynamic context
├── dashboard/
│   ├── index.html              # Public metrics dashboard
│   └── index.py                # Fetch public metrics
├── track-complaint/
│   ├── index.html              # Track by code interface
│   └── index.py                # Handle tracking queries
├── submit-grievance/
│   ├── index.html              # Web submission form
│   └── index.py                # Handle submissions
└── reports/
    ├── index.html              # Historical report archive
    └── index.py                # List public reports
```

**Implementation Pattern (per Frappe docs):**

Each page pair (HTML + Python):
- `.html` - Jinja template extending `templates/web.html`
- `.py` - `get_context(context)` function for dynamic data
- Python uses `@frappe.whitelist(allow_guest=True)` APIs

**Example - Track Complaint:**

`track-complaint/index.html`:
```html
{% extends "templates/web.html" %}

{% block page_content %}
<div class="container">
    <h1>Track Your Complaint</h1>
    <input type="text" id="tracking_code" placeholder="Enter tracking code">
    <button onclick="trackComplaint()">Track</button>
    <div id="result"></div>
</div>

<script>
function trackComplaint() {
    const code = document.getElementById('tracking_code').value;
    frappe.call({
        method: 'egrm.api.public_tracking.track_complaint',
        args: { tracking_code: code },
        callback: function(r) {
            // Display result
        }
    });
}
</script>
{% endblock %}
```

#### 1.4 Optional Web Submission Form

**Features:**
- Simple HTML form at `/grm-public/submit-grievance`
- Optional email/phone OTP verification (to prevent spam)
- Creates GRM Issue via public API
- Sends tracking code to submitter

**Accessibility:**
- No smartphone required
- Low-bandwidth friendly
- Accessible to citizens without mobile app

---

## 2. Automated Public Reporting

### Problem Statement

**WB Requirement (WB Approach p.6):**
> "The client should provide **regular (monthly or quarterly) reports to the public** that track the # complaints received, resolved, not resolved, and referred to a third party."

**Current Gap:** No automated public reporting mechanism.

### Solution Overview

Use Frappe's **Auto Email Report** feature (standard functionality) to automatically generate and distribute reports on schedule.

### Components

#### 2.1 Script Reports

Create two Frappe Script Reports:

**Report 1: GRM Public Monthly Report**
```
egrm/egrm/report/grm_public_monthly_report/
├── __init__.py
├── grm_public_monthly_report.json      # Metadata
├── grm_public_monthly_report.py        # Report logic
└── grm_public_monthly_report.js        # Filters
```

**Report 2: GRM Public Quarterly Report**
```
egrm/egrm/report/grm_public_quarterly_report/
├── __init__.py
├── grm_public_quarterly_report.json
├── grm_public_quarterly_report.py
└── grm_public_quarterly_report.js
```

**Report Structure:**

```python
def execute(filters=None):
    """
    Main execution function

    Returns:
        columns: Report columns
        data: Report rows (anonymized)
        chart: Trend visualizations
        report_summary: Key metrics cards
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    report_summary = get_report_summary(data)

    return columns, data, None, chart, report_summary
```

**Summary Cards:**
- Total Complaints Received
- Total Resolved
- Total Pending
- Total Referred to Third Party (Appeals)
- Average Resolution Time

**Charts:**
- Line chart: Complaints received vs resolved over time
- Bar chart: Breakdown by category
- Pie chart: Regional distribution

**Data Rows:**
- Anonymized statistics by category/region/status
- No personal identifiable information

#### 2.2 Auto Email Report Configuration

**Setup:** Administrators create Auto Email Report documents via Frappe UI

**Navigation:** Home > Settings > Auto Email Report > New

**Configuration Example (Monthly):**

```
Report: GRM Public Monthly Report
User: Administrator
Enabled: ✓
Send If Data: ✓

Filters:
  - Project: [Selected Project]
  - Date Range: Last Month

Email To:
  - publicreports@project.example.com
  - stakeholders@worldbank.org
  - community@project.gov

Frequency: Monthly
Send Attachments: ✓
Format: XLSX ✓, PDF ✓

Message:
"This is the monthly GRM public transparency report for [Project Name].
Visit https://[site]/grm-public/dashboard for more information."

No of Rows: 500
```

**Per-Project Setup:**
- Each project creates its own Auto Email Report documents
- Configures recipients, frequency, format
- Tests with "Send Now" button before enabling

#### 2.3 Public Report Archive

**Web Page:** `egrm/www/grm-public/reports/index.html`

**Purpose:** Public archive of historical reports

**Features:**
- Lists all generated monthly/quarterly reports
- Downloadable PDFs (stored in public files folder)
- Filterable by project, date
- No authentication required

**Implementation Options:**

**Option A:** Manual upload workflow
- Admin manually uploads final PDFs to public folder after generation
- Web page lists files in folder

**Option B:** Automated with hook (future enhancement)
- Hook into File DocType `after_insert` event
- Detect when Auto Email Report generates PDF
- Copy to public folder automatically

**Recommendation:** Start with Option A (manual), upgrade to Option B if needed.

---

## 3. Receipt & Process Roadmap System

### Problem Statement

**WB Requirement (WB Approach p.4):**
> "Complainants should be handed a **receipt and a flyer** that describes the GRM procedures and timeline."

> "Typically, the user should be provided with a **receipt and 'roadmap'** telling him/her how the complaint process works and when to expect further information."

**Current Gap:** No automated receipt or process roadmap sent to citizens.

### Solution Overview

Create customizable notification templates and configure automatic sending based on issue lifecycle events.

### Components

#### 3.1 GRM Notification Template DocType

**Purpose:** Store reusable email/SMS templates for different events

**File Structure:**
```
egrm/egrm/doctype/grm_notification_template/
├── __init__.py
├── grm_notification_template.json
├── grm_notification_template.py
└── grm_notification_template.js
```

**Fields:**

```json
{
  "fields": [
    {
      "fieldname": "template_name",
      "fieldtype": "Data",
      "label": "Template Name",
      "reqd": 1,
      "unique": 1
    },
    {
      "fieldname": "description",
      "fieldtype": "Small Text",
      "label": "Description"
    },
    {
      "fieldname": "email_template",
      "fieldtype": "Link",
      "options": "Email Template",
      "label": "Email Template",
      "description": "Select standard Frappe Email Template"
    },
    {
      "fieldname": "sms_message",
      "fieldtype": "Text",
      "label": "SMS Message",
      "description": "Supports Jinja: {{ doc.tracking_code }}, {{ doc.status }}, etc."
    }
  ]
}
```

**Example Templates:**

**Template 1: Receipt Acknowledgment**
- Email Template: → (Link to Frappe Email Template)
- SMS: `Your complaint {{ doc.tracking_code }} has been received. Track at {{ tracking_url }}`

**Template 2: Investigation Started**
- Email Template: → (Link to Frappe Email Template)
- SMS: `Complaint {{ doc.tracking_code }} is under investigation.`

**Template 3: Resolution Complete**
- Email Template: → (Link to Frappe Email Template)
- SMS: `Complaint {{ doc.tracking_code }} resolved. Check details at {{ tracking_url }}`

**Template 4: Escalation Notice**
- Email Template: → (Link to Frappe Email Template)
- SMS: `Complaint {{ doc.tracking_code }} has been escalated.`

**Template 5: Appeal Notification**
- Email Template: → (Link to Frappe Email Template)
- SMS: `Your appeal for {{ doc.tracking_code }} has been received.`

#### 3.2 GRM Project Notification Settings

**Add to GRM Project DocType:**

```json
{
  "fields": [
    {
      "fieldname": "notification_settings_section",
      "fieldtype": "Section Break",
      "label": "Notification Settings"
    },
    {
      "fieldname": "enable_sms_notifications",
      "fieldtype": "Check",
      "label": "Enable SMS Notifications"
    },
    {
      "fieldname": "notification_templates_section",
      "fieldtype": "Section Break",
      "label": "Notification Templates"
    },
    {
      "fieldname": "receipt_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Receipt Template",
      "description": "Sent when complaint is first created"
    },
    {
      "fieldname": "acknowledgment_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Acknowledgment Template",
      "description": "Sent when complaint is formally acknowledged"
    },
    {
      "fieldname": "investigation_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Investigation Started Template"
    },
    {
      "fieldname": "resolution_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Resolution Template"
    },
    {
      "fieldname": "escalation_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Escalation Template"
    },
    {
      "fieldname": "appeal_template",
      "fieldtype": "Link",
      "options": "GRM Notification Template",
      "label": "Appeal Template"
    }
  ]
}
```

**Benefits:**
- Each project selects which templates to use
- Templates can be shared across projects or project-specific
- Easy to customize via UI

#### 3.3 Frappe Email Template Examples

**Administrators create Email Templates via:** Home > Settings > Email Template > New

**Example: Receipt Email Template**

```
Name: GRM Receipt Email
Subject: Complaint Received - {{ doc.tracking_code }}

Message (HTML):
<p>Dear {{ doc.citizen_name or "Complainant" }},</p>

<p>Your grievance has been successfully registered.</p>

<table style="border-collapse: collapse; margin: 20px 0;">
  <tr>
    <td style="padding: 8px; font-weight: bold;">Tracking Code:</td>
    <td style="padding: 8px;">{{ doc.tracking_code }}</td>
  </tr>
  <tr>
    <td style="padding: 8px; font-weight: bold;">Submission Date:</td>
    <td style="padding: 8px;">{{ doc.creation.strftime('%d %B %Y') }}</td>
  </tr>
  <tr>
    <td style="padding: 8px; font-weight: bold;">Category:</td>
    <td style="padding: 8px;">{{ doc.category }}</td>
  </tr>
  <tr>
    <td style="padding: 8px; font-weight: bold;">Expected Acknowledgment:</td>
    <td style="padding: 8px;">{{ doc.expected_acknowledgment_date.strftime('%d %B %Y') }}</td>
  </tr>
  <tr>
    <td style="padding: 8px; font-weight: bold;">Expected Resolution:</td>
    <td style="padding: 8px;">{{ doc.expected_resolution_date.strftime('%d %B %Y') }}</td>
  </tr>
</table>

<h3>How to Track Your Complaint:</h3>
<p>Visit: <a href="{{ frappe.utils.get_url() }}/grm-public/track-complaint">Track Complaint</a></p>
<p>Enter tracking code: <strong>{{ doc.tracking_code }}</strong></p>

<h3>Grievance Redress Process:</h3>
<ol style="margin: 20px 0;">
  <li><strong>Receipt & Registration</strong> - Your complaint is registered ✓</li>
  <li><strong>Acknowledgment</strong> - Staff reviews and confirms receipt (within 7 days)</li>
  <li><strong>Investigation</strong> - Assigned officer investigates the issue (within 30 days)</li>
  <li><strong>Resolution</strong> - Solution proposed and implemented</li>
  <li><strong>Appeal</strong> - If not satisfied, you can appeal within 14 days</li>
</ol>

<h3>Contact Information:</h3>
<p>For questions, visit our help center: <a href="{{ frappe.utils.get_url() }}/grm-public">GRM Help Center</a></p>

<p style="margin-top: 30px; font-size: 12px; color: #666;">
This is an automated message. Please do not reply to this email.<br>
{{ doc.project }}
</p>
```

**Multi-Language Support:**
- Use Frappe's standard `_("translatable text")` function
- Email templates support translation system
- No custom code needed

#### 3.4 Notification Logic in GRM Issue

**Update `grm_issue.py`:**

```python
class GRMIssue(Document):
    def after_insert(self):
        """Send receipt notification when issue is created"""
        # Initialize SLA (covered in Section 4)
        sla = SLAManager(self)
        sla.initialize_sla()
        self.save()

        # Send receipt
        self.send_notification("receipt_template")

    def on_update(self):
        """Send notifications on status changes"""
        # Update SLA status
        if not self.is_new():
            sla = SLAManager(self)
            sla.update_sla_status()

        # Check for status changes
        if self.has_value_changed("status"):
            self.handle_status_change()

        # Check for acknowledgment
        if self.has_value_changed("acknowledged_date"):
            self.send_notification("acknowledgment_template")

        # Check for escalation
        if self.has_value_changed("escalate_flag") and self.escalate_flag:
            self.send_notification("escalation_template")

        # Check for appeal
        if self.has_value_changed("appeal_submitted") and self.appeal_submitted:
            self.send_notification("appeal_template")

        # Check for resolution rejection -> appeal
        if self.has_value_changed("resolution_accepted"):
            if self.resolution_accepted == "Rejected":
                self.initiate_appeal()

    def handle_status_change(self):
        """Determine which template to send based on status"""
        status_doc = frappe.get_doc("GRM Issue Status", self.status)

        # Check if investigation status
        if "investigation" in status_doc.status_name.lower():
            self.send_notification("investigation_template")

        # Check if final/resolved status
        if status_doc.final_status:
            self.send_notification("resolution_template")

    def send_notification(self, template_field):
        """Send email and SMS using configured template"""
        project = frappe.get_doc("GRM Project", self.project)
        template_name = project.get(template_field)

        if not template_name:
            return  # No template configured, skip

        template = frappe.get_doc("GRM Notification Template", template_name)

        # Send Email
        if template.email_template and self.citizen_email:
            self.send_email_notification(template.email_template)

        # Send SMS
        if template.sms_message and self.citizen_phone and project.enable_sms_notifications:
            self.send_sms_notification(template.sms_message)

    def send_email_notification(self, email_template_name):
        """Send email using Frappe Email Template"""
        from frappe.email.doctype.email_template.email_template import get_email_template

        email_template = get_email_template(email_template_name, self.as_dict())

        frappe.sendmail(
            recipients=[self.citizen_email],
            subject=email_template.get("subject"),
            message=email_template.get("message"),
            reference_doctype=self.doctype,
            reference_name=self.name
        )

    def send_sms_notification(self, sms_template):
        """Send SMS using Jinja template"""
        from frappe.core.doctype.sms_settings.sms_settings import send_sms
        from jinja2 import Template

        # Render SMS template with doc context
        context = self.as_dict()
        context["tracking_url"] = f"{frappe.utils.get_url()}/grm-public/track-complaint?code={self.tracking_code}"

        template = Template(sms_template)
        message = template.render(**context)

        send_sms([self.citizen_phone], message)

    def initiate_appeal(self):
        """Auto-initiate appeal when resolution rejected"""
        self.appeal_submitted = 1
        self.appeal_date = now()

        # Get appeal department from category
        category = frappe.get_doc("GRM Issue Category", self.category)

        if category.appeal_department:
            sla = SLAManager(self)
            new_assignee = sla.find_department_head(category.appeal_department)

            if new_assignee:
                self.assignee = new_assignee
                self.add_comment("Info", f"Appeal initiated. Reassigned to {new_assignee}")

        self.send_notification("appeal_template")
```

#### 3.5 Expected Date Fields

**Add to GRM Issue DocType:**

```json
{
  "fields": [
    {
      "fieldname": "expected_acknowledgment_date",
      "fieldtype": "Date",
      "label": "Expected Acknowledgment Date",
      "read_only": 1
    },
    {
      "fieldname": "expected_resolution_date",
      "fieldtype": "Date",
      "label": "Expected Resolution Date",
      "read_only": 1
    }
  ]
}
```

These are auto-calculated by the SLA Manager (Section 4).

---

## 4. SLA Tracking & Workflow Enhancements

### Problem Statement

**WB Requirements:**
1. Acknowledgment within 7 days (WB Approach p.4)
2. Multi-level resolution timelines (WB Questionnaire)
3. Automated appeal workflow
4. Formal resolution agreements

**Current Gap:** No SLA tracking, no acknowledgment enforcement, manual appeal processing.

### Solution Overview

Build an Administrative Level-based SLA system where:
- SLAs are configured per Administrative Level Type (Village, District, Province, National)
- SLA determined by issue's `administrative_region.administrative_level`
- Auto-escalation to parent region when SLA expires
- Clean separation via dedicated SLA Manager module

### Components

#### 4.1 SLA Configuration in Administrative Level Type

**Update `grm_administrative_level_type.json`:**

Add SLA fields directly to existing DocType:

```json
{
  "field_order": [
    "level_name",
    "level_order",
    "project",
    "sla_section",
    "acknowledgment_days",
    "resolution_days",
    "column_break_sla",
    "reminder_before_days"
  ],
  "fields": [
    // ... existing fields (level_name, level_order, project) ...
    {
      "fieldname": "sla_section",
      "fieldtype": "Section Break",
      "label": "SLA Configuration"
    },
    {
      "fieldname": "acknowledgment_days",
      "fieldtype": "Int",
      "label": "Acknowledgment SLA (Days)",
      "default": 7,
      "reqd": 1,
      "description": "Days to acknowledge complaint at this level"
    },
    {
      "fieldname": "resolution_days",
      "fieldtype": "Int",
      "label": "Resolution SLA (Days)",
      "default": 30,
      "reqd": 1,
      "description": "Days to resolve complaint at this level"
    },
    {
      "fieldname": "column_break_sla",
      "fieldtype": "Column Break"
    },
    {
      "fieldname": "reminder_before_days",
      "fieldtype": "Int",
      "label": "Reminder Before Days",
      "default": 3,
      "description": "Send SLA reminder X days before deadline"
    }
  ]
}
```

**Example Configuration:**

| Level Name | Level Order | Acknowledgment Days | Resolution Days | Reminder Before |
|------------|-------------|---------------------|-----------------|-----------------|
| Village    | 1           | 7                   | 30              | 3               |
| District   | 2           | 5                   | 20              | 2               |
| Province   | 3           | 3                   | 15              | 2               |
| National   | 4           | 2                   | 10              | 1               |

**Benefits:**
- Each administrative level has its own SLA
- Higher levels have tighter SLAs (escalation urgency)
- Configurable per project
- No redundant DocTypes

#### 4.2 Project-Level Auto-Escalation Setting

**Add to `grm_project.json`:**

```json
{
  "fields": [
    {
      "fieldname": "enable_auto_escalation",
      "fieldtype": "Check",
      "label": "Enable Auto Escalation",
      "default": 1,
      "description": "Automatically escalate issues to parent region when SLA expires"
    }
  ]
}
```

#### 4.3 SLA Tracking Fields in GRM Issue

**Add to `grm_issue.json`:**

```json
{
  "field_order": [
    // ... existing fields ...
    "sla_section",
    "current_sla_start_date",
    "expected_acknowledgment_date",
    "expected_resolution_date",
    "column_break_sla",
    "acknowledged_date",
    "acknowledged_by",
    "sla_status",
    "days_to_sla_deadline"
  ],
  "fields": [
    {
      "fieldname": "sla_section",
      "fieldtype": "Section Break",
      "label": "SLA Tracking",
      "collapsible": 1
    },
    {
      "fieldname": "current_sla_start_date",
      "fieldtype": "Datetime",
      "label": "Current SLA Start Date",
      "read_only": 1,
      "description": "When the current SLA period started (resets on escalation)"
    },
    {
      "fieldname": "expected_acknowledgment_date",
      "fieldtype": "Date",
      "label": "Expected Acknowledgment Date",
      "read_only": 1
    },
    {
      "fieldname": "expected_resolution_date",
      "fieldtype": "Date",
      "label": "Expected Resolution Date",
      "read_only": 1
    },
    {
      "fieldname": "column_break_sla",
      "fieldtype": "Column Break"
    },
    {
      "fieldname": "acknowledged_date",
      "fieldtype": "Date",
      "label": "Acknowledged Date"
    },
    {
      "fieldname": "acknowledged_by",
      "fieldtype": "Link",
      "options": "User",
      "label": "Acknowledged By"
    },
    {
      "fieldname": "sla_status",
      "fieldtype": "Select",
      "label": "SLA Status",
      "options": "On Track\nAt Risk\nOverdue",
      "read_only": 1
    },
    {
      "fieldname": "days_to_sla_deadline",
      "fieldtype": "Int",
      "label": "Days to SLA Deadline",
      "read_only": 1
    }
  ]
}
```

#### 4.4 SLA Workflow Manager Module

**File:** `egrm/egrm/utils/sla_manager.py`

**Purpose:** Dedicated module for all SLA-related logic (keeps GRM Issue class clean)

**Key Functions:**

1. **`initialize_sla()`** - Called on issue creation
   - Sets `current_sla_start_date` to now
   - Looks up admin level from `administrative_region.administrative_level`
   - Calculates `expected_acknowledgment_date` and `expected_resolution_date`
   - Sets initial `sla_status`

2. **`update_sla_status()`** - Called on every issue update
   - Compares current date to `expected_resolution_date`
   - Calculates `days_to_sla_deadline`
   - Updates `sla_status`:
     - "On Track" if > reminder_before_days remaining
     - "At Risk" if ≤ reminder_before_days remaining
     - "Overdue" if past deadline

3. **`check_and_escalate()`** - Called by daily scheduler
   - Checks if SLA expired
   - Checks if `enable_auto_escalation` is true
   - Calls `escalate_to_parent_level()` if needed

4. **`escalate_to_parent_level()`** - Auto-escalation logic
   - Gets parent region from `administrative_region.parent_region`
   - Updates `administrative_region` to parent
   - Resets `current_sla_start_date`
   - Recalculates expected dates based on parent level's SLA
   - Finds new assignee for parent region
   - Sets `escalate_flag`, `escalated_date`, `escalated_by`
   - Adds comment to issue log
   - Sends escalation notification

5. **`find_assignee_for_region()`** - Helper
   - Queries `GRM User Project Assignment`
   - Priority: Department Head > Project Manager
   - Returns user assigned to that administrative region

**Daily Scheduler Job:**

```python
@frappe.whitelist()
def check_all_slas():
    """
    Scheduled job (runs daily)
    - Finds all issues with expired SLAs
    - Auto-escalates if project has enable_auto_escalation
    - Sends escalation notifications
    """
```

**Scheduled in `hooks.py`:**

```python
scheduler_events = {
    "daily": [
        "egrm.egrm.utils.sla_manager.check_all_slas"
    ]
}
```

#### 4.5 Integration with GRM Issue

**Update `grm_issue.py`:**

```python
from egrm.egrm.utils.sla_manager import SLAManager

class GRMIssue(Document):
    def after_insert(self):
        """Initialize SLA and send receipt"""
        sla = SLAManager(self)
        sla.initialize_sla()
        self.save()

        # Send receipt notification (from Section 3)
        self.send_notification("receipt_template")

    def on_update(self):
        """Update SLA status on every change"""
        if not self.is_new():
            sla = SLAManager(self)
            sla.update_sla_status()

        # Handle other events (notifications, status changes, etc.)
        # ... (from Section 3)
```

**Benefits:**
- GRM Issue class stays clean
- SLA logic isolated in dedicated module
- Easy to test SLA logic independently
- Reusable across different contexts

#### 4.6 SLA Reminder Notifications

**Configure via Frappe Notification (Standard UI):**

No custom code needed - use Frappe's Notification DocType.

**Notification 1: SLA At Risk**
```
Name: GRM SLA At Risk
Document Type: GRM Issue
Event: Value Change
Condition: doc.sla_status == "At Risk"
Enabled: ✓

Recipients:
  - Document Field: assignee

Subject: SLA At Risk - {{ doc.tracking_code }}

Message:
Complaint {{ doc.tracking_code }} is approaching SLA deadline.

Expected Resolution: {{ doc.expected_resolution_date }}
Days Remaining: {{ doc.days_to_sla_deadline }}

Please prioritize this complaint.
```

**Notification 2: SLA Overdue**
```
Name: GRM SLA Overdue
Document Type: GRM Issue
Event: Value Change
Condition: doc.sla_status == "Overdue"
Enabled: ✓

Recipients:
  - Document Field: assignee
  - Role: GRM Project Manager

Subject: ⚠️ SLA OVERDUE - {{ doc.tracking_code }}

Message:
URGENT: Complaint {{ doc.tracking_code }} has exceeded SLA deadline.

Expected Resolution: {{ doc.expected_resolution_date }}
Days Overdue: {{ doc.days_to_sla_deadline * -1 }}

Immediate action required.
```

**Notification 3: Issue Escalated**
```
Name: GRM Issue Escalated
Document Type: GRM Issue
Event: Value Change
Condition: doc.escalate_flag == 1
Enabled: ✓

Recipients:
  - Document Field: assignee

Subject: Issue Escalated - {{ doc.tracking_code }}

Message:
Complaint {{ doc.tracking_code }} has been escalated.

New Expected Resolution: {{ doc.expected_resolution_date }}

Please review and take action.
```

#### 4.7 Resolution Agreement Documents

**Add to `grm_issue.json`:**

```json
{
  "fields": [
    {
      "fieldname": "resolution_agreement_section",
      "fieldtype": "Section Break",
      "label": "Resolution Agreement",
      "depends_on": "eval: doc.resolution_accepted == 'Accepted'"
    },
    {
      "fieldname": "resolution_agreement",
      "fieldtype": "Attach",
      "label": "Resolution Agreement Document",
      "description": "Upload signed agreement between complainant and project (WB requirement)"
    },
    {
      "fieldname": "agreement_date",
      "fieldtype": "Date",
      "label": "Agreement Date"
    },
    {
      "fieldname": "implementation_confirmation",
      "fieldtype": "Attach",
      "label": "Implementation Confirmation Document",
      "description": "Upload confirmation that resolution was implemented"
    },
    {
      "fieldname": "implementation_confirmed_date",
      "fieldtype": "Date",
      "label": "Implementation Confirmed Date"
    }
  ]
}
```

**WB Requirement (WB Approach p.6):**
> "Where there is an agreement between the complainant and the client or contractor on how the complaint will be resolved, **a minute will be drafted and signed** by both parties."

**Implementation:**
- Simple file upload fields
- Admin uploads scanned/signed agreement documents
- Optional validation reminder if resolution accepted without agreement

#### 4.8 SLA Compliance Dashboard

**Add to existing `egrm/api/stats.py`:**

```python
@frappe.whitelist()
def sla_compliance_dashboard(project_id=None):
    """
    Get SLA compliance statistics for dashboard

    Returns:
        - Acknowledgment compliance rate
        - Resolution compliance rate
        - Current at-risk issues
        - Current overdue issues
        - Escalation statistics
    """
    from egrm.egrm.utils.sla_manager import get_sla_compliance_stats

    return get_sla_compliance_stats(project_id)
```

**Dashboard Metrics:**
- Acknowledgment SLA Compliance: 85% (40/47 acknowledged on time)
- Resolution SLA Compliance: 78% (23/30 resolved on time)
- Currently At Risk: 5 issues
- Currently Overdue: 2 issues
- Auto-escalated This Month: 3 issues

---

## 5. Multi-Project & Multi-Language Support

### Multi-Project Architecture

**Design Principle:** Each project configures independently

**Per-Project Configuration:**

1. **SLA Levels:** Configured in GRM Administrative Level Type (per project)
2. **Notification Templates:** Projects select templates from shared pool or create project-specific
3. **Auto Email Reports:** Each project creates its own Auto Email Report documents
4. **Public Pages:** Filter by project (all public APIs accept `project_id` parameter)
5. **Auto-Escalation:** Each project enables/disables independently

**Example:**
- **Project A (Urban Infrastructure):** Village→District→National, 7/30/10 day SLAs
- **Project B (Rural Development):** Community→Region→Country, 10/45/20 day SLAs

Each has different administrative hierarchies and timelines.

### Multi-Language Support

**Frappe's Built-in Translation System:**

All text uses Frappe's `_()` function:

```python
from frappe import _

label = _("Complaint Received")  # Auto-translated
```

**Email Templates:**
- Use `_()` for translatable text
- Create separate templates per language if needed
- Or use Frappe's translation JSON files

**SMS Templates:**
- Support Jinja variables
- Text auto-translated via Frappe system

**Public Web Pages:**
- Use `_()` in templates
- Language switcher in UI (if needed)

**No Custom Translation Code Needed** - Frappe handles it.

---

## 6. Role Structure Clarification

### QA Report Section 2.1 Analysis

**QA Concern:** "Role redundancy between Project Manager and Department Head"

**Resolution:** **KEEP BOTH ROLES**

**Justification:**

The multi-project nature of this system **justifies** separate PM and Department Head roles:

1. **Multi-Project Assignment:**
   - A user can be Project Manager on Project A
   - Same user can be Department Head on Project B
   - Roles are project-specific, not global

2. **Organizational Models:**
   - Some projects are small (no departments) → PM manages all
   - Large projects have departments → Department Heads manage by function
   - Both models need to coexist

3. **Scope Differences:**
   - **PM:** Project-wide visibility and control
   - **Department Head:** Department-scoped (Environmental, Land, Employment, etc.)
   - Scope enforced by `grm_issue_permissions.py` logic

4. **Existing Implementation:**
   - Permission system already handles scope correctly
   - Field permissions already differentiated
   - Changing roles would break existing project assignments

**Documentation Update:**

Add to system docs:
- **When to use Project Manager:** Small projects, overall coordination
- **When to use Department Head:** Large projects with functional departments
- **Can users have both?** Yes, on different projects or even same project (PM + specific dept)

**No Code Changes Required** - just documentation clarification.

---

## 7. Implementation Phases

### Phase 1: Critical Compliance (Weeks 1-3)

**Goal:** Address 20% compliance gap in public transparency

**Deliverables:**
1. Public Metrics API (`egrm/api/public_metrics.py`)
2. Public Tracking API (`egrm/api/public_tracking.py`)
3. Public web pages (`egrm/www/grm-public/`)
   - Homepage
   - Dashboard
   - Track Complaint
   - Submit Grievance (optional)
4. GRM Public Monthly Report (Script Report)
5. GRM Public Quarterly Report (Script Report)
6. Auto Email Report configurations (documentation + examples)

**Success Criteria:**
- ✅ Public can view aggregate GRM metrics
- ✅ Public can track complaints by code
- ✅ Monthly/quarterly reports auto-generated

**Estimated Effort:** 3 weeks (2 developers)

### Phase 2: Notifications & SLA (Weeks 4-6)

**Goal:** Automated receipts and SLA tracking

**Deliverables:**
1. GRM Notification Template DocType
2. Update GRM Project with template selectors
3. Frappe Email Templates (examples + documentation)
4. Update GRM Issue notification logic
5. Update GRM Administrative Level Type with SLA fields
6. Create SLA Manager module (`egrm/egrm/utils/sla_manager.py`)
7. Update GRM Issue with SLA fields
8. Integrate SLA Manager with GRM Issue
9. Configure Frappe Notifications (SLA reminders)
10. Daily scheduler for auto-escalation

**Success Criteria:**
- ✅ Citizens receive automated receipts
- ✅ Citizens receive roadmap/timeline
- ✅ SLA tracking per administrative level
- ✅ Auto-escalation on SLA expiry
- ✅ Staff receive SLA reminders

**Estimated Effort:** 3 weeks (2 developers)

### Phase 3: Polish & Documentation (Weeks 7-8)

**Goal:** User documentation and deployment readiness

**Deliverables:**
1. Administrator documentation
   - How to configure notification templates
   - How to set up Auto Email Reports
   - How to configure SLA per level
2. User guides
   - Citizen guide (how to track complaints)
   - Field officer guide (using the app)
3. Public report archive page
4. Resolution agreement upload documentation
5. Multi-language setup guide (if needed)
6. Testing documentation (for future Phase 4)

**Success Criteria:**
- ✅ Complete admin documentation
- ✅ Complete user guides
- ✅ System ready for deployment

**Estimated Effort:** 2 weeks (1 developer + 1 technical writer)

**Total Timeline:** 8 weeks
**Total Effort:** ~14 person-weeks

---

## 8. Technical Architecture Summary

### Technology Stack

**Framework:** Frappe v15+
**Language:** Python 3.10+
**Database:** MariaDB
**Frontend:** Jinja2 templates, Frappe UI
**Scheduler:** RQ (Redis Queue)
**Email:** Frappe Email Queue
**SMS:** Frappe SMS Settings (optional)

### File Structure

```
egrm/
├── egrm/
│   ├── api/
│   │   ├── public_metrics.py           # NEW: Public guest APIs
│   │   ├── public_tracking.py          # NEW: Complaint tracking
│   │   └── stats.py                    # UPDATED: Add SLA stats
│   ├── doctype/
│   │   ├── grm_notification_template/  # NEW: Template storage
│   │   ├── grm_project/                # UPDATED: Add template selectors
│   │   ├── grm_issue/                  # UPDATED: Add SLA fields + logic
│   │   └── grm_administrative_level_type/  # UPDATED: Add SLA fields
│   ├── report/
│   │   ├── grm_public_monthly_report/  # NEW: Monthly report
│   │   └── grm_public_quarterly_report/# NEW: Quarterly report
│   └── utils/
│       └── sla_manager.py              # NEW: SLA workflow manager
├── www/
│   └── grm-public/                     # NEW: Public web pages
│       ├── index.html
│       ├── index.py
│       ├── dashboard/
│       ├── track-complaint/
│       ├── submit-grievance/
│       └── reports/
└── hooks.py                            # UPDATED: Add scheduler events
```

### Data Flow

**Issue Creation → Receipt:**
```
Citizen/Field Officer creates GRM Issue
  ↓
GRM Issue.after_insert()
  ↓
SLAManager.initialize_sla() → Calculate expected dates
  ↓
GRM Issue.send_notification("receipt_template")
  ↓
Fetch Email Template from GRM Project config
  ↓
Send email/SMS to citizen
```

**SLA Monitoring → Auto-Escalation:**
```
Daily Scheduler (midnight)
  ↓
check_all_slas()
  ↓
For each overdue issue:
  SLAManager.check_and_escalate()
    ↓
  Escalate to parent administrative region
    ↓
  Reset SLA clock
    ↓
  Reassign to parent region staff
    ↓
  Send escalation notification
```

**Public Tracking:**
```
Citizen visits /grm-public/track-complaint
  ↓
Enters tracking code
  ↓
API call to public_tracking.track_complaint() (no auth)
  ↓
Lookup issue by tracking_code
  ↓
Return anonymized status info
  ↓
Display to citizen
```

### Security Model

**Public APIs:**
- `@frappe.whitelist(allow_guest=True)` for guest access
- Return only aggregate/anonymized data
- No PII in public endpoints
- Rate limiting (Frappe built-in)

**Internal APIs:**
- `@frappe.whitelist()` requires authentication
- Role-based permissions (existing system)
- Field-level permissions (existing system)

**File Uploads:**
- Resolution agreements stored securely
- Only accessible to authorized users
- Linked to GRM Issue via Attach field

---

## 9. Dependencies & Assumptions

### External Dependencies

**Required:**
- Frappe Framework v15+
- MariaDB (already in use)
- Redis (for scheduler)

**Optional:**
- SMS Gateway (for SMS notifications)
- Email SMTP server (for email notifications)

### Assumptions

1. **Existing administrative hierarchy** is properly configured (regions with parent relationships)
2. **User assignments** are maintained (users assigned to administrative regions)
3. **Email infrastructure** is available for notifications
4. **Public web access** is allowed (firewall configured for www/ pages)
5. **Frappe scheduler** is running in production

### Configuration Prerequisites

Before implementation:
1. ✅ Administrative Level Types created per project
2. ✅ Administrative Regions created with hierarchy
3. ✅ User Project Assignments configured
4. ✅ GRM Issue Categories with appeal departments
5. ✅ GRM Issue Statuses with initial/final flags

---

## 10. Risk Mitigation

### Risk 1: Email Delivery Failures

**Risk:** Receipts/notifications not delivered to citizens

**Mitigation:**
- Use reliable SMTP provider
- Implement email queue retry (Frappe built-in)
- Log all email attempts
- Provide fallback: citizens can check status via public tracking
- SMS as backup channel (if enabled)

### Risk 2: SLA Auto-Escalation Issues

**Risk:** Incorrect escalations due to misconfigured hierarchy

**Mitigation:**
- Validate administrative region hierarchy on save
- Test auto-escalation thoroughly before production
- Add manual override: `enable_auto_escalation` per project
- Log all escalations for audit
- Alert admins when escalation fails (no parent region)

### Risk 3: Public API Abuse

**Risk:** Public endpoints spammed or scraped

**Mitigation:**
- Frappe's built-in rate limiting
- Optional CAPTCHA on web submission form
- Optional OTP verification for submissions
- Monitor public API usage
- Cloudflare or similar CDN for DDoS protection

### Risk 4: Template Configuration Errors

**Risk:** Projects forget to configure notification templates

**Mitigation:**
- Provide default templates during installation
- Validation warning if template not configured
- Documentation with step-by-step setup guide
- Notification test button: "Send Test Email"

---

## 11. Future Enhancements (Out of Scope)

**Not in current design, but possible later:**

1. **Web-based GRM submission with full form builder**
   - Currently: Simple submission form
   - Future: Full custom form builder with conditional fields

2. **Mobile app improvements**
   - Currently: Existing mobile app works
   - Future: Enhanced UX, offline photo upload, geolocation

3. **Advanced analytics & BI dashboards**
   - Currently: Basic public dashboard
   - Future: Power BI / Tableau integration

4. **AI-powered categorization**
   - Currently: Manual category selection
   - Future: Auto-suggest category based on description

5. **Citizen portal with login**
   - Currently: Track by code only (no login)
   - Future: Full citizen portal with complaint history

6. **Integration with external systems**
   - Currently: Standalone
   - Future: Webhook integrations, API exports

7. **Comprehensive test suite**
   - Currently: Deferred to later phase
   - Future: Unit tests, integration tests, E2E tests

---

## 12. Success Metrics

### Compliance Metrics

**Target:** 85%+ WB GRM Compliance (up from 68%)

**Measured by:**
- ✅ Public transparency features implemented
- ✅ Automated public reporting in place
- ✅ Receipt/roadmap system operational
- ✅ SLA tracking and enforcement active
- ✅ All WB critical requirements addressed

### Operational Metrics

**Target:** Improve GRM efficiency

**Measured by:**
- Average acknowledgment time ≤ 7 days
- SLA compliance rate ≥ 80%
- Auto-escalation reducing manual interventions
- Citizen satisfaction (via ratings)
- Staff workload balanced via SLA visibility

### Public Access Metrics

**Target:** Increase public transparency

**Measured by:**
- Public dashboard page views
- Complaint tracking usage
- Web submissions (if enabled)
- Report download counts
- Public API usage

---

## 13. Rollout Strategy

### Pre-Production Testing

**Week 1-2: Staging Environment**
1. Deploy to staging
2. Configure test project with sample data
3. Test all public pages
4. Test auto-escalation with time-travel
5. Test email/SMS notifications
6. Run SLA calculations with various scenarios

**Week 3: User Acceptance Testing**
1. Train administrators
2. Configure notification templates
3. Set up Auto Email Reports
4. Test end-to-end workflows
5. Gather feedback

### Production Deployment

**Week 4: Go-Live**

**Step 1: Database Changes**
- Run migrations for new fields
- Add SLA fields to Administrative Level Types
- Add notification template records

**Step 2: Code Deployment**
- Deploy new modules (sla_manager, public APIs)
- Deploy www/ pages
- Deploy reports
- Update hooks.py

**Step 3: Configuration**
- Configure SLA per administrative level
- Create notification templates
- Set up Auto Email Reports
- Configure Frappe Notifications

**Step 4: Validation**
- Smoke tests on production
- Test public pages
- Verify scheduler running
- Send test notifications

**Step 5: Monitoring**
- Monitor error logs
- Check email queue
- Verify scheduler jobs
- Monitor public API usage

### Training Plan

**Administrators:**
- How to configure SLAs
- How to create/edit notification templates
- How to set up Auto Email Reports
- How to monitor compliance dashboard

**Field Officers:**
- How receipt system works
- Understanding SLA timelines
- When to manually acknowledge
- Escalation process

**Citizens (Public Guides):**
- How to track complaints online
- How to submit via web form
- Understanding the GRM process
- What to expect at each stage

---

## 14. Appendices

### Appendix A: World Bank Requirements Mapping

| WB Requirement | Section | Implementation | Status |
|----------------|---------|----------------|--------|
| Public database access | WB Approach p.4 | Public dashboard + APIs | Section 1 |
| Monthly/quarterly reports | WB Approach p.6 | Auto Email Reports | Section 2 |
| Receipt & roadmap | WB Approach p.4 | Notification templates | Section 3 |
| Acknowledgment within 7 days | WB Approach p.4 | SLA tracking | Section 4 |
| Multi-level resolution timelines | WB Questionnaire | Admin level SLAs | Section 4 |
| Appeal process | WB Questionnaire Sec 8 | Auto-appeal workflow | Section 3 |
| Formal agreements | WB Approach p.6 | File upload fields | Section 4 |

### Appendix B: Field-Level Changes Summary

**New DocTypes:**
- GRM Notification Template

**Updated DocTypes:**

**GRM Administrative Level Type:**
- `acknowledgment_days` (Int)
- `resolution_days` (Int)
- `reminder_before_days` (Int)

**GRM Project:**
- `enable_auto_escalation` (Check)
- `enable_sms_notifications` (Check)
- `receipt_template` (Link)
- `acknowledgment_template` (Link)
- `investigation_template` (Link)
- `resolution_template` (Link)
- `escalation_template` (Link)
- `appeal_template` (Link)

**GRM Issue:**
- `current_sla_start_date` (Datetime)
- `expected_acknowledgment_date` (Date)
- `expected_resolution_date` (Date)
- `acknowledged_date` (Date)
- `acknowledged_by` (Link: User)
- `sla_status` (Select)
- `days_to_sla_deadline` (Int)
- `resolution_agreement` (Attach)
- `implementation_confirmation` (Attach)

### Appendix C: API Endpoints Summary

**New Public APIs (Guest Access):**
- `egrm.api.public_metrics.get_public_dashboard`
- `egrm.api.public_tracking.track_complaint`

**New Internal APIs:**
- `egrm.egrm.utils.sla_manager.check_all_slas` (scheduler)
- `egrm.egrm.utils.sla_manager.get_sla_compliance_stats`

**Updated APIs:**
- `egrm.api.stats.dashboard` (add SLA stats)

### Appendix D: Scheduler Jobs

**New Daily Jobs:**
- `egrm.egrm.utils.sla_manager.check_all_slas` (runs at midnight)

### Appendix E: Frappe Notifications to Configure

Via UI (Home > Settings > Notification):
1. GRM SLA At Risk
2. GRM SLA Overdue
3. GRM Issue Escalated

### Appendix F: Email Templates to Create

Via UI (Home > Settings > Email Template):
1. GRM Receipt Email
2. GRM Acknowledgment Email
3. GRM Investigation Started Email
4. GRM Resolution Email
5. GRM Escalation Email
6. GRM Appeal Email

### Appendix G: Reports to Create

Via UI (Home > Report):
1. GRM Public Monthly Report (Script Report)
2. GRM Public Quarterly Report (Script Report)

---

## Conclusion

This design addresses all critical World Bank GRM compliance gaps while leveraging Frappe's standard features to minimize custom code. The phased approach allows for incremental delivery with clear validation points.

**Key Success Factors:**
1. ✅ Reuses Frappe infrastructure (no reinventing the wheel)
2. ✅ Clean separation of concerns (SLA Manager module)
3. ✅ Multi-project flexibility (each project configures independently)
4. ✅ Minimal code changes (mostly configuration + dedicated modules)
5. ✅ Well-defined phases (can stop after Phase 1 if needed)

**Next Steps:**
1. Review and approve this design
2. Create detailed implementation plan (task breakdown, file-level changes)
3. Set up development environment
4. Begin Phase 1 implementation

---

**Document Version Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-16 | AI Design Team | Initial design document |

**Approvals**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Owner | | | |
| Technical Lead | | | |
| WB Compliance Officer | | | |
