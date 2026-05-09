"""Top-level orchestrator for the AQE-generated full suite.

Runs every sub-suite in dependency order and aggregates their per-suite
JSON results into one REPORT.json.

Order matters:
  1.  ONBOARDING       — must run first; provisions wizard_state.json
  2.  ARCH-CONTRACT    — runs early (right after onboarding) so a fresh
                          site is verified against the per-project
                          architecture plan before any side-effects pile up
  3.  MULTI-PROJECT    — depends on (1) for the 3-project set
  4.  MOBILE-DUTY      — depends on (1) for catalog lookups
  5.  PUBLIC-CITIZEN   — depends on (1) for at least one project
  6.  ISSUE-LIFECYCLE  — depends on (1) and seeds its own issue
  7.  SECURITY         — depends on (1)
  8.  EDGE-CASES       — depends on (1)
  9.  API-CONTRACT     — depends on (1)
  10. PERFORMANCE      — bulk-seeds extra regions for the
                          location-cascade <100ms test on RW-WB
  11. UI-SCREENSHOTS   — captures the populated UI for the existing
                          three projects + per-wizard-step shots
  12. ACTOR-EVIDENCE   — one duty-relevant PNG per canonical actor,
                          each captured under a fresh per-actor session
                          (depends on UI-SCREENSHOTS for seeded data)
  13. BULK-IMPORT      — LAST; UI-ONLY (XD-specced download/upload).
                          Bench CLI commands are out of scope. Runs
                          against a dedicated PERF-IMPORT project so
                          its volume does not pollute the other suites.

Usage:
    python run_full_suite.py            # all sub-suites
    python run_full_suite.py SECURITY   # just one (case-insensitive name)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = Path("/Users/victor/egrm/aqe-screenshots/aqe-full-suite")
ART.mkdir(parents=True, exist_ok=True)


SUITES = [
    ("ONBOARDING",      "run_onboarding_tests.py"),
    ("ARCH-CONTRACT",   "run_arch_contract_tests.py"),
    ("MULTI-PROJECT",   "run_multi_project_tests.py"),
    ("MOBILE-DUTY",     "run_mobile_duty_tests.py"),
    ("PUBLIC-CITIZEN",  "run_public_citizen_tests.py"),
    ("ISSUE-LIFECYCLE", "run_issue_lifecycle_tests.py"),
    ("SECURITY",        "run_security_tests.py"),
    ("EDGE-CASES",      "run_edge_case_tests.py"),
    ("API-CONTRACT",    "run_api_contract_tests.py"),
    ("PERFORMANCE",     "run_performance_tests.py"),
    ("UI-SCREENSHOTS",  "run_ui_screenshots.py"),
    # XD-FIDELITY runs IMMEDIATELY after UI-SCREENSHOTS so it can compare
    # the freshly captured wizard_step_NN.png + .txt sidecars against
    # each XD link in xd-links.md. Heuristic comparison (text fidelity,
    # sha1 distinctness, palette family) — no pixel diff.
    ("XD-FIDELITY",     "run_xd_fidelity_tests.py"),
    # ACTOR-EVIDENCE runs AFTER UI-SCREENSHOTS so it can rely on the
    # seeded projects + login-known-good for each canonical actor.
    ("ACTOR-EVIDENCE",  "run_actor_evidence.py"),
    # ACTOR-FLOW runs AFTER ACTOR-EVIDENCE: per-actor end-to-end
    # lifecycle. For each canonical actor, exercises every action their
    # duty(ies) permit, walking real issues through every stage to a
    # terminal state with PNG + state evidence captured per action.
    ("ACTOR-FLOW",      "run_actor_flow_tests.py"),
    # UI-GRM-USERS asserts the /app/grm-users custom page exposes a
    # search input + paginator + "Showing X–Y of Z" status, and that
    # the rendered count matches the canonical server-side total. Runs
    # AFTER UI-SCREENSHOTS so the post-fix screenshot of 07-grm-users.png
    # wins (overwrites the earlier capture).
    ("UI-GRM-USERS",    "run_ui_grm_users_tests.py"),
    # BULK-IMPORT is intentionally LAST: it tests the XD-specced UI
    # download/upload flow on a dedicated PERF-IMPORT project to keep
    # its volume out of every other suite's view. Bench CLI commands
    # are explicitly out of scope.
    ("BULK-IMPORT",     "run_bulk_import_tests.py"),
]


def run_one(name: str, script: str) -> dict:
    print(f"\n{'=' * 72}\n[RUN] {name} → {script}\n{'=' * 72}")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(HERE / script)],
        cwd=str(HERE),
        capture_output=False,
    )
    elapsed = time.time() - t0
    json_path = ART / f"{name}.json"
    detail = {}
    if json_path.exists():
        try:
            detail = json.loads(json_path.read_text())
        except Exception as e:
            detail = {"_error": f"could not parse {json_path}: {e}"}
    return {
        "suite": name,
        "exit_code": proc.returncode,
        "elapsed_s": round(elapsed, 2),
        "passed": detail.get("passed", 0),
        "failed": detail.get("failed", 0),
        "total": detail.get("total", 0),
        "results": detail.get("results", []),
    }


def main() -> int:
    only = sys.argv[1].upper() if len(sys.argv) > 1 else None
    suites = [s for s in SUITES if (only is None or s[0].upper() == only)]
    if not suites:
        print(f"No suite matches '{only}'. Available: "
              + ", ".join(s[0] for s in SUITES))
        return 2

    overall_t0 = time.time()
    aggregated: list[dict] = []
    for name, script in suites:
        aggregated.append(run_one(name, script))

    total_passed = sum(r["passed"] for r in aggregated)
    total_failed = sum(r["failed"] for r in aggregated)
    total = sum(r["total"] for r in aggregated)
    total_elapsed = round(time.time() - overall_t0, 2)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "site": "http://egrm.local:8000",
        "elapsed_s": total_elapsed,
        "totals": {
            "passed": total_passed,
            "failed": total_failed,
            "total": total,
        },
        "suites": aggregated,
    }
    out = ART / "REPORT.json"
    out.write_text(json.dumps(report, indent=2, default=str))

    # ---- console summary ----------------------------------------------
    print("\n" + "=" * 72)
    print(f"AQE FULL SUITE — {total_passed}/{total} passed, "
          f"{total_failed} failed in {total_elapsed:.1f}s")
    print("=" * 72)
    for r in aggregated:
        status = "PASS" if r["failed"] == 0 and r["exit_code"] == 0 else "FAIL"
        print(f"  [{status}] {r['suite']:<18} "
              f"{r['passed']:>3}/{r['total']:<3}  "
              f"({r['elapsed_s']:>5.1f}s)")
    print(f"\nFull report -> {out}")

    # ---- render REPORT.html (v2) --------------------------------------
    # Always re-render the human-visualisable HTML report from the
    # freshly written REPORT.json, even on partial runs (`only`). The
    # script is fully resilient against a missing report.
    try:
        subprocess.run(
            [sys.executable, str(HERE / "make_html_report.py")],
            cwd=str(HERE),
            check=False,
        )
    except Exception as e:
        print(f"[run_full_suite] make_html_report failed: {e}")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
