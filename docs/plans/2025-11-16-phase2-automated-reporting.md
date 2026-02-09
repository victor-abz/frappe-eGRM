# Phase 2: Automated Public Reporting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement automated monthly/quarterly public reports using Frappe's Auto Email Report feature to meet WB requirement for "regular reports to the public."

**Architecture:** Create Frappe Script Reports with summary cards and charts. Configure Auto Email Reports via UI (no scheduler code needed). Optionally create public report archive page.

**Tech Stack:** Frappe Framework v15+, Python 3.10+, Frappe Reports, Auto Email Report

**Design Reference:** `docs/plans/2025-11-16-wb-grm-compliance-design.md` Section 2

**Prerequisites:** Phase 1 completed (public APIs available for testing)

---

## Task 1: GRM Public Monthly Report - Structure

**Files:**
- Create: `egrm/egrm/report/grm_public_monthly_report/__init__.py`
- Create: `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.json`
- Create: `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.py`
- Create: `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.js`

### Step 1: Create report directory structure

**Command:**
```bash
mkdir -p egrm/egrm/report/grm_public_monthly_report
touch egrm/egrm/report/grm_public_monthly_report/__init__.py
```

**Expected:** Directory and __init__.py created

### Step 2: Create report JSON metadata

**File:** `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.json`

**Code:**
```json
{
 "add_total_row": 0,
 "columns": [],
 "creation": "2025-11-16 00:00:00",
 "disabled": 0,
 "docstatus": 0,
 "doctype": "Report",
 "idx": 0,
 "is_standard": "Yes",
 "modified": "2025-11-16 00:00:00",
 "modified_by": "Administrator",
 "module": "egrm",
 "name": "GRM Public Monthly Report",
 "owner": "Administrator",
 "ref_doctype": "GRM Issue",
 "report_name": "GRM Public Monthly Report",
 "report_type": "Script Report",
 "roles": [
  {
   "role": "GRM Administrator"
  },
  {
   "role": "GRM Project Manager"
  }
 ]
}
```

### Step 3: Create report Python logic

**File:** `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.py`

