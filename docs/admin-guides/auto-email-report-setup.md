# Auto Email Report Setup Guide for GRM Reports

This guide explains how to configure Frappe's built-in **Auto Email Report** feature to automatically generate and email monthly and quarterly GRM transparency reports to stakeholders.

---

## Prerequisites

Before configuring Auto Email Reports, ensure the following are in place:

1. **Reports Created**: The GRM script reports must already exist in the system:
   - GRM Monthly Summary Report
   - GRM Quarterly Summary Report
   - Any project-specific report variants

2. **Email Configured**: Outgoing email must be working on your Frappe site:
   - Navigate to **Home > Settings > Email Account**
   - Verify at least one email account is configured with SMTP settings
   - Send a test email to confirm delivery

3. **User Permissions**: You must have the **System Manager** role to create Auto Email Reports.

4. **Recipient Email Addresses**: Collect the email addresses of all stakeholders who should receive the reports (e.g., project managers, World Bank TTLs, PIU staff).

---

## Step-by-Step: Monthly Report Setup

### Step 1: Navigate to Auto Email Report

1. Go to **Home > Settings > Auto Email Report**
2. Click **+ Add Auto Email Report**

### Step 2: Configure the Report

| Field             | Value                                      |
|-------------------|--------------------------------------------|
| **Report**        | Select the GRM monthly report name         |
| **Report Type**   | Script Report                              |
| **Enabled**       | Checked                                    |
| **Send If Empty** | Unchecked (avoids sending blank reports)    |

### Step 3: Set Filters

In the **Filters** section, configure the date range and any project filters:

```json
{
  "from_date": "Last Month Start",
  "to_date": "Last Month End"
}
```

If you want to restrict the report to a specific project:

```json
{
  "from_date": "Last Month Start",
  "to_date": "Last Month End",
  "project": "Your Project Name"
}
```

### Step 4: Configure Recipients

In the **Email To** field, enter recipient email addresses separated by commas:

```
project-manager@example.org, ttl@worldbank.org, piu-head@example.org
```

### Step 5: Set Frequency

| Field          | Value          |
|----------------|----------------|
| **Frequency**  | Monthly        |
| **Day of Week**| (not applicable for monthly) |

The report will be sent on the first day of each month, covering the previous month's data.

### Step 6: Configure Format and Attachments

| Field                | Value                                           |
|----------------------|-------------------------------------------------|
| **Format**           | HTML (for inline viewing) or PDF                |
| **Include Attachment**| Checked (sends PDF attachment for archiving)   |
| **Description**      | Monthly GRM Transparency Report - [Project Name]|

### Step 7: Save and Enable

1. Click **Save**
2. Ensure the **Enabled** checkbox is checked
3. The report will be sent automatically on the configured schedule

---

## Step-by-Step: Quarterly Report Setup

Follow the same steps as the monthly setup with these differences:

### Filters

```json
{
  "from_date": "Last Quarter Start",
  "to_date": "Last Quarter End"
}
```

### Frequency

| Field          | Value          |
|----------------|----------------|
| **Frequency**  | Quarterly      |

The report will be sent at the beginning of each quarter (January, April, July, October), covering the previous quarter.

### Subject Line

Use a descriptive subject so recipients can easily identify the report:

```
GRM Quarterly Summary Report - [Project Name] - Q{quarter} {year}
```

---

## Per-Project Configuration

If you manage multiple projects, create a separate Auto Email Report for each project:

1. **Duplicate** an existing Auto Email Report configuration
2. Update the **Filters** to specify the target project:
   ```json
   {
     "from_date": "Last Month Start",
     "to_date": "Last Month End",
     "project": "Water Supply Improvement Project"
   }
   ```
3. Update the **Email To** field with that project's stakeholders
4. Update the **Description** to reflect the project name
5. Save and enable

### Naming Convention

Use a clear naming pattern for your Auto Email Reports:

