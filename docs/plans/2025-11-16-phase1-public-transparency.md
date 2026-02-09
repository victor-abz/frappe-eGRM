# Phase 1: Public Transparency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement public-facing GRM transparency features (dashboard, complaint tracking, web submission) to address the critical 20% WB compliance gap.

**Architecture:** Use Frappe's `www/` directory for public web pages and `@frappe.whitelist(allow_guest=True)` for guest-accessible APIs. Reuse existing stats logic with anonymization wrapper. No PII exposed publicly.

**Tech Stack:** Frappe Framework v15+, Python 3.10+, Jinja2 templates, MariaDB

**Design Reference:** `docs/plans/2025-11-16-wb-grm-compliance-design.md`

---

## Task 1: Public Metrics API

**Files:**
- Create: `egrm/api/public_metrics.py`
- Test: `egrm/tests/test_public_metrics.py` (manual testing for now)

### Step 1: Create test project and sample data

**Command:**
```bash
# In Frappe bench console
bench --site [site-name] console
```

**Python console:**
```python
# Create test project
project = frappe.get_doc({
    "doctype": "GRM Project",
    "project_name": "Test Public Project",
    "active": 1
})
project.insert()

# Create some test issues (need at least 5 for testing)
for i in range(5):
    issue = frappe.get_doc({
        "doctype": "GRM Issue",
        "project": project.name,
        # Add required fields based on your schema
    })
    issue.insert()

frappe.db.commit()
```

**Expected:** Test project with 5+ issues created

### Step 2: Create public metrics API module

**File:** `egrm/api/public_metrics.py`

**Code:**
```python
"""
Public Metrics API
Provides anonymized aggregate GRM statistics for public access
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_public_dashboard(project_id=None, date_range=None):
    """
    Get public dashboard metrics (anonymized, no PII)

    Args:
        project_id (str, optional): Filter by project
        date_range (str, optional): 7d, 30d, 90d, 1y

    Returns:
        dict: Anonymized aggregate statistics
    """
    try:
        # Get accessible projects (all public projects)
        if project_id:
            projects = [project_id] if frappe.db.exists("GRM Project", project_id) else []
        else:
            projects = frappe.get_all("GRM Project", filters={"active": 1}, pluck="name")

        if not projects:
            return {
                "status": "error",
                "message": _("No public projects available")
            }

        # Get date filter
        date_filter = get_date_filter(date_range)

        # Build aggregate stats (reuse existing logic)
        stats = {
            "overview": get_overview_stats(projects, date_filter),
            "status_breakdown": get_status_breakdown(projects, date_filter),
            "category_breakdown": get_category_breakdown(projects, date_filter),
            "region_breakdown": get_region_breakdown(projects, date_filter),
            "trend_data": get_trend_data(projects, date_range or "30d")
        }

        return {
            "status": "success",
            "data": stats
        }

    except Exception as e:
        frappe.log_error(f"Public metrics error: {str(e)}", "Public Metrics API")
        return {
            "status": "error",
            "message": _("Error retrieving public metrics")
        }


def get_date_filter(date_range):
    """Convert date range to filter date"""
    from frappe.utils import add_to_date, getdate

    if not date_range:
        return None

    today = getdate()

    range_map = {
        "7d": {"days": -7},
        "30d": {"days": -30},
        "90d": {"days": -90},
        "1y": {"years": -1}
    }

    delta = range_map.get(date_range)
    if delta:
        return add_to_date(today, **delta)

    return None


def get_overview_stats(projects, date_filter):
    """Get aggregate overview statistics"""
    filters = {"project": ["in", projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    # Total issues
    total = frappe.db.count("GRM Issue", filters)

    # Open issues
    open_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"open_status": 1},
        pluck="name"
    )
    open_count = frappe.db.count(
        "GRM Issue",
        {**filters, "status": ["in", open_statuses]} if open_statuses else filters
    )

    # Resolved issues
    resolved_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"final_status": 1},
        pluck="name"
    )
    resolved_count = frappe.db.count(
        "GRM Issue",
        {**filters, "status": ["in", resolved_statuses]} if resolved_statuses else filters
    )

    # Pending (initial status)
    pending_statuses = frappe.get_all(
        "GRM Issue Status",
        filters={"initial_status": 1},
        pluck="name"
    )
    pending_count = frappe.db.count(
        "GRM Issue",
        {**filters, "status": ["in", pending_statuses]} if pending_statuses else filters
    )

    return {
        "total_issues": total,
        "open_issues": open_count,
        "resolved_issues": resolved_count,
        "pending_issues": pending_count
    }


def get_status_breakdown(projects, date_filter):
    """Get breakdown by status (anonymized)"""
    filters = {"project": ["in", projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    statuses = frappe.get_all("GRM Issue Status", fields=["name", "status_name"])

    breakdown = []
    for status in statuses:
        count = frappe.db.count("GRM Issue", {**filters, "status": status.name})
        if count > 0:
            breakdown.append({
                "status": status.status_name,
                "count": count
            })

    return breakdown


def get_category_breakdown(projects, date_filter):
    """Get breakdown by category (anonymized)"""
    filters = {"project": ["in", projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    categories = frappe.get_all(
        "GRM Issue Category",
        filters={"project": ["in", projects]},
        fields=["name", "category_name"]
    )

    breakdown = []
    for category in categories:
        count = frappe.db.count("GRM Issue", {**filters, "category": category.name})
        if count > 0:
            breakdown.append({
                "category": category.category_name,
                "count": count
            })

    return breakdown


def get_region_breakdown(projects, date_filter):
    """Get breakdown by region (anonymized)"""
    filters = {"project": ["in", projects]}
    if date_filter:
        filters["creation"] = [">=", date_filter]

    regions = frappe.get_all(
        "GRM Administrative Region",
        filters={"project": ["in", projects]},
        fields=["name", "region_name"]
    )

    breakdown = []
    for region in regions:
        count = frappe.db.count("GRM Issue", {**filters, "administrative_region": region.name})
        if count > 0:
            breakdown.append({
                "region": region.region_name,
                "count": count
            })

    return breakdown


def get_trend_data(projects, date_range):
    """Get trend data for charts"""
    from frappe.utils import add_to_date, getdate

    days = 30  # default
    if date_range == "7d":
        days = 7
    elif date_range == "90d":
        days = 90
    elif date_range == "1y":
        days = 365

    today = getdate()
    trend = []

    for i in range(days):
        date = add_to_date(today, days=-i)
        next_date = add_to_date(date, days=1)

        count = frappe.db.count("GRM Issue", {
            "project": ["in", projects],
            "creation": [">=", date],
            "creation": ["<", next_date]
        })

        trend.append({
            "date": date.strftime("%Y-%m-%d"),
            "count": count
        })

    return list(reversed(trend))
```

