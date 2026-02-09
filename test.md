Phase 1: Public Transparency

  1. Public Homepage
  - Visit http://egrm.local/grm-public
  - Verify hero section, 3 action cards (Dashboard, Track, Submit), active projects list, and 6-step process overview

  2. Public Dashboard
  - Visit http://egrm.local/grm-public/dashboard
  - Verify 4 metric cards (Total, Open, Resolved, Pending)
  - Test project filter dropdown and date range filter (7d, 30d, 90d, 1y)
  - Verify status, category, and region breakdown tables

  3. Complaint Tracking
  - Visit http://egrm.local/grm-public/track-complaint
  - Get a valid tracking code:
  bench --site egrm.local console
  >>> frappe.db.get_value("GRM Issue", {"docstatus": 1}, "tracking_code")
  - Enter valid tracking code - verify status, category, dates shown (no PII)
  - Enter invalid code (e.g. FAKE-123) - verify error message

  4. Submit Grievance Placeholder
  - Visit http://egrm.local/grm-public/submit-grievance
  - Verify placeholder page with alternative submission methods

  5. Public Reports Archive
  - Visit http://egrm.local/grm-public/reports
  - Verify empty state message (no reports uploaded yet)
  - To test with data: create {site_path}/public/files/grm_reports/ and add a PDF named 2026-01_ProjectName_Monthly.pdf, then reload

  6. Public Metrics API (direct)
  bench --site egrm.local console
  >>> from egrm.api.public_metrics import get_public_dashboard
  >>> get_public_dashboard()
  - Verify status: "success" with overview, breakdowns, and trend_data

  ---
  Phase 2: Automated Reporting

  7. Monthly Report
  - Go to http://egrm.local/app/query-report/GRM Public Monthly Report
  - Verify filters: Project, From Date, To Date (defaults to last month)
  - Verify columns: Category, Total Received, Resolved, Pending, Appealed, Avg Resolution Days
  - Verify bar chart (Received vs Resolved) and summary cards
  - Test with a custom date range that has data (check your issue dates)

  8. Quarterly Report
  - Go to http://egrm.local/app/query-report/GRM Public Quarterly Report
  - Verify filters default to last completed quarter
  - Verify same columns/chart/summary as monthly report
  - Test with custom date range

  ---
  Phase 3: Notifications & SLA

  9. GRM Notification Template DocType
  - Go to http://egrm.local/app/grm-notification-template
  - Create a new template:
    - Template Name: GRM Test Receipt
    - Template Type: Receipt
    - Enable SMS: check
    - SMS Message: Your complaint {{ tracking_code }} has been received.
    - Active: check
  - Save - verify no errors
  - Click "Preview" button - verify sample data dialog
  - Try saving without email or SMS configured - verify validation error

  10. GRM Project Notification Settings
  - Go to http://egrm.local/app/grm-project/{your-project}
  - Scroll to "Notification Settings" section (collapsible)
  - Verify Enable Notifications checkbox (default on)
  - Link the receipt template you just created to "Receipt Template"
  - Save - verify no errors
  - Uncheck Enable Notifications - verify template fields hide
  - Try linking a template from a different project - verify validation error

  11. SLA Configuration on Admin Level Types
  - Go to http://egrm.local/app/grm-administrative-level-type
  - Open any level (e.g. "District")
  - Verify "SLA Configuration" section with:
    - Acknowledgment Days: 7
    - Resolution Days: 30
    - Reminder Before (Days): 2
    - Auto-Escalate on SLA Breach: checked
  - Try setting Acknowledgment Days > Resolution Days - save - verify validation error
  - Try setting Reminder Before Days > Resolution Days - verify validation error

  12. SLA Initialization on New Issue
  - Create and submit a new GRM Issue (ensure it has a valid administrative region)
  - After submission, scroll to "SLA Tracking" section
  - Verify:
    - SLA Acknowledgment Days and SLA Resolution Days are populated (from admin level config)
    - SLA Acknowledgment Due and SLA Resolution Due dates are set
    - SLA Acknowledgment Status shows "On Time"
    - SLA Resolution Status shows "On Time"
    - SLA Days Remaining is calculated

  13. SLA Status Color Coding
  - On the GRM Issue form, verify SLA status fields are color-coded:
    - Green = "On Time"
    - Orange = "Nearing Due"
    - Red = "Breached"

  14. Manual Escalation
  - Open a submitted GRM Issue (not Resolved/Closed)
  - Click Actions > Escalate to Higher Level
  - Enter a reason in the dialog, click Escalate
  - Verify:
    - Escalation Count increments
    - Last Escalated Date is set
    - SLA Escalation Reason is populated
    - Administrative region changed to parent (if one exists)

  15. Resend Notification
  - Open a submitted GRM Issue
  - Click Actions > Resend Notification
  - Select a notification type (e.g. "receipt")
  - Verify no error (actual delivery depends on email/SMS config)

  16. Resolution Agreement Fields
  - Open a resolved/closed GRM Issue
  - Scroll to "Resolution Agreement" section
  - Verify fields appear: Attach file, Date, Parties, Notes
  - Upload a test agreement file and save

  17. SLA Monitor Scheduler
  - Run manually:
  bench --site egrm.local execute egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla
  - Check the log:
  bench --site egrm.local console
  >>> frappe.get_all("Error Log", filters={"method": ["like", "%sla%"]}, fields=["name", "method", "error"], limit=5)
  - Verify no errors in the Error Log

  18. SLA Dashboard API
  bench --site egrm.local execute egrm.egrm.utils.sla_manager.get_sla_dashboard_data
  - Verify output shows total_active_issues, acknowledgment/resolution counters, and escalation stats

  ---
  Quick Smoke Test Sequence

  If you want a fast end-to-end check, run these in order:

  # 1. Verify migration applied cleanly
  bench --site egrm.local migrate

  # 2. Test APIs
  bench --site egrm.local execute egrm.api.public_metrics.get_public_dashboard
  bench --site egrm.local execute egrm.api.public_tracking.track_complaint --kwargs '{"tracking_code": "INVALID"}'
  bench --site egrm.local execute egrm.egrm.utils.sla_manager.get_sla_dashboard_data

  # 3. Test reports
  bench --site egrm.local execute egrm.egrm.report.grm_public_monthly_report.grm_public_monthly_report.execute
  bench --site egrm.local execute egrm.egrm.report.grm_public_quarterly_report.grm_public_quarterly_report.execute

  # 4. Test scheduler
  bench --site egrm.local execute egrm.egrm.scheduled_jobs.sla_monitor.monitor_sla
