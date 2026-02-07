# GRM Notification Configuration Guide

## Overview

This guide explains how to configure automated notifications for your GRM project.

## Prerequisites

- GRM Project created
- Email settings configured in Frappe (Setup > Email Account)
- Email Templates created (optional, for email notifications)

## Step 1: Create Notification Templates

1. Go to **eGRM > GRM Notification Template > New**
2. Fill in:
   - **Template Name**: Unique identifier (e.g., "Project A Receipt")
   - **Template Type**: Select type (Receipt, Acknowledgment, In Progress, Resolved, Closed, Escalated, SLA Reminder)
   - **Email Template**: Link to a Frappe Email Template
   - **Enable SMS**: Check if SMS needed
   - **SMS Message**: Jinja2 template text
   - **Project**: Leave blank for shared, or select a specific project
3. Save

### Available Template Variables (SMS)

- `{{ tracking_code }}` - Issue tracking code
- `{{ subject }}` - Issue description
- `{{ status }}` - Current status
- `{{ administrative_region }}` - Region name
- `{{ complainant_name }}` - Complainant name
- `{{ sla_acknowledgment_due }}` - Acknowledgment deadline
- `{{ sla_resolution_due }}` - Resolution deadline
- `{{ sla_days_remaining }}` - Days until resolution deadline

## Step 2: Configure Project Notifications

1. Go to **GRM Project > [Your Project] > Edit**
2. Expand **Notification Settings** section
3. Check **Enable Automated Notifications**
4. Select templates for each event type
5. Save

## Step 3: Test Notifications

1. Create a test complaint
2. Check email received (Receipt notification)
3. Change status - verify acknowledgment/progress notifications
4. Resolve issue - verify resolution notification

## Troubleshooting

**No emails sent:**
- Check Email Account is configured in Frappe
- Check Email Queue for errors
- Verify template is active
- Ensure citizen contact information is populated

**SMS not working:**
- Check SMS Settings in Frappe
- Verify SMS provider credentials
- Check Error Log for SMS errors