**Code:**
```python
"""
GRM Public Monthly Report
Generates monthly public transparency report per WB requirements
"""

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate


def execute(filters=None):
    """
    Main execution function for monthly report

    Args:
        filters (dict): Report filters (project, from_date, to_date)

    Returns:
        tuple: (columns, data, message, chart, report_summary)
    """
    if not filters:
        filters = {}

    # Validate/set date range
    filters = validate_filters(filters)

    # Get report data
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    report_summary = get_report_summary(filters)

    return columns, data, None, chart, report_summary


def validate_filters(filters):
    """Validate and set default filters"""
    # Default to last month if no dates provided
    if not filters.get("from_date") or not filters.get("to_date"):
        today = getdate()
        last_month = add_months(today, -1)
        filters["from_date"] = get_first_day(last_month)
        filters["to_date"] = get_last_day(last_month)

    return filters


def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "category",
            "label": _("Category"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "total_received",
            "label": _("Received"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "resolved",
            "label": _("Resolved"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "pending",
            "label": _("Pending"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "appealed",
            "label": _("Appealed"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "avg_resolution_days",
            "label": _("Avg Resolution (Days)"),
            "fieldtype": "Float",
            "width": 150,
            "precision": 1
        }
    ]


def get_data(filters):
    """Get report data grouped by category"""
    # Build base filters
    base_filters = {
        "creation": ["between", [filters["from_date"], filters["to_date"]]]
    }

    if filters.get("project"):
        base_filters["project"] = filters["project"]

    # Get all categories
    category_filter = {}
    if filters.get("project"):
        category_filter["project"] = filters["project"]

    categories = frappe.get_all(
        "GRM Issue Category",
        filters=category_filter,
        fields=["name", "category_name"]
    )

    # Get resolved statuses
    resolved_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"final_status": 1},
        pluck="name"
    )

    # Get initial statuses (pending)
    pending_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"initial_status": 1},
        pluck="name"
    )

    data = []

    for category in categories:
        # Total received in this category
        cat_filters = {**base_filters, "category": category.name}
        total = frappe.db.count("GRM Issue", cat_filters)

        if total == 0:
            continue  # Skip categories with no issues

        # Resolved count
        resolved_count = 0
        if resolved_statuses:
            resolved_count = frappe.db.count(
                "GRM Issue",
                {**cat_filters, "status": ["in", resolved_statuses]}
            )

        # Pending count
        pending_count = 0
        if pending_statuses:
            pending_count = frappe.db.count(
                "GRM Issue",
                {**cat_filters, "status": ["in", pending_statuses]}
            )

        # Appealed count
        appealed_count = frappe.db.count(
            "GRM Issue",
            {**cat_filters, "appeal_submitted": 1}
        )

        # Average resolution time
        avg_days = get_avg_resolution_time(cat_filters, resolved_statuses)

        data.append({
            "category": category.category_name,
            "total_received": total,
            "resolved": resolved_count,
            "pending": pending_count,
            "appealed": appealed_count,
            "avg_resolution_days": avg_days
        })

    # Add total row
    if data:
        total_row = {
            "category": _("<b>TOTAL</b>"),
            "total_received": sum(row["total_received"] for row in data),
            "resolved": sum(row["resolved"] for row in data),
            "pending": sum(row["pending"] for row in data),
            "appealed": sum(row["appealed"] for row in data),
            "avg_resolution_days": sum(row["avg_resolution_days"] for row in data) / len(data) if data else 0
        }
        data.append(total_row)

    return data


def get_avg_resolution_time(filters, resolved_statuses):
    """Calculate average resolution time in days"""
    from frappe.utils import date_diff

    if not resolved_statuses:
        return 0

    issues = frappe.get_all(
        "GRM Issue",
        filters={**filters, "status": ["in", resolved_statuses], "resolution_date": ["is", "set"]},
        fields=["creation", "resolution_date"]
    )

    if not issues:
        return 0

    total_days = sum(
        date_diff(issue.resolution_date, issue.creation)
        for issue in issues
        if issue.creation and issue.resolution_date
    )

    return total_days / len(issues) if issues else 0


def get_chart_data(data, filters):
    """Generate chart for visual representation"""
    if not data or len(data) <= 1:  # No data or only total row
        return None

    # Remove total row for chart
    chart_data = [row for row in data if "<b>TOTAL</b>" not in row.get("category", "")]

    return {
        "data": {
            "labels": [row["category"] for row in chart_data],
            "datasets": [
                {
                    "name": _("Received"),
                    "values": [row["total_received"] for row in chart_data]
                },
                {
                    "name": _("Resolved"),
                    "values": [row["resolved"] for row in chart_data]
                }
            ]
        },
        "type": "bar",
        "colors": ["#7cd6fd", "#48bb78"],
        "barOptions": {
            "stacked": 0
        }
    }


def get_report_summary(filters):
    """Generate summary cards at top of report"""
    # Build base filters
    base_filters = {
        "creation": ["between", [filters["from_date"], filters["to_date"]]]
    }

    if filters.get("project"):
        base_filters["project"] = filters["project"]

    # Total complaints received
    total_received = frappe.db.count("GRM Issue", base_filters)

    # Resolved
    resolved_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"final_status": 1},
        pluck="name"
    )

    resolved_count = 0
    if resolved_statuses:
        resolved_count = frappe.db.count(
            "GRM Issue",
            {**base_filters, "status": ["in", resolved_statuses]}
        )

    # Pending (not resolved)
    not_resolved = total_received - resolved_count

    # Referred to third party (appeals)
    appealed = frappe.db.count("GRM Issue", {**base_filters, "appeal_submitted": 1})

    # Resolution rate
    resolution_rate = (resolved_count / total_received * 100) if total_received > 0 else 0

    return [
        {
            "value": total_received,
            "label": _("Complaints Received"),
            "datatype": "Int",
            "indicator": "Blue"
        },
        {
            "value": resolved_count,
            "label": _("Complaints Resolved"),
            "datatype": "Int",
            "indicator": "Green"
        },
        {
            "value": not_resolved,
            "label": _("Not Resolved (Open)"),
            "datatype": "Int",
            "indicator": "Orange"
        },
        {
            "value": appealed,
            "label": _("Referred to Third Party"),
            "datatype": "Int",
            "indicator": "Red"
        },
        {
            "value": resolution_rate,
            "label": _("Resolution Rate (%)"),
            "datatype": "Percent",
            "indicator": "Green" if resolution_rate >= 70 else "Orange"
        }
    ]
```

### Step 4: Create report JavaScript filters

**File:** `egrm/egrm/report/grm_public_monthly_report/grm_public_monthly_report.js`

