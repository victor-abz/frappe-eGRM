"""
Public Reports API
Provides list of publicly available GRM reports (allow_guest=True)
"""

import os
import frappe


@frappe.whitelist(allow_guest=True)
def get_public_reports():
    """
    Return a list of publicly available GRM report PDFs.

    Scans the site's ``public/files/grm_reports/`` directory for PDF
    files and parses metadata from filenames in the format:
    ``DATE_PROJECT_TYPE.pdf``.

    Returns:
        list[dict]: Each entry has keys *filename*, *url*, *date*,
                    *project*, *type*.
    """
    reports = []
    site_path = frappe.get_site_path()
    reports_path = os.path.join(site_path, "public", "files", "grm_reports")

    if not os.path.exists(reports_path):
        return reports

    for root, _dirs, files in os.walk(reports_path):
        for file in files:
            if file.endswith(".pdf"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(
                    file_path, os.path.join(site_path, "public")
                )
                parts = file.replace(".pdf", "").split("_")
                reports.append(
                    {
                        "filename": file,
                        "url": f"/files/{rel_path}",
                        "date": parts[0] if len(parts) > 0 else "Unknown",
                        "project": parts[1] if len(parts) > 1 else "All Projects",
                        "type": parts[2] if len(parts) > 2 else "Report",
                    }
                )

    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports
