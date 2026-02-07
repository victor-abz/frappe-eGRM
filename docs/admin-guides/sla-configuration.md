# GRM SLA Configuration Guide

## Overview

This guide explains how to configure Service Level Agreements (SLAs) for your GRM administrative hierarchy.

## Step 1: Configure SLA per Administrative Level

1. Go to **eGRM > GRM Administrative Level Type > [Level] > Edit**
2. Expand **SLA Configuration** section
3. Set timeframes:
   - **Acknowledgment Days**: Business days to acknowledge (default: 7)
   - **Resolution Days**: Business days to resolve (default: 30)
   - **Reminder Before (Days)**: Days before deadline to send reminder (default: 2)
   - **Auto-Escalate on SLA Breach**: Check to enable automatic escalation
4. Save

### Example Configuration

| Level | Acknowledgment | Resolution | Reminder | Auto-Escalate |
|-------|---------------|------------|----------|---------------|
| Village | 7 days | 30 days | 2 days | Yes |
| District | 5 days | 45 days | 3 days | Yes |
| Province | 3 days | 60 days | 5 days | No |

## Step 2: Monitor SLA Compliance

### View SLA Status

1. Go to **GRM Issue List**
2. Add filters: SLA Resolution Status = "Breached"
3. Review list of breached issues

### SLA Dashboard Data

Access via: `bench execute egrm.egrm.utils.sla_manager.get_sla_dashboard_data --kwargs "{'project': 'Project Name'}"`

## Step 3: Handle Escalations

### Automatic Escalation

When SLA is breached and auto-escalate is enabled:
1. Issue moves to parent administrative region
2. SLA recalculated based on new level
3. Escalation notification sent
4. Comment added to issue

### Manual Escalation

1. Open GRM Issue
2. Click **Actions > Escalate to Higher Level**
3. Enter reason and click **Escalate**

## Scheduled Jobs

SLA monitoring runs daily:
- Updates all SLA statuses
- Sends reminder notifications
- Triggers auto-escalation for breached issues

Manual run: `bench execute egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla`

## Resolution Agreements

When resolving an issue:
1. Set status to Resolved
2. The **Resolution Agreement** section becomes visible
3. Upload signed agreement document (PDF/image)
4. Fill in agreement date, parties, and notes