- `GRM Monthly - [Project Name]`
- `GRM Quarterly - [Project Name]`

This makes it easy to manage multiple configurations from the list view.

---

## Testing Checklist

Before relying on automated delivery, verify each configuration:

- [ ] **Manual Send**: Click "Send Now" on the Auto Email Report to trigger an immediate send
- [ ] **Recipient Delivery**: Confirm all recipients received the email
- [ ] **Data Accuracy**: Verify the report data matches expectations for the configured date range
- [ ] **PDF Attachment**: If enabled, confirm the PDF attachment opens correctly and is readable
- [ ] **Empty Report Handling**: If "Send If Empty" is unchecked, verify that no email is sent when there is no data
- [ ] **Filter Accuracy**: Confirm that project filters correctly limit the data to the intended project
- [ ] **Spam/Junk Folder**: Ask recipients to check spam folders and whitelist the sender address

---

## Troubleshooting

### Emails Not Sending

1. **Check Email Queue**: Go to **Home > Settings > Email Queue** and look for errors
2. **Verify Email Account**: Ensure the default outgoing email account is enabled and credentials are correct
3. **Check Scheduler**: Run `bench doctor` from the command line to confirm the scheduler is running
4. **Check Error Log**: Go to **Home > Settings > Error Log** for any report generation errors
5. **Test SMTP**: Send a test email from the email account configuration page

### Wrong Data in Reports

1. **Verify Filters**: Open the Auto Email Report and check that the date filters are correct
2. **Test Manually**: Run the report manually from the report page with the same filters to compare output
3. **Check Permissions**: The report runs as the System Manager user; ensure data access is not restricted
4. **Date Range Issues**: If using custom date expressions, verify they resolve to the expected dates

### Attachments Too Large

If PDF attachments exceed email size limits:

1. **Reduce Data Range**: Add more specific filters to limit the data volume
2. **Simplify Report**: Remove unnecessary columns from the report configuration
3. **Split by Project**: Instead of one large "All Projects" report, create separate per-project reports
4. **Increase Email Limit**: Check your SMTP provider's attachment size limit and adjust if possible
5. **Use Report Archive**: Upload large reports to the public archive instead and share the link

### Report Shows No Data

1. **Date Range**: Verify the from/to date filters match a period that has grievance data
2. **Project Filter**: Ensure the project name in filters exactly matches the project name in the system
3. **Status Filter**: If filtering by status, confirm grievances exist with that status in the date range

---

## Example Configurations

### Example 1: Monthly Report for All Projects

```
Report:        GRM Monthly Summary Report
Frequency:     Monthly
Filters:       {"from_date": "Last Month Start", "to_date": "Last Month End"}
Email To:      grm-admin@example.org, director@example.org
Format:        PDF
Description:   Monthly GRM Summary - All Projects
```

### Example 2: Quarterly Report for a Specific Project

```
Report:        GRM Quarterly Summary Report
Frequency:     Quarterly
Filters:       {"from_date": "Last Quarter Start", "to_date": "Last Quarter End", "project": "Rural Roads Project"}
Email To:      pm-roads@example.org, ttl-roads@worldbank.org
Format:        PDF
Description:   Quarterly GRM Summary - Rural Roads Project
```

### Example 3: Weekly Internal Summary

```
Report:        GRM Monthly Summary Report
Frequency:     Weekly
Filters:       {"from_date": "Last Week Start", "to_date": "Last Week End"}
Email To:      grm-team@example.org
Format:        HTML
Description:   Weekly GRM Internal Summary
```

---

## Additional Notes

- Auto Email Reports run via the Frappe background scheduler. If the scheduler is paused or the site is in maintenance mode, reports will not be sent.
- Reports are generated using the permissions of the user who created the Auto Email Report. Use a System Manager account to ensure full data access.
- For compliance with World Bank GRM requirements, ensure monthly and quarterly reports are configured and verified for each active project.