**Code:**
```javascript
// Copyright (c) 2025, eGRM and contributors
// For license information, please see license.txt

frappe.query_reports["GRM Public Monthly Report"] = {
    "filters": [
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "GRM Project",
            "reqd": 0
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.month_start(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.month_end(), -1),
            "reqd": 1
        }
    ]
};
```

### Step 5: Test monthly report

**Frappe UI:**
1. Navigate to: Home > Reports > GRM Public Monthly Report
2. Select filters (project, dates)
3. Click "Refresh"
4. Verify summary cards appear
5. Verify data table shows categories
6. Verify chart renders

**Expected:** Report runs successfully with summary, data, and chart

### Step 6: Commit monthly report

**Command:**
```bash
git add egrm/egrm/report/grm_public_monthly_report/
git commit -m "feat: add GRM public monthly report

- Script report with category breakdown
- Summary cards for key metrics
- Charts for visual representation
- Supports WB monthly reporting requirement

Refs: WB GRM Compliance Phase 2"
```

---

## Task 2: GRM Public Quarterly Report

**Files:**
- Create: `egrm/egrm/report/grm_public_quarterly_report/__init__.py`
- Create: `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.json`
- Create: `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.py`
- Create: `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.js`

### Step 1: Create quarterly report directory

**Command:**
```bash
mkdir -p egrm/egrm/report/grm_public_quarterly_report
touch egrm/egrm/report/grm_public_quarterly_report/__init__.py
```

### Step 2: Create quarterly report JSON

**File:** `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.json`

**Code:**
```json
{
 "add_total_row": 0,
 "columns": [],
 "creation": "2025-11-16 00:00:00",
 "disabled": 0,
 "docstatus": 0,
 "doctype": "Report",
 "idx": 0,
 "is_standard": "Yes",
 "modified": "2025-11-16 00:00:00",
 "modified_by": "Administrator",
 "module": "egrm",
 "name": "GRM Public Quarterly Report",
 "owner": "Administrator",
 "ref_doctype": "GRM Issue",
 "report_name": "GRM Public Quarterly Report",
 "report_type": "Script Report",
 "roles": [
  {
   "role": "GRM Administrator"
  },
  {
   "role": "GRM Project Manager"
  }
 ]
}
```

### Step 3: Create quarterly report Python (reuse monthly logic)

**File:** `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.py`

**Code:**
```python
"""
GRM Public Quarterly Report
Generates quarterly public transparency report per WB requirements
(Reuses monthly report logic with quarterly defaults)
"""

import frappe
from frappe.utils import add_months, get_first_day, getdate

# Import monthly report functions
from egrm.egrm.report.grm_public_monthly_report.grm_public_monthly_report import (
    get_columns,
    get_data,
    get_chart_data,
    get_report_summary
)


def execute(filters=None):
    """
    Main execution function for quarterly report

    Args:
        filters (dict): Report filters (project, from_date, to_date)

    Returns:
        tuple: (columns, data, message, chart, report_summary)
    """
    if not filters:
        filters = {}

    # Validate/set date range for quarterly
    filters = validate_quarterly_filters(filters)

    # Reuse monthly report logic
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    report_summary = get_report_summary(filters)

    return columns, data, None, chart, report_summary


def validate_quarterly_filters(filters):
    """Validate and set default filters for quarterly"""
    # Default to last quarter if no dates provided
    if not filters.get("from_date") or not filters.get("to_date"):
        today = getdate()

        # Determine last quarter
        current_month = today.month
        if current_month <= 3:
            # Q1: Jan-Mar, so last quarter is Q4 of previous year
            q_start = today.replace(year=today.year - 1, month=10, day=1)
            q_end = today.replace(year=today.year - 1, month=12, day=31)
        elif current_month <= 6:
            # Q2: Apr-Jun, so last quarter is Q1
            q_start = today.replace(month=1, day=1)
            q_end = today.replace(month=3, day=31)
        elif current_month <= 9:
            # Q3: Jul-Sep, so last quarter is Q2
            q_start = today.replace(month=4, day=1)
            q_end = today.replace(month=6, day=30)
        else:
            # Q4: Oct-Dec, so last quarter is Q3
            q_start = today.replace(month=7, day=1)
            q_end = today.replace(month=9, day=30)

        filters["from_date"] = q_start
        filters["to_date"] = q_end

    return filters
```

