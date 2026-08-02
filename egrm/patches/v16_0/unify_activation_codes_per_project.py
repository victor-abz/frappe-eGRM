# Copyright (c) 2026, eGRM and contributors
# For license information, please see license.txt
"""Collapse per-assignment activation state onto one state per (user, project).

Before this release ``before_insert`` minted a fresh 6-digit code for every
government-worker assignment row. Once multi-region assignments became legal a
single user could end up with one Pending row per region, each holding a
different code, while ``activation.activate_government_worker`` resolves exactly
one assignment per call. The remaining rows were unreachable, and every
project-scoped query (mobile sync, region lookup, issue filtering) requires
``activation_status = 'Activated'`` — so those users saw no projects at all.

This patch normalises existing data to match the new one-activation-per-project
behaviour:

* If any assignment in a (user, project) group is already ``Activated``, the
  group's other non-suspended rows are activated too — the user already proved
  ownership of the account for that project.
* Otherwise the group's pending rows all adopt the single code with the latest
  expiry, so whichever row the API resolves accepts the code the user holds.

Idempotent: re-running finds groups already consistent and makes no writes.
"""

import secrets

import frappe
from frappe.utils import add_to_date, get_datetime, now, now_datetime

from egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment import (
    _is_gov_worker_assignment,
)


def execute():  # type: ignore[no-untyped-def]
    rows = frappe.get_all(
        "GRM User Project Assignment",
        filters={"is_active": 1},
        fields=[
            "name",
            "user",
            "project",
            "role",
            "administrative_region",
            "department",
            "activation_status",
            "activation_code",
            "activation_expires_on",
        ],
    )

    groups: dict[tuple[str, str], list] = {}
    for row in rows:
        if not _is_gov_worker_assignment(row):
            continue
        groups.setdefault((row.user, row.project), []).append(row)

    activated_count = 0
    recoded_count = 0
    refreshed_count = 0

    for (user, project), group in groups.items():
        if len(group) < 2:
            continue

        pending = [
            r for r in group if r.activation_status not in ("Activated", "Suspended")
        ]
        if not pending:
            continue

        if any(r.activation_status == "Activated" for r in group):
            for row in pending:
                frappe.db.set_value(
                    "GRM User Project Assignment",
                    row.name,
                    {
                        "activation_status": "Activated",
                        "activated_on": frappe.utils.now(),
                        "activation_attempts": 0,
                    },
                    update_modified=False,
                )
                activated_count += 1
            continue

        # No activated row: the group converges on a single LIVE code so the
        # worker has exactly one redeemable OTP.
        coded = [r for r in pending if r.activation_code and r.activation_expires_on]
        winner_code = None
        winner_expiry = None
        if coded:
            winner = max(coded, key=lambda r: get_datetime(r.activation_expires_on))
            if get_datetime(winner.activation_expires_on) > now_datetime():
                winner_code = winner.activation_code
                winner_expiry = winner.activation_expires_on

        if winner_code is None:
            # Every code in the group has lapsed — the common case for users
            # stranded by the per-row bug, since nobody could redeem them
            # before the 48h TTL ran out. Unifying onto a dead code would
            # leave them just as stuck, so issue one fresh code and let an
            # admin resend/export it. CSPRNG + TTL mirror
            # ``GRMUserProjectAssignment.generate_activation_code``.
            winner_code = f"{secrets.randbelow(10**6):06d}"
            winner_expiry = add_to_date(now(), hours=48)
            refreshed_count += 1

        for row in pending:
            already_converged = (
                row.activation_code == winner_code
                and row.activation_status == "Pending Activation"
            )
            if already_converged:
                continue
            frappe.db.set_value(
                "GRM User Project Assignment",
                row.name,
                {
                    "activation_code": winner_code,
                    "activation_expires_on": winner_expiry,
                    # Clears any row validate() had already flipped to Expired.
                    "activation_status": "Pending Activation",
                    "activation_attempts": 0,
                },
                update_modified=False,
            )
            recoded_count += 1

    if activated_count or recoded_count:
        frappe.db.commit()

    print(
        f"unify_activation_codes_per_project: activated {activated_count} "
        f"assignment(s), unified codes on {recoded_count} assignment(s), "
        f"issued {refreshed_count} fresh code(s) for groups whose codes had lapsed"
    )
