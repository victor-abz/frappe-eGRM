"""
GRM Public Reports Archive
Lists publicly available GRM reports
"""

import frappe
import os


def get_context(context):
    context.no_cache = 1
    reports = get_public_reports()
    context.reports = reports
    context.site_url = frappe.utils.get_url()


def get_public_reports():
    reports = []
    site_path = frappe.get_site_path()
    reports_path = os.path.join(site_path, "public", "files", "grm_reports")

    if not os.path.exists(reports_path):
        os.makedirs(reports_path)
        return reports

    for root, dirs, files in os.walk(reports_path):
        for file in files:
            if file.endswith('.pdf'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, os.path.join(site_path, "public"))
                parts = file.replace('.pdf', '').split('_')
                reports.append({
                    "filename": file,
                    "url": f"/files/{rel_path}",
                    "date": parts[0] if len(parts) > 0 else "Unknown",
                    "project": parts[1] if len(parts) > 1 else "All Projects",
                    "type": parts[2] if len(parts) > 2 else "Report"
                })

    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports
