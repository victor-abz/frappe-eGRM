"""DEV-ONLY: Set known passwords for gov-workers created inline during the
ACT 4 wizard assignment form (Scenario B users). Without this they cannot
log in via desk for downstream acts (Intake, Triage, Resolution).

Run: bench --site egrm.local execute egrm.cli.set_worker_passwords.run
"""

from __future__ import annotations

import frappe
from frappe.utils.password import update_password


WORKER_CREDENTIALS = [
    ("triage-officer@egrm.test", "TriageOfficer@2026"),
    ("grm-officer@egrm.test",    "GrmOfficer@2026"),
    ("grm-dept@egrm.test",       "GrmDept@2026"),
]


def run() -> None:
    for email, pwd in WORKER_CREDENTIALS:
        if not frappe.db.exists("User", email):
            print(f"MISSING {email}")
            continue
        update_password(email, pwd)
        print(f"OK      {email}  ->  {pwd}")
    frappe.db.commit()
    print("--- DONE ---")