### Step 4: Create quarterly report JavaScript

**File:** `egrm/egrm/report/grm_public_quarterly_report/grm_public_quarterly_report.js`

**Code:**
```javascript
// Copyright (c) 2025, eGRM and contributors
// For license information, please see license.txt

frappe.query_reports["GRM Public Quarterly Report"] = {
    "filters": [
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "GRM Project",
            "reqd": 0
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": get_last_quarter_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": get_last_quarter_end(),
            "reqd": 1
        }
    ]
};

function get_last_quarter_start() {
    let today = new Date();
    let month = today.getMonth();
    let year = today.getFullYear();

    if (month < 3) {
        // Q1, so last quarter is Q4 of previous year
        return new Date(year - 1, 9, 1).toISOString().split('T')[0];
    } else if (month < 6) {
        // Q2, so last quarter is Q1
        return new Date(year, 0, 1).toISOString().split('T')[0];
    } else if (month < 9) {
        // Q3, so last quarter is Q2
        return new Date(year, 3, 1).toISOString().split('T')[0];
    } else {
        // Q4, so last quarter is Q3
        return new Date(year, 6, 1).toISOString().split('T')[0];
    }
}

function get_last_quarter_end() {
    let today = new Date();
    let month = today.getMonth();
    let year = today.getFullYear();

    if (month < 3) {
        return new Date(year - 1, 11, 31).toISOString().split('T')[0];
    } else if (month < 6) {
        return new Date(year, 2, 31).toISOString().split('T')[0];
    } else if (month < 9) {
        return new Date(year, 5, 30).toISOString().split('T')[0];
    } else {
        return new Date(year, 8, 30).toISOString().split('T')[0];
    }
}
```

### Step 5: Test quarterly report

**Frappe UI:**
1. Navigate to: Home > Reports > GRM Public Quarterly Report
2. Verify default dates are last quarter
3. Click "Refresh"
4. Verify report works same as monthly

**Expected:** Quarterly report runs successfully

### Step 6: Commit quarterly report

**Command:**
```bash
git add egrm/egrm/report/grm_public_quarterly_report/
git commit -m "feat: add GRM public quarterly report

- Reuses monthly report logic
- Defaults to last quarter dates
- Supports WB quarterly reporting requirement

Refs: WB GRM Compliance Phase 2"
```

---

## Task 3: Auto Email Report Configuration Documentation

**Files:**
- Create: `docs/admin-guides/auto-email-report-setup.md`

### Step 1: Create admin documentation

**File:** `docs/admin-guides/auto-email-report-setup.md`

**Code:**
```markdown
# Auto Email Report Setup Guide

## Overview

This guide explains how to configure automated monthly and quarterly GRM public reports using Frappe's Auto Email Report feature.

## Prerequisites

- GRM Public Monthly Report created
- GRM Public Quarterly Report created
- Email server configured in Frappe
- Administrator access

## Setup Monthly Reports

### Step 1: Navigate to Auto Email Report

1. Go to: **Home > Settings > Auto Email Report**
2. Click **New**

### Step 2: Configure Monthly Report

**Basic Settings:**
- **Report:** GRM Public Monthly Report
- **Report Type:** Script Report
- **Enabled:** ✓ (check to enable)
- **User:** Administrator (or designated GRM Admin)

**Filters:**
- **Project:** Select specific project (or leave blank for all projects)
- **From Date:** Leave blank (will auto-calculate last month)
- **To Date:** Leave blank (will auto-calculate last month)

**Email Settings:**
- **Email To:**
  ```
  publicreports@project.example.com
  stakeholders@worldbank.org
  community@ministry.gov
  ```
  (One email per line or comma-separated)

**Schedule:**
- **Frequency:** Monthly
- **Day of Month:** 1 (send on 1st of each month)

**Attachments:**
- **Send Attachments:** ✓ (check)
- **Format:** Select both:
  - ✓ XLSX (for analysis)
  - ✓ PDF (for distribution)

**Message:**
```
This is the monthly GRM public transparency report for [Project Name].

The report covers the period: [from_date] to [to_date]

Key Metrics:
- Complaints Received: [Will show in report]
- Complaints Resolved: [Will show in report]
- Resolution Rate: [Will show in report]

For more information, visit: https://[your-site]/grm-public/dashboard