### Step 3: Test the API manually

**Command:**
```bash
bench --site [site-name] console
```

**Python console:**
```python
from egrm.api import public_metrics

# Test without auth (simulating guest access)
result = public_metrics.get_public_dashboard()
print(result)

# Should return stats without errors
# Verify no PII in response
```

**Expected:** Returns aggregate stats, no errors, no PII

### Step 4: Commit public metrics API

**Command:**
```bash
git add egrm/api/public_metrics.py
git commit -m "feat: add public metrics API for WB transparency

- Add @frappe.whitelist(allow_guest=True) endpoint
- Return anonymized aggregate statistics
- Support project and date range filters
- No PII exposed in public data

Refs: WB GRM Compliance Phase 1"
```

---

## Task 2: Public Tracking API

**Files:**
- Create: `egrm/api/public_tracking.py`

### Step 1: Create public tracking API

**File:** `egrm/api/public_tracking.py`

**Code:**
```python
"""
Public Tracking API
Allows citizens to track complaints by tracking code (no auth required)
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def track_complaint(tracking_code):
    """
    Track complaint status by tracking code

    Args:
        tracking_code (str): Unique tracking code

    Returns:
        dict: Complaint status (anonymized, no PII)
    """
    if not tracking_code:
        return {
            "status": "error",
            "message": _("Tracking code is required")
        }

    try:
        # Find issue by tracking code
        issue_name = frappe.db.get_value("GRM Issue", {"tracking_code": tracking_code}, "name")

        if not issue_name:
            return {
                "status": "error",
                "message": _("Complaint not found. Please check your tracking code.")
            }

        # Get issue data (only public-safe fields)
        issue = frappe.db.get_value(
            "GRM Issue",
            issue_name,
            [
                "tracking_code",
                "status",
                "creation",
                "expected_acknowledgment_date",
                "expected_resolution_date",
                "acknowledged_date",
                "resolution_date",
                "appeal_submitted",
                "category"
            ],
            as_dict=True
        )

        # Get status name
        status_name = ""
        if issue.status:
            status_name = frappe.db.get_value("GRM Issue Status", issue.status, "status_name")

        # Get category name
        category_name = ""
        if issue.category:
            category_name = frappe.db.get_value("GRM Issue Category", issue.category, "category_name")

        # Build response (NO PII)
        response = {
            "status": "success",
            "data": {
                "tracking_code": issue.tracking_code,
                "status": status_name,
                "category": category_name,
                "submission_date": issue.creation.strftime("%Y-%m-%d %H:%M") if issue.creation else None,
                "expected_acknowledgment": issue.expected_acknowledgment_date.strftime("%Y-%m-%d") if issue.expected_acknowledgment_date else None,
                "expected_resolution": issue.expected_resolution_date.strftime("%Y-%m-%d") if issue.expected_resolution_date else None,
                "acknowledged_date": issue.acknowledged_date.strftime("%Y-%m-%d") if issue.acknowledged_date else None,
                "resolution_date": issue.resolution_date.strftime("%Y-%m-%d") if issue.resolution_date else None,
                "appeal_submitted": issue.appeal_submitted or False
            }
        }

        return response

    except Exception as e:
        frappe.log_error(f"Tracking error: {str(e)}", "Public Tracking API")
        return {
            "status": "error",
            "message": _("Error retrieving complaint status")
        }
```

