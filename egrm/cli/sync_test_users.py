"""DEPRECATED — DO NOT USE.

Test users are now created at runtime by the AQE ONBOARDING suite via
the GRM Project Wizard Step 9 UI. The function bodies in this module
are retained transiently but every CLI entry point hard-stops with a
deprecation message; importers that still reference these symbols
will fail loudly the moment they invoke them.

Spec: docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md
"""
import sys

import frappe
from frappe.utils.password import update_password


_DEPRECATION_MSG = (
    "ERROR: sync_test_users is DEPRECATED.\n"
    "Test users are now created via the GRM Project Wizard Step 9 UI flow.\n"
    "Run the AQE ONBOARDING suite instead "
    "(docs/superpowers/plans/aqe-generated/run_onboarding_tests.py).\n"
    "See: docs/superpowers/specs/2026-05-09-no-seeding-wizard-driven-tests-design.md\n"
)


def _hard_stop() -> None:
    """Hard-stop every CLI entry point. Prints the deprecation banner to
    stderr and exits non-zero so `bench execute` returns a failure."""
    print(_DEPRECATION_MSG, file=sys.stderr)
    sys.exit(2)


USERS = [
    # Top of hierarchy — runs the wizard, oversees everything
    {
        "email": "project-admin@egrm.test",
        "first_name": "Pria",
        "last_name": "Admin",
        "roles": ["GRM Platform Administrator", "GRM Supervise"],
        "password": "ProjectAdmin@2026",
        "duty": "Platform / Supervise",
    },
    # Intake duty — raises issues from the field (kept as `field-officer` for continuity)
    {
        "email": "field-officer@egrm.test",
        "first_name": "Frida",
        "last_name": "Officer",
        "roles": ["GRM Intake"],
        "password": "FieldOfficer@2026",
        "duty": "Intake (Uptake / Data Entry)",
    },
    # Triage duties — reviews issue classification then assigns to resolvers
    {
        "email": "triage-officer@egrm.test",
        "first_name": "Tomo",
        "last_name": "Triage",
        "roles": ["GRM Review", "GRM Assignment"],
        "password": "TriageOfficer@2026",
        "duty": "Review + Assignment",
    },
    # Resolution + Feedback — works the issue and closes the loop with the citizen
    {
        "email": "resolver@egrm.test",
        "first_name": "Reno",
        "last_name": "Resolver",
        "roles": ["GRM Investigate & Resolve", "GRM Feedback"],
        "password": "Resolver@2026",
        "duty": "Investigate & Resolve + Feedback",
    },
    # Mobile field worker — full intake + resolve duty (used by AQE
    # mobile-duty / API-contract / security / arch-contract suites as
    # the canonical "GRM officer" actor). Distinct from `field-officer`
    # which is intake-only; this user covers the end-to-end mobile
    # pull/push surface.
    {
        "email": "grm-officer@egrm.test",
        "first_name": "Geno",
        "last_name": "Officer",
        "roles": [
            "GRM Intake",
            "GRM Investigate & Resolve",
            "GRM Feedback",
        ],
        "password": "GrmOfficer@2026",
        "duty": "Intake + Investigate & Resolve + Feedback (mobile)",
    },
]


def _sync_one(u):
    if frappe.db.exists("User", u["email"]):
        user = frappe.get_doc("User", u["email"])
        print(f"EXISTS  {u['email']}")
    else:
        user = frappe.new_doc("User")
        user.email = u["email"]
        user.first_name = u["first_name"]
        user.last_name = u["last_name"]
        user.send_welcome_email = 0
        user.enabled = 1
        user.user_type = "System User"
        user.new_password = u["password"]
        user.insert(ignore_permissions=True)
        print(f"CREATED {u['email']}")

    keep = {"All", "Guest"}
    target_set = set(u["roles"])
    existing = {r.role for r in user.get("roles", [])}
    for r in list(user.get("roles", [])):
        if r.role not in target_set and r.role not in keep:
            user.remove(r)
    for r in u["roles"]:
        if r not in existing:
            user.append("roles", {"role": r})
    user.save(ignore_permissions=True)
    update_password(u["email"], u["password"])

    # Platform admins MUST be unscoped — they bootstrap NEW projects via the
    # wizard. A stale `User Permission` row pinning them to a single project
    # would block /api/resource/GRM Project POSTs with 403 PermissionError.
    # The eGRM duty-driven access model only scopes non-platform users via
    # `User Permission` (via `egrm.utils.user_permissions.sync_assignment`).
    if "GRM Platform Administrator" in u["roles"]:
        ups = frappe.get_all(
            "User Permission",
            filters={"user": u["email"], "allow": "GRM Project"},
            pluck="name",
        )
        for up_name in ups:
            try:
                frappe.delete_doc(
                    "User Permission", up_name,
                    ignore_permissions=True, force=True,
                )
                print(f"  cleared stale User Permission: {up_name}")
            except Exception as exc:
                print(f"  could not clear UP {up_name}: {exc}")

    rs = sorted([x.role for x in user.get("roles", [])])
    print(f"  duty -> {u['duty']}")
    print(f"  roles -> {rs}")


def sync():
    _hard_stop()
    for u in USERS:
        _sync_one(u)
    frappe.db.commit()
    print("--- DONE ---")


def sync_subset(emails):
    """Provision only the users whose email is in `emails`. Use to set up
    Scenario-A users (pre-existing at platform level) while leaving
    Scenario-B users absent so the assignment UI must create them inline.

    Run: bench --site egrm.local execute \
      "frappe.get_attr('egrm.cli.sync_test_users.sync_subset')(['project-admin@egrm.test','triage-officer@egrm.test'])"
    """
    _hard_stop()
    wanted = {e.strip().lower() for e in emails}
    for u in USERS:
        if u["email"].lower() in wanted:
            _sync_one(u)
    frappe.db.commit()
    print(f"--- DONE subset: {sorted(wanted)} ---")


def purge_users(emails):
    """Hard-delete the named User records (used by E2E reset to ensure
    Scenario-B emails are unknown to Frappe at the start of a run).

    Run: bench --site egrm.local execute \
      "frappe.get_attr('egrm.cli.sync_test_users.purge_users')(['field-officer@egrm.test','resolver@egrm.test'])"
    """
    _hard_stop()
    for email in emails:
        if frappe.db.exists("User", email):
            try:
                frappe.delete_doc("User", email, ignore_permissions=True, force=True)
                print(f"DELETED {email}")
            except Exception as e:
                print(f"  failed to delete {email}: {e}")
        else:
            print(f"ABSENT  {email}")
    frappe.db.commit()
    print("--- DONE purge_users ---")