This is an automated report. For questions, contact [project-contact].
```

**Advanced Options:**
- **Send If Data:** ✓ (only send if report has data)
- **No of Rows:** 500 (default)

### Step 3: Test Before Enabling

1. Click **Save** (do not enable yet)
2. Click **Download** button to preview report
3. Verify report looks correct
4. Click **Send Now** button to test email delivery
5. Check recipient inboxes
6. If OK, check **Enabled** and **Save**

### Step 4: Monitor

- Reports will send automatically at midnight on scheduled day
- Check **Email Queue** for delivery status
- Check error logs if emails fail

## Setup Quarterly Reports

Follow same steps as monthly, but:

**Schedule:**
- **Frequency:** Quarterly
- **Send on:** 1st of Jan, Apr, Jul, Oct

**Message:** Update to mention "quarterly" instead of "monthly"

## Per-Project Configuration

For multi-project setups, create separate Auto Email Reports for each project:

1. Create "GRM Monthly - Project A"
2. Create "GRM Monthly - Project B"
3. Each with different:
   - Filter: Project = [specific project]
   - Recipients: Project-specific stakeholders

## Email Templates (Optional Enhancement)

For more customized emails:

1. Create Email Template: Home > Settings > Email Template
2. Name: "GRM Monthly Report Email"
3. Use Jinja variables
4. Reference in Auto Email Report

## Troubleshooting

**Emails not sending:**
- Check Email Queue (Home > Email Queue)
- Verify SMTP settings (Setup > Email Account)
- Check scheduler is running: `bench doctor`

**Wrong data in report:**
- Verify filters are correct
- Check date range calculation
- Test report manually first

**Attachments too large:**
- Reduce "No of Rows" setting
- Add project filter to reduce data
- Use XLSX only (smaller than PDF)

## Testing Checklist

Before going live:

- [ ] Report runs without errors
- [ ] Summary cards show correct data
- [ ] Charts render properly
- [ ] Attachments are formatted well
- [ ] Email delivers successfully
- [ ] Recipients can open attachments
- [ ] Schedule is correct (monthly/quarterly)
- [ ] Message text is accurate

## Example Configurations

### Configuration 1: Single Project Monthly

```
Report: GRM Public Monthly Report
Project: National Infrastructure Project
Email To: pm@project.gov, stakeholders@worldbank.org
Frequency: Monthly
Formats: XLSX, PDF
Enabled: Yes
```

### Configuration 2: All Projects Quarterly

```
Report: GRM Public Quarterly Report
Project: [Blank - all projects]
Email To: director@ministry.gov, reports@worldbank.org
Frequency: Quarterly
Formats: PDF only
Enabled: Yes
```

## Maintenance

**Monthly tasks:**
- Review sent reports
- Update recipient lists if needed
- Check for bounced emails

**Quarterly tasks:**
- Verify report content is accurate
- Update message text if process changes
- Archive old reports (optional)

## Support

For issues:
- Check Frappe documentation: docs.frappe.io
- Review error logs
- Contact system administrator
```

### Step 2: Commit documentation

**Command:**
```bash
git add docs/admin-guides/auto-email-report-setup.md
git commit -m "docs: add auto email report setup guide

- Step-by-step configuration instructions
- Monthly and quarterly setup
- Troubleshooting tips
- Example configurations

Refs: WB GRM Compliance Phase 2"
```

---

## Task 4: Public Report Archive Page (Optional)

**Files:**
- Create: `egrm/www/grm-public/reports/index.html`
- Create: `egrm/www/grm-public/reports/index.py`

### Step 1: Create reports directory

**Command:**
```bash
mkdir -p egrm/www/grm-public/reports
```

### Step 2: Create reports page Python

**File:** `egrm/www/grm-public/reports/index.py`