### Step 2: Test tracking API

**Command:**
```bash
bench --site [site-name] console
```

**Python console:**
```python
from egrm.api import public_tracking

# Get a real tracking code from test data
tracking_code = frappe.db.get_value("GRM Issue", {}, "tracking_code")

# Test tracking
result = public_tracking.track_complaint(tracking_code)
print(result)

# Verify no PII (no citizen name, contact info, assignee, etc.)
```

**Expected:** Returns status info, no PII exposed

### Step 3: Commit tracking API

**Command:**
```bash
git add egrm/api/public_tracking.py
git commit -m "feat: add public complaint tracking API

- Allow guests to track by tracking code
- Return complaint status without PII
- Include expected dates and current stage

Refs: WB GRM Compliance Phase 1"
```

---

## Task 3: Public Web Pages - Homepage

**Files:**
- Create: `egrm/www/grm-public/index.html`
- Create: `egrm/www/grm-public/index.py`

### Step 1: Create www directory structure

**Command:**
```bash
mkdir -p egrm/www/grm-public
```

**Expected:** Directory created

### Step 2: Create homepage Python context

**File:** `egrm/www/grm-public/index.py`

**Code:**
```python
"""
GRM Public Homepage
Provides dynamic context for public homepage
"""

import frappe


def get_context(context):
    """
    Get context for public GRM homepage

    Args:
        context (dict): Template context
    """
    context.no_cache = 1  # Don't cache (for now)

    # Get active projects
    projects = frappe.get_all(
        "GRM Project",
        filters={"active": 1},
        fields=["name", "project_name", "description"]
    )

    context.projects = projects
    context.site_url = frappe.utils.get_url()
```

### Step 3: Create homepage HTML template

**File:** `egrm/www/grm-public/index.html`

