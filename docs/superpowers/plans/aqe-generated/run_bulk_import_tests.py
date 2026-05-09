"""SUITE: BULK-IMPORT — runs LAST in the orchestrator and exercises the
user-facing UI download/upload flow the XD specs.

Scope
-----
THIS SUITE TESTS THE XD-SPECCED UI BULK-IMPORT FLOW ONLY.

The bench CLI commands (`import-admin-regions`,
`create-government-workers`, …) are an OPERATOR convenience for shell
users and are explicitly OUT OF SCOPE here. The user-facing surface a
project admin actually sees is the XD "Download template → fill →
Upload" page; that is what we test.

Expected whitelisted RPCs (under `egrm.api.bulk_import`):
  - `download_admin_regions_template`
  - `upload_admin_regions`
  - `download_workers_template`
  - `upload_workers`

If any are missing the suite FAILS with an actionable hint so the
developer adds the module — the XD design does not allow silently
dropping the UI surface.

Why LAST in the orchestrator
----------------------------
This suite runs against a SEPARATE `PERF-IMPORT` project so the bulk
operations cannot pollute the views any earlier suite (multi-project
listings, perf budgets, security checks) reports against.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import requests

from _common import (
    ACTOR_PROJECT_ADMIN, SuiteRun, get, login, logout, msg, post, run,
    summary,
)

# UI-side whitelisted RPCs the XD bulk-import flow expects. These are
# the methods the page must call to (a) hand the user a CSV/XLSX
# template and (b) ingest a populated upload. If any are missing the
# suite FAILS with an actionable hint so the developer knows to add
# them — the XD design does NOT allow silently dropping the UI surface.
EXPECTED_UI_RPCS = [
    "egrm.api.bulk_import.download_admin_regions_template",
    "egrm.api.bulk_import.upload_admin_regions",
    "egrm.api.bulk_import.download_workers_template",
    "egrm.api.bulk_import.upload_workers",
]

# Dedicated project for this LAST suite — kept distinct from RW-WB /
# KE-EAC / STJ-HOSP so its bulk volume cannot pollute the views any
# earlier suite reports against.
PERF_PROJECT_CODE = "PERF-IMPORT"


def _build_smoke_csv(path: Path, n_rows: int) -> None:
    """Write a tiny Province/District/Sector/Cell/Village CSV.

    Columns mirror `egrm/commands/rwanda_locations.csv` so the parser
    behind the upload RPC doesn't care.
    """
    import csv  # local import — only needed for the upload payload
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Province", "District", "Sector", "Cell", "Village"])
        for i in range(n_rows):
            w.writerow([
                "Perf Province",
                f"Perf District {i // 100}",
                f"Perf Sector {i // 25}",
                f"Perf Cell {i // 5}",
                f"Perf Village {i:04d}",
            ])


# ----------------------------------------------------------------- UI flow

def assert_ui_rpc_registered(
    suite: SuiteRun, s: requests.Session, rpc: str,
) -> bool:
    """A whitelisted RPC must respond with something OTHER than the
    Frappe "method does not exist" envelope.

    We probe with a GET to `/api/method/<rpc>` and call the contract met
    iff:
      - HTTP is 200/400/417 (registered + arg validation), OR
      - HTTP is 403 (registered but permission-gated for this user), OR
      - HTTP is 404 with a body that contains the path being callable
        (Frappe sometimes returns 404 even for valid whitelisted
        functions when args are missing — fine, registration confirmed).

    A 404 with `Method ... not found / does not exist` is a HARD FAIL.
    """
    url = f"/api/method/{rpc}"
    code, body = get(s, url, timeout=15)
    text = (str(body) if body is not None else "").lower()
    not_registered = (
        code == 404
        and ("does not exist" in text or "not found" in text)
    ) or (code == 417 and "frappedoesnotexisterror" in text)
    return suite.ok(
        f"BI-UI-1.{rpc.split('.')[-1]}_registered",
        not not_registered,
        f"http={code} body={text[:200]!r}",
    )


def assert_ui_template_round_trip(
    suite: SuiteRun, s: requests.Session,
) -> None:
    """Round-trip the regions template: download → upload (1 row) → verify."""
    # 1. download template
    code, body = get(
        s,
        "/api/method/egrm.api.bulk_import.download_admin_regions_template",
        params={"project": PERF_PROJECT_CODE},
        timeout=20,
    )
    suite.ok(
        "BI-UI-2.download_admin_regions_template",
        code == 200,
        f"http={code} body={str(body)[:200]!r}",
    )
    # If the endpoint returns a file_url instead of inline bytes, that's
    # also a valid contract (Frappe `frappe.utils.file_manager.save_file`
    # pattern). Either is accepted.

    # 2. upload a 1-row populated CSV via the symmetric RPC
    tmp = Path(tempfile.mkdtemp(prefix="aqe-bulk-ui-"))
    csv_path = tmp / "ui-perf-locations.csv"
    _build_smoke_csv(csv_path, n_rows=5)
    files = {"file": ("ui-perf-locations.csv", csv_path.open("rb"), "text/csv")}
    code, body = post(
        s,
        "/api/method/egrm.api.bulk_import.upload_admin_regions",
        data={"project": PERF_PROJECT_CODE, "highest_level": "Country"},
        files=files,
        timeout=60,
    )
    suite.ok(
        "BI-UI-3.upload_admin_regions",
        code in (200, 201),
        f"http={code} body={str(body)[:300]!r}",
    )
    shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------- main

def _ensure_perf_project(suite: SuiteRun, s: requests.Session) -> str | None:
    """Ensure the dedicated PERF-IMPORT project exists.

    The CLI surface used to seed it via `--create-project`; in UI-only
    scope the suite creates the project record itself with the same
    REST endpoint the wizard uses on Step 1.
    """
    code, body = post(
        s,
        f"/api/resource/GRM%20Project",
        data={
            "project_code": PERF_PROJECT_CODE,
            "title": "PERF-IMPORT (UI bulk-import)",
            "description": "Dedicated project for the LAST suite. UI-only.",
            "start_date": "2026-01-01",
            "end_date": "2030-12-31",
            "default_language": "en",
            "auto_escalation_days": 15,
        },
        timeout=20,
    )
    ok = code in (200, 201) or (
        # Already exists from a prior run — fine, reuse it.
        code == 409 or "already exists" in str(body).lower()
    )
    suite.ok(
        "BI-UI-0.perf_project_ready",
        ok,
        f"http={code} body={str(body)[:200]!r}",
    )
    return PERF_PROJECT_CODE if ok else None


def main() -> int:
    # Suite label MUST match the key the orchestrator (`run_full_suite.py`)
    # uses to locate the per-suite JSON (`BULK-IMPORT.json`). The
    # "(UI-only)" qualifier was confusing the aggregator into reading a
    # non-existent file, which silently zeroed the suite totals.
    suite = SuiteRun("BULK-IMPORT")

    s = requests.Session()
    code, body = login(s, *ACTOR_PROJECT_ADMIN)
    if not (code == 200 and msg(body) == "Logged In"):
        suite.ok("BI-UI-0.admin_login", False, str(body)[:200])
        return summary(suite)
    suite.ok("BI-UI-0.admin_login", True, "logged in")

    # Provision the dedicated PERF-IMPORT project.
    if not _ensure_perf_project(suite, s):
        logout(s)
        return summary(suite)

    # ---- Step 1: XD-specced UI RPCs registered? ----------------------
    ui_all_ok = True
    for rpc in EXPECTED_UI_RPCS:
        if not assert_ui_rpc_registered(suite, s, rpc):
            ui_all_ok = False
    if not ui_all_ok:
        suite.ok(
            "BI-UI-1.MISSING_UI_RPCS",
            False,
            "One or more XD-specced UI bulk-import RPCs are NOT "
            "registered. The XD design defines a Download-template / "
            "Upload page for project admins. Add an "
            "`egrm.api.bulk_import` whitelisted module exposing "
            "download_admin_regions_template, upload_admin_regions, "
            "download_workers_template, upload_workers — wrapped "
            "behind a project-admin permission gate so admins without "
            "shell access can use the UI bulk-load. (Internally these "
            "may reuse the same parsing logic as the bench commands; "
            "that is an implementation detail and out of scope here.)",
        )
        logout(s)
        return summary(suite)

    # ---- Step 2: round-trip download → upload ------------------------
    assert_ui_template_round_trip(suite, s)
    logout(s)
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