**Code:**
```python
"""
GRM Public Reports Archive
Lists publicly available GRM reports
"""

import frappe
import os


def get_context(context):
    """
    Get context for public reports archive

    Args:
        context (dict): Template context
    """
    context.no_cache = 1

    # Get public reports from files directory
    # Admins manually upload PDFs to: public/files/grm_reports/
    reports = get_public_reports()

    context.reports = reports
    context.site_url = frappe.utils.get_url()


def get_public_reports():
    """
    Get list of public report files
    Returns list of report metadata
    """
    reports = []

    # Path to public reports (manually uploaded)
    site_path = frappe.get_site_path()
    reports_path = os.path.join(site_path, "public", "files", "grm_reports")

    # Create directory if doesn't exist
    if not os.path.exists(reports_path):
        os.makedirs(reports_path)
        return reports

    # Walk through directory
    for root, dirs, files in os.walk(reports_path):
        for file in files:
            if file.endswith('.pdf'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, site_path)

                # Extract metadata from filename
                # Expected format: YYYY-MM_Project_Monthly.pdf or YYYY-QN_Project_Quarterly.pdf
                parts = file.replace('.pdf', '').split('_')

                reports.append({
                    "filename": file,
                    "url": f"/files/{os.path.relpath(file_path, os.path.join(site_path, 'public'))}",
                    "date": parts[0] if len(parts) > 0 else "Unknown",
                    "project": parts[1] if len(parts) > 1 else "All Projects",
                    "type": parts[2] if len(parts) > 2 else "Report"
                })

    # Sort by date descending
    reports.sort(key=lambda x: x["date"], reverse=True)

    return reports
```

### Step 3: Create reports page HTML

**File:** `egrm/www/grm-public/reports/index.html`

**Code:**
```html
{% extends "templates/web.html" %}

{% block title %}Public Reports Archive{% endblock %}

{% block head %}
<style>
.report-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: box-shadow 0.3s;
}
.report-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.report-info h4 {
    margin: 0 0 10px 0;
    color: #333;
}
.report-meta {
    color: #666;
    font-size: 0.9em;
}
.download-btn {
    background: #667eea;
    color: white;
    padding: 10px 20px;
    border-radius: 6px;
    text-decoration: none;
    transition: background 0.3s;
}
.download-btn:hover {
    background: #764ba2;
    color: white;
}
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #666;
}
</style>
{% endblock %}

{% block page_content %}
<div class="container">
    <h1>GRM Public Reports Archive</h1>
    <p class="lead">Historical monthly and quarterly transparency reports</p>

    {% if reports %}
    <div style="margin-top: 30px;">
        {% for report in reports %}
        <div class="report-card">
            <div class="report-info">
                <h4>{{ report.type }} Report - {{ report.date }}</h4>
                <div class="report-meta">
                    <span>📁 Project: {{ report.project }}</span>
                    <span style="margin-left: 20px;">📄 {{ report.filename }}</span>
                </div>
            </div>
            <a href="{{ report.url }}" target="_blank" class="download-btn">
                📥 Download PDF
            </a>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <h3>No Reports Available</h3>
        <p>Public reports will appear here once generated.</p>
        <p style="color: #999; font-size: 0.9em;">
            Administrators: Upload PDF reports to <code>public/files/grm_reports/</code>
        </p>
    </div>
    {% endif %}

    <div style="margin-top: 50px; text-align: center;">
        <a href="/grm-public" class="btn btn-default">← Back to Homepage</a>
    </div>
</div>
{% endblock %}
```

### Step 4: Create sample report upload instructions

**File:** `docs/admin-guides/report-archive-upload.md`

**Code:**
```markdown
# Report Archive Upload Instructions

## Manual Upload Process

After Auto Email Report generates monthly/quarterly reports:

### Step 1: Download Report PDF

1. Go to **Home > Email Queue**
2. Find the sent report email
3. Download PDF attachment

### Step 2: Rename File

Use standard naming format:
```
YYYY-MM_ProjectName_Monthly.pdf
YYYY-Q1_ProjectName_Quarterly.pdf
```

Examples:
- `2025-11_Infrastructure_Monthly.pdf`
- `2025-Q4_Infrastructure_Quarterly.pdf`
- `2025-10_AllProjects_Monthly.pdf`

### Step 3: Upload to Public Folder

**Via Frappe UI:**
1. Go to **Home > File Manager**
2. Navigate to `/public/files/grm_reports/`
3. Upload renamed PDF

**Via SSH:**
```bash
# Copy file to public folder
cp report.pdf ~/frappe-bench/sites/[site-name]/public/files/grm_reports/