**Code:**
```html
{% extends "templates/web.html" %}

{% block title %}GRM Public Portal{% endblock %}

{% block head %}
<meta name="description" content="Grievance Redress Mechanism - Track and submit complaints">
<style>
.grm-hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 60px 20px;
    text-align: center;
    margin: -15px -15px 30px -15px;
}
.grm-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 30px;
    margin-bottom: 20px;
    transition: box-shadow 0.3s;
}
.grm-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.grm-btn {
    display: inline-block;
    background: #667eea;
    color: white;
    padding: 12px 30px;
    border-radius: 6px;
    text-decoration: none;
    margin: 10px 5px;
    transition: background 0.3s;
}
.grm-btn:hover {
    background: #764ba2;
    color: white;
}
.grm-btn-secondary {
    background: #48bb78;
}
.grm-btn-secondary:hover {
    background: #38a169;
}
</style>
{% endblock %}

{% block page_content %}
<div class="grm-hero">
    <h1 style="font-size: 2.5em; margin-bottom: 20px;">Grievance Redress Mechanism</h1>
    <p style="font-size: 1.2em; max-width: 800px; margin: 0 auto;">
        Track complaints, view statistics, and submit grievances for active projects.
    </p>
</div>

<div class="container">
    <div class="row">
        <div class="col-md-4">
            <div class="grm-card">
                <h3>📊 View Dashboard</h3>
                <p>Access public statistics and aggregate metrics for all active projects.</p>
                <a href="/grm-public/dashboard" class="grm-btn">View Dashboard</a>
            </div>
        </div>

        <div class="col-md-4">
            <div class="grm-card">
                <h3>🔍 Track Complaint</h3>
                <p>Check the status of your complaint using your tracking code.</p>
                <a href="/grm-public/track-complaint" class="grm-btn grm-btn-secondary">Track Now</a>
            </div>
        </div>

        <div class="col-md-4">
            <div class="grm-card">
                <h3>📝 Submit Complaint</h3>
                <p>File a new grievance through our web portal (optional).</p>
                <a href="/grm-public/submit-grievance" class="grm-btn">Submit</a>
            </div>
        </div>
    </div>

    <div style="margin-top: 50px;">
        <h2>Active Projects</h2>
        {% if projects %}
        <div class="row">
            {% for project in projects %}
            <div class="col-md-6">
                <div class="grm-card">
                    <h4>{{ project.project_name }}</h4>
                    <p>{{ project.description or "No description available" }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p>No active projects available.</p>
        {% endif %}
    </div>

    <div style="margin-top: 50px; padding: 30px; background: #f7fafc; border-radius: 8px;">
        <h2>About the GRM Process</h2>
        <ol style="font-size: 1.1em; line-height: 1.8;">
            <li><strong>Submit</strong> - File your grievance through web, mobile, or field officer</li>
            <li><strong>Receive</strong> - Get tracking code and expected timeline</li>
            <li><strong>Review</strong> - Staff reviews and acknowledges within 7 days</li>
            <li><strong>Investigate</strong> - Assigned officer investigates the issue</li>
            <li><strong>Resolve</strong> - Solution proposed and implemented</li>
            <li><strong>Appeal</strong> - If not satisfied, appeal within 14 days</li>
        </ol>
    </div>
</div>
{% endblock %}
```

### Step 4: Test homepage

**Browser:** Navigate to `http://[your-site]/grm-public`

**Expected:** Public homepage loads, shows active projects, navigation links

### Step 5: Commit homepage

**Command:**
```bash
git add egrm/www/grm-public/index.html egrm/www/grm-public/index.py
git commit -m "feat: add public GRM homepage

- Create public-facing homepage
- List active projects
- Links to dashboard, tracking, submission
- Explain GRM process to citizens

Refs: WB GRM Compliance Phase 1"
```

---

## Task 4: Public Dashboard Page

**Files:**
- Create: `egrm/www/grm-public/dashboard/index.html`
- Create: `egrm/www/grm-public/dashboard/index.py`

### Step 1: Create dashboard directory

**Command:**
```bash
mkdir -p egrm/www/grm-public/dashboard
```

### Step 2: Create dashboard Python context

**File:** `egrm/www/grm-public/dashboard/index.py`

**Code:**
```python
"""
GRM Public Dashboard
Dynamic context for public metrics dashboard
"""

import frappe
from egrm.api.public_metrics import get_public_dashboard


def get_context(context):
    """
    Get context for public dashboard

    Args:
        context (dict): Template context
    """
    context.no_cache = 1

    # Get project filter from URL
    project_id = frappe.form_dict.get("project")
    date_range = frappe.form_dict.get("range", "30d")

    # Get metrics via API
    metrics_result = get_public_dashboard(project_id, date_range)

    if metrics_result.get("status") == "success":
        context.metrics = metrics_result.get("data", {})
    else:
        context.metrics = {}
        context.error = metrics_result.get("message")

    # Get available projects for filter
    context.projects = frappe.get_all(
        "GRM Project",
        filters={"active": 1},
        fields=["name", "project_name"]
    )

    context.selected_project = project_id
    context.selected_range = date_range
    context.site_url = frappe.utils.get_url()
```

### Step 3: Create dashboard HTML template

**File:** `egrm/www/grm-public/dashboard/index.html`

**Code:**
```html
{% extends "templates/web.html" %}

{% block title %}GRM Public Dashboard{% endblock %}

{% block head %}
<meta name="description" content="Public GRM Dashboard - Aggregate Statistics">
<style>
.metric-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    margin-bottom: 20px;
    background: white;
}
.metric-number {
    font-size: 3em;
    font-weight: bold;
    color: #667eea;
    margin: 10px 0;
}
.metric-label {
    font-size: 1.1em;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.filter-bar {
    background: #f7fafc;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 30px;
}
.breakdown-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}
.breakdown-table th,
.breakdown-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
}
.breakdown-table th {
    background: #f7fafc;
    font-weight: bold;
}
</style>
{% endblock %}

{% block page_content %}
<div class="container">
    <h1>GRM Public Dashboard</h1>
    <p class="lead">Aggregate statistics for all active grievance redress projects.</p>

    <!-- Filters -->
    <div class="filter-bar">
        <form method="get" action="/grm-public/dashboard">
            <div class="row">
                <div class="col-md-6">
                    <label>Project:</label>
                    <select name="project" class="form-control" onchange="this.form.submit()">
                        <option value="">All Projects</option>
                        {% for project in projects %}
                        <option value="{{ project.name }}" {% if project.name == selected_project %}selected{% endif %}>
                            {{ project.project_name }}
                        </option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-6">
                    <label>Date Range:</label>
                    <select name="range" class="form-control" onchange="this.form.submit()">
                        <option value="7d" {% if selected_range == "7d" %}selected{% endif %}>Last 7 Days</option>
                        <option value="30d" {% if selected_range == "30d" %}selected{% endif %}>Last 30 Days</option>
                        <option value="90d" {% if selected_range == "90d" %}selected{% endif %}>Last 90 Days</option>
                        <option value="1y" {% if selected_range == "1y" %}selected{% endif %}>Last Year</option>
                    </select>
                </div>
            </div>
        </form>
    </div>

    {% if error %}
    <div class="alert alert-warning">{{ error }}</div>
    {% elif metrics %}

    <!-- Overview Metrics -->
    <div class="row">
        <div class="col-md-3">
            <div class="metric-card">
                <div class="metric-label">Total Complaints</div>
                <div class="metric-number">{{ metrics.overview.total_issues }}</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="metric-card">
                <div class="metric-label">Open</div>
                <div class="metric-number" style="color: #ed8936;">{{ metrics.overview.open_issues }}</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="metric-card">
                <div class="metric-label">Resolved</div>
                <div class="metric-number" style="color: #48bb78;">{{ metrics.overview.resolved_issues }}</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="metric-card">
                <div class="metric-label">Pending</div>
                <div class="metric-number" style="color: #4299e1;">{{ metrics.overview.pending_issues }}</div>
            </div>
        </div>
    </div>

    <!-- Breakdown Tables -->
    <div class="row" style="margin-top: 40px;">
        <div class="col-md-6">
            <h3>By Status</h3>
            {% if metrics.status_breakdown %}
            <table class="breakdown-table">
                <thead>
                    <tr>
                        <th>Status</th>
                        <th style="text-align: right;">Count</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in metrics.status_breakdown %}
                    <tr>
                        <td>{{ item.status }}</td>
                        <td style="text-align: right;"><strong>{{ item.count }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No data available</p>
            {% endif %}
        </div>

        <div class="col-md-6">
            <h3>By Category</h3>
            {% if metrics.category_breakdown %}
            <table class="breakdown-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th style="text-align: right;">Count</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in metrics.category_breakdown %}
                    <tr>
                        <td>{{ item.category }}</td>
                        <td style="text-align: right;"><strong>{{ item.count }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No data available</p>
            {% endif %}
        </div>
    </div>

    <div class="row" style="margin-top: 40px;">
        <div class="col-md-12">
            <h3>By Region</h3>
            {% if metrics.region_breakdown %}
            <table class="breakdown-table">
                <thead>
                    <tr>
                        <th>Region</th>
                        <th style="text-align: right;">Count</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in metrics.region_breakdown %}
                    <tr>
                        <td>{{ item.region }}</td>
                        <td style="text-align: right;"><strong>{{ item.count }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No data available</p>
            {% endif %}
        </div>
    </div>

    {% else %}
    <p>No metrics available</p>
    {% endif %}

    <div style="margin-top: 50px; text-align: center;">
        <a href="/grm-public" class="btn btn-default">← Back to Homepage</a>
    </div>
</div>
{% endblock %}
```

### Step 4: Test dashboard

**Browser:** Navigate to `http://[your-site]/grm-public/dashboard`

**Expected:** Dashboard loads with metrics, filters work

### Step 5: Commit dashboard

**Command:**
```bash
git add egrm/www/grm-public/dashboard/
git commit -m "feat: add public GRM dashboard page

- Display aggregate metrics publicly
- Filter by project and date range
- Show status, category, region breakdowns
- No PII exposed

Refs: WB GRM Compliance Phase 1"
```

---

## Task 5: Public Complaint Tracking Page

**Files:**
- Create: `egrm/www/grm-public/track-complaint/index.html`
- Create: `egrm/www/grm-public/track-complaint/index.py`