# Set permissions
chmod 644 ~/frappe-bench/sites/[site-name]/public/files/grm_reports/*.pdf
```

### Step 4: Verify

1. Visit `/grm-public/reports`
2. Verify report appears in list
3. Click download to test

## Automated Upload (Future Enhancement)

For automatic archiving, create custom script in Auto Email Report after_insert hook.
```

### Step 5: Test reports archive

**Browser:** Navigate to `http://[your-site]/grm-public/reports`

**Expected:** Page loads (empty or with any test PDFs uploaded)

### Step 6: Commit reports archive

**Command:**
```bash
git add egrm/www/grm-public/reports/ docs/admin-guides/report-archive-upload.md
git commit -m "feat: add public reports archive page

- Display historical monthly/quarterly reports
- Manual upload workflow documented
- Public access to transparency reports

Refs: WB GRM Compliance Phase 2"
```

---

## Final Steps

### Step 1: Create phase 2 summary documentation

**File:** `docs/admin-guides/phase2-summary.md`

**Code:**
```markdown
# Phase 2 Implementation Summary

## Completed Features

### 1. GRM Public Monthly Report
- **Location:** Home > Reports > GRM Public Monthly Report
- **Purpose:** Monthly public transparency report
- **Features:**
  - Summary cards (received, resolved, pending, appealed)
  - Category breakdown
  - Charts
  - Configurable filters

### 2. GRM Public Quarterly Report
- **Location:** Home > Reports > GRM Public Quarterly Report
- **Purpose:** Quarterly public transparency report
- **Features:** Same as monthly, defaults to quarterly dates

### 3. Auto Email Report Setup
- **Documentation:** docs/admin-guides/auto-email-report-setup.md
- **Configuration:** Via Frappe UI (Home > Settings > Auto Email Report)
- **No Custom Code:** Uses Frappe standard feature

### 4. Public Reports Archive
- **URL:** /grm-public/reports
- **Purpose:** Historical report downloads
- **Upload:** Manual process documented

## Administrator Tasks

### Initial Setup (One-Time)

1. **Create Auto Email Report for Monthly:**
   - Navigate: Home > Settings > Auto Email Report > New
   - Configure per docs/admin-guides/auto-email-report-setup.md
   - Test with "Send Now" button
   - Enable when ready

2. **Create Auto Email Report for Quarterly:**
   - Same process as monthly
   - Set frequency to "Quarterly"

3. **Configure Recipients:**
   - Update email addresses for stakeholders
   - Different lists for monthly vs quarterly (if needed)

### Ongoing Maintenance

**Monthly:**
- Reports auto-send on 1st of month
- Check Email Queue for delivery status
- Download and archive PDFs (optional)

**Quarterly:**
- Reports auto-send on 1st of Jan/Apr/Jul/Oct
- Review content for accuracy
- Share link to public archive

## Compliance Status

✅ **WB Requirement Met:** "Regular (monthly or quarterly) reports to the public"

- Monthly reports: Configured and automated
- Quarterly reports: Configured and automated
- Public distribution: Via email + public archive
- Content: Complaints received, resolved, not resolved, referred to third party

## Next Phase

**Phase 3:** Notifications & SLA Tracking
- Citizen receipts and roadmap
- SLA tracking per administrative level
- Auto-escalation workflow
```

### Step 2: Test both reports end-to-end

**Testing Checklist:**

1. ✅ Monthly report runs with filters
2. ✅ Quarterly report runs with filters
3. ✅ Summary cards display correctly
4. ✅ Charts render
5. ✅ Data is accurate
6. ✅ Can download XLSX
7. ✅ Can download PDF
8. ✅ Auto Email Report configuration works
9. ✅ Test email sends successfully
10. ✅ Reports archive page displays

### Step 3: Commit phase 2 summary

**Command:**
```bash
git add docs/admin-guides/phase2-summary.md
git commit -m "docs: add phase 2 implementation summary

- Document completed features
- Administrator setup tasks
- Compliance status
- Ongoing maintenance guide

Refs: WB GRM Compliance Phase 2 Complete"
```

### Step 4: Create phase 2 tag

**Command:**
```bash
git tag -a v1.0-phase2-automated-reporting -m "Phase 2: Automated Public Reporting

Implemented:
- GRM Public Monthly Report (Script Report)
- GRM Public Quarterly Report (Script Report)
- Auto Email Report configuration docs
- Public reports archive page
- Complete admin documentation

Compliance: Addresses WB monthly/quarterly reporting requirement
Next: Phase 3 (Notifications & SLA Tracking)"

git push origin main --tags
```

---

**Phase 2 Complete!**

Automated monthly and quarterly public reporting now meets World Bank requirements. System can automatically generate and distribute transparency reports.

**Next:** Phase 3 will implement citizen receipt system and SLA tracking.