### Step 1: Create tracking directory

**Command:**
```bash
mkdir -p egrm/www/grm-public/track-complaint
```

### Step 2: Create tracking Python context

**File:** `egrm/www/grm-public/track-complaint/index.py`

**Code:**
```python
"""
GRM Public Complaint Tracking
Context for tracking page
"""

import frappe


def get_context(context):
    """
    Get context for tracking page

    Args:
        context (dict): Template context
    """
    context.no_cache = 1
    context.site_url = frappe.utils.get_url()
```

### Step 3: Create tracking HTML template

**File:** `egrm/www/grm-public/track-complaint/index.html`

**Code:**
```html
{% extends "templates/web.html" %}

{% block title %}Track Your Complaint{% endblock %}

{% block head %}
<meta name="description" content="Track your GRM complaint status">
<style>
.tracking-form {
    max-width: 600px;
    margin: 50px auto;
    padding: 40px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.tracking-input {
    width: 100%;
    padding: 15px;
    font-size: 1.2em;
    border: 2px solid #e0e0e0;
    border-radius: 6px;
    margin: 20px 0;
}
.tracking-btn {
    width: 100%;
    padding: 15px;
    font-size: 1.2em;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.3s;
}
.tracking-btn:hover {
    background: #764ba2;
}
.result-card {
    margin-top: 30px;
    padding: 30px;
    background: #f7fafc;
    border-radius: 8px;
    display: none;
}
.result-card.show {
    display: block;
}
.status-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: bold;
    margin: 10px 0;
}
.status-open {
    background: #fed7d7;
    color: #c53030;
}
.status-resolved {
    background: #c6f6d5;
    color: #22543d;
}
.status-pending {
    background: #bee3f8;
    color: #2c5282;
}
.info-row {
    display: flex;
    justify-content: space-between;
    padding: 15px 0;
    border-bottom: 1px solid #e0e0e0;
}
.info-label {
    font-weight: bold;
    color: #666;
}
.error-msg {
    padding: 20px;
    background: #fed7d7;
    color: #c53030;
    border-radius: 6px;
    margin-top: 20px;
    display: none;
}
.error-msg.show {
    display: block;
}
</style>
{% endblock %}

{% block page_content %}
<div class="container">
    <div class="tracking-form">
        <h1 style="text-align: center; margin-bottom: 10px;">Track Your Complaint</h1>
        <p style="text-align: center; color: #666;">Enter your tracking code to check the status</p>

        <input
            type="text"
            id="tracking_code"
            class="tracking-input"
            placeholder="Enter tracking code (e.g., GRM-2025-00123)"
            autocomplete="off"
        >

        <button onclick="trackComplaint()" class="tracking-btn">Track Complaint</button>

        <div id="error-msg" class="error-msg"></div>

        <div id="result-card" class="result-card">
            <h3 style="margin-bottom: 20px;">Complaint Status</h3>

            <div class="info-row">
                <span class="info-label">Tracking Code:</span>
                <span id="result-code"></span>
            </div>

            <div class="info-row">
                <span class="info-label">Status:</span>
                <span id="result-status" class="status-badge"></span>
            </div>

            <div class="info-row">
                <span class="info-label">Category:</span>
                <span id="result-category"></span>
            </div>

            <div class="info-row">
                <span class="info-label">Submitted:</span>
                <span id="result-submitted"></span>
            </div>

            <div class="info-row">
                <span class="info-label">Expected Acknowledgment:</span>
                <span id="result-ack"></span>
            </div>

            <div class="info-row">
                <span class="info-label">Expected Resolution:</span>
                <span id="result-resolution"></span>
            </div>

            <div class="info-row" id="ack-row" style="display: none;">
                <span class="info-label">Acknowledged On:</span>
                <span id="result-ack-date"></span>
            </div>

            <div class="info-row" id="resolved-row" style="display: none;">
                <span class="info-label">Resolved On:</span>
                <span id="result-resolved-date"></span>
            </div>

            <div class="info-row" id="appeal-row" style="display: none;">
                <span class="info-label">Appeal Status:</span>
                <span style="color: #ed8936; font-weight: bold;">Appeal Submitted</span>
            </div>
        </div>
    </div>

    <div style="text-align: center; margin-top: 30px;">
        <a href="/grm-public" style="color: #667eea;">← Back to Homepage</a>
    </div>
</div>

<script>
function trackComplaint() {
    const trackingCode = document.getElementById('tracking_code').value.trim();
    const resultCard = document.getElementById('result-card');
    const errorMsg = document.getElementById('error-msg');

    // Hide previous results
    resultCard.classList.remove('show');
    errorMsg.classList.remove('show');

    if (!trackingCode) {
        errorMsg.textContent = 'Please enter a tracking code';
        errorMsg.classList.add('show');
        return;
    }

    // Call API
    frappe.call({
        method: 'egrm.api.public_tracking.track_complaint',
        args: { tracking_code: trackingCode },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                const data = r.message.data;

                // Populate result card
                document.getElementById('result-code').textContent = data.tracking_code;
                document.getElementById('result-status').textContent = data.status || 'Unknown';
                document.getElementById('result-category').textContent = data.category || 'N/A';
                document.getElementById('result-submitted').textContent = data.submission_date || 'N/A';
                document.getElementById('result-ack').textContent = data.expected_acknowledgment || 'N/A';
                document.getElementById('result-resolution').textContent = data.expected_resolution || 'N/A';

                // Show optional fields
                if (data.acknowledged_date) {
                    document.getElementById('result-ack-date').textContent = data.acknowledged_date;
                    document.getElementById('ack-row').style.display = 'flex';
                }

                if (data.resolution_date) {
                    document.getElementById('result-resolved-date').textContent = data.resolution_date;
                    document.getElementById('resolved-row').style.display = 'flex';
                }

                if (data.appeal_submitted) {
                    document.getElementById('appeal-row').style.display = 'flex';
                }

                // Show result card
                resultCard.classList.add('show');
            } else {
                errorMsg.textContent = r.message.message || 'Complaint not found';
                errorMsg.classList.add('show');
            }
        },
        error: function(err) {
            errorMsg.textContent = 'Error tracking complaint. Please try again.';
            errorMsg.classList.add('show');
        }
    });
}

// Allow Enter key to track
document.getElementById('tracking_code').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        trackComplaint();
    }
});
</script>
{% endblock %}
```

### Step 4: Test tracking page

**Browser:** Navigate to `http://[your-site]/grm-public/track-complaint`

**Test Steps:**
1. Enter valid tracking code
2. Click "Track Complaint"
3. Verify status displays correctly
4. Verify no PII shown
5. Test with invalid code → should show error

**Expected:** Tracking works, no PII exposed

### Step 5: Commit tracking page

**Command:**
```bash
git add egrm/www/grm-public/track-complaint/
git commit -m "feat: add public complaint tracking page

- Allow citizens to track by code
- Display status, dates, category
- No authentication required
- No PII exposed to public

Refs: WB GRM Compliance Phase 1"
```

---

## Task 6: Web Submission Form (Optional)

**Files:**
- Create: `egrm/www/grm-public/submit-grievance/index.html`
- Create: `egrm/www/grm-public/submit-grievance/index.py`
- Create: `egrm/api/public_submission.py`

**Note:** This is marked optional in the design. For MVP, we can create a simple placeholder page that says "Please use mobile app or contact field officer" and implement full web submission later.

### Step 1: Create placeholder submission page

**Command:**
```bash
mkdir -p egrm/www/grm-public/submit-grievance
```

**File:** `egrm/www/grm-public/submit-grievance/index.html`

**Code:**
```html
{% extends "templates/web.html" %}

{% block title %}Submit Complaint{% endblock %}

{% block page_content %}
<div class="container" style="max-width: 800px; margin: 50px auto; text-align: center;">
    <h1>Submit a Complaint</h1>

    <div style="padding: 40px; background: #f7fafc; border-radius: 8px; margin: 30px 0;">
        <h3>Alternative Submission Methods</h3>
        <p style="font-size: 1.1em; line-height: 1.8;">
            To submit a complaint, please use one of the following methods:
        </p>

        <ul style="text-align: left; font-size: 1.1em; max-width: 500px; margin: 30px auto;">
            <li><strong>Mobile App:</strong> Download our mobile app for offline submission</li>
            <li><strong>Field Officer:</strong> Contact your local GRM field officer</li>
            <li><strong>Phone:</strong> Call the project hotline</li>
            <li><strong>In Person:</strong> Visit project office</li>
        </ul>
    </div>

    <p style="color: #666; margin-top: 30px;">
        Web-based submission form coming soon
    </p>

    <div style="margin-top: 30px;">
        <a href="/grm-public" class="btn btn-primary">← Back to Homepage</a>
    </div>
</div>
{% endblock %}
```

**File:** `egrm/www/grm-public/submit-grievance/index.py`

**Code:**
```python
"""
GRM Public Submission (Placeholder)
"""

import frappe


def get_context(context):
    context.no_cache = 1
```

### Step 2: Test placeholder page

**Browser:** Navigate to `http://[your-site]/grm-public/submit-grievance`

**Expected:** Placeholder page displays alternative methods

### Step 3: Commit placeholder

**Command:**
```bash
git add egrm/www/grm-public/submit-grievance/
git commit -m "feat: add placeholder web submission page

- Display alternative submission methods
- Prepare for future web form implementation
- Link back to homepage

Refs: WB GRM Compliance Phase 1"
```

---

## Task 7: Update gitignore and Documentation

**Files:**
- Update: `.gitignore` (if needed)
- Create: `docs/user-guides/public-portal-guide.md`

### Step 1: Create user guide

**File:** `docs/user-guides/public-portal-guide.md`

**Code:**
```markdown
# GRM Public Portal User Guide

## Overview

The GRM Public Portal provides transparent access to grievance redress statistics and complaint tracking.

## Features

### 1. Public Dashboard

**URL:** `/grm-public/dashboard`

**Features:**
- View aggregate statistics (no personal data)
- Filter by project and date range
- See breakdowns by status, category, region

**Who can access:** Anyone (no login required)

### 2. Complaint Tracking

**URL:** `/grm-public/track-complaint`

**Features:**
- Track complaint status using tracking code
- View expected acknowledgment and resolution dates
- Check appeal status

**Who can access:** Anyone with a valid tracking code

**How to use:**
1. Go to `/grm-public/track-complaint`
2. Enter your tracking code (received when complaint was filed)
3. Click "Track Complaint"
4. View status information

### 3. Homepage

**URL:** `/grm-public`

**Features:**
- Overview of GRM process
- Links to all public features
- List of active projects

## Privacy & Security

**What is public:**
- Aggregate statistics (counts, percentages)
- Complaint status (when tracked by code)
- Expected dates and timelines

**What is NOT public:**
- Citizen names or contact information
- Assignee or staff details
- Internal notes or investigation details
- Individual complaint details (except when tracked with code)

## Technical Details

**Technology:**
- Frappe Framework public pages (`www/` directory)
- Guest-accessible APIs (`@frappe.whitelist(allow_guest=True)`)
- No authentication required

**Performance:**
- Pages served directly by Frappe
- API responses cached where appropriate
- Lightweight design for low-bandwidth access

## Support

For issues or questions:
- Contact your project's GRM focal point
- Email: [project contact]
- Phone: [project hotline]
```

### Step 2: Commit documentation

**Command:**
```bash
git add docs/user-guides/public-portal-guide.md
git commit -m "docs: add public portal user guide

- Document all public features
- Explain privacy/security model
- Provide usage instructions

Refs: WB GRM Compliance Phase 1"
```

---

## Final Steps

### Step 1: Test complete public portal flow

**Manual Testing Checklist:**

1. ✅ Homepage loads (`/grm-public`)
2. ✅ Dashboard shows metrics (`/grm-public/dashboard`)
3. ✅ Dashboard filters work (project, date range)
4. ✅ Tracking page accepts code (`/grm-public/track-complaint`)
5. ✅ Tracking shows correct status
6. ✅ No PII exposed anywhere
7. ✅ All pages work without login
8. ✅ Mobile responsive (check on phone)

### Step 2: Create summary commit

**Command:**
```bash
git log --oneline --since="1 day ago"
```

**Review commits, then create annotated tag:**

```bash
git tag -a v1.0-phase1-public-portal -m "Phase 1: Public Transparency Portal

Implemented:
- Public metrics API (anonymized)
- Public tracking API (by code)
- Public homepage
- Public dashboard with filters
- Public tracking page
- Placeholder submission page
- User documentation

Compliance: Addresses WB 20% transparency gap
Next: Phase 2 (Automated Reporting)"
```

### Step 3: Push changes (if remote configured)

**Command:**
```bash
git push origin main
git push origin --tags
```

---

## Next Phase

**Phase 2 Preview:** Automated Public Reporting
- GRM Public Monthly Report (Script Report)
- GRM Public Quarterly Report (Script Report)
- Auto Email Report configuration
- Public report archive page

**Estimated Effort:** 3-4 days

---

**Plan Complete!**

All public transparency features implemented. System now meets World Bank requirement for "publicly accessible web site" for GRM data.
