"""Shared helpers for every AQE-generated test sub-suite.

Standard pattern for sub-suites:

    from _common import (
        SITE, ART, login, post, get, ok, fail, summary,
        ACTOR_GRM_OFFICER, ACTOR_PROJECT_ADMIN,
    )

Each sub-suite calls `summary(name, results)` at the end so
`run_full_suite.py` can aggregate.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

SITE = "http://egrm.local:8000"

# Shared output directory. Anything dumped here is collected by the
# top-level orchestrator into REPORT.json.
ART = Path("/Users/victor/egrm/aqe-screenshots/aqe-full-suite")
ART.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- ACTORS

# (email, password)
ACTOR_PROJECT_ADMIN  = ("project-admin@egrm.test",  "ProjectAdmin@2026")
ACTOR_GRM_OFFICER    = ("grm-officer@egrm.test",    "GrmOfficer@2026")
ACTOR_TRIAGE_OFFICER = ("triage-officer@egrm.test", "TriageOfficer@2026")
ACTOR_RESOLVER       = ("resolver@egrm.test",       "Resolver@2026")
ACTOR_FIELD_OFFICER  = ("field-officer@egrm.test",  "FieldOfficer@2026")
ACTOR_GRM_DEPT       = ("grm-dept@egrm.test",       "GrmDept@2026")

# Project codes provisioned by `run_onboarding_tests.py` (must run first).
# Downstream suites should resolve concrete record names via `load_wizard_state()`
# and the helpers below — no hardcoded record IDs.
PROJECT_RW   = "RW-WB"     # Rwanda 6-level
PROJECT_KE   = "KE-EAC"    # Kenya 5-level
PROJECT_HOSP = "STJ-HOSP"  # Hospital 4-level (non-geographic)
ALL_PROJECT_CODES = (PROJECT_RW, PROJECT_KE, PROJECT_HOSP)


def load_wizard_state() -> list[dict]:
    """Return the per-project records emitted by ONBOARDING.

    Each entry has shape:
        {"code": str, "project_name": str,
         "levels": {level_name: doc_name, ...},
         "regions": {region_name: doc_name, ...}}
    """
    p = ART / "wizard_state.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def state_for(code: str) -> dict | None:
    for st in load_wizard_state():
        if st.get("code") == code:
            return st
    return None


# ----------------------------------------------------------------- assertion helpers

@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""

@dataclass
class SuiteRun:
    name: str
    results: list[Result] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def ok(self, name: str, cond: bool, detail: str = "") -> bool:
        # Always retain `detail` (even on success) so the HTML report and
        # downstream learning loops can surface inputs / observed values.
        # PERFORMANCE in particular needs every assertion's detail to be
        # populated for `make_html_report.render_perf_table` to render.
        r = Result(name, bool(cond), detail)
        self.results.append(r)
        if cond:
            print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
        else:
            print(f"  ✗ {name} — {detail}")
        return bool(cond)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


def ok(name: str, cond: bool, detail: str = "") -> None:
    """Backwards-compat assertion (raises). Used inside small helpers."""
    if not cond:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"  ✓ {name}")


def fail(name: str, detail: str) -> None:
    print(f"  ✗ {name} — {detail}")


# ----------------------------------------------------------------- HTTP helpers

def _h() -> dict[str, str]:
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }


def login(s: requests.Session, email: str, pwd: str) -> tuple[int, dict]:
    r = s.post(
        f"{SITE}/api/method/login",
        data={"usr": email, "pwd": pwd},
        headers=_h(),
        timeout=30,
    )
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:200]}
    return r.status_code, body


def _form_encode_safe(data: dict | None) -> dict | None:
    """Make `data=` payloads safe for Frappe's form-encoded REST endpoints.

    Python `requests` flattens list/dict values when form-encoding — a
    payload like ``{"grm_project_link": [{"project": "RW-WB"}]}`` ends up
    on the wire as ``grm_project_link=project`` (only the inner dict's
    keys, the values are silently dropped). This corrupts every child-table
    insert.

    Frappe accepts JSON-encoded scalar form values and auto-decodes them
    via ``frappe.parse_json`` before they reach the document layer, so the
    safe transformation is to ``json.dumps`` any ``list`` or ``dict``
    value the caller passes in. Scalars are left untouched so we don't
    spuriously double-quote ints / bools.
    """
    if data is None:
        return None
    out: dict = {}
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            out[k] = json.dumps(v, default=str)
        else:
            out[k] = v
    return out


def post(s: requests.Session, path: str,
         json_body: dict | None = None,
         data: dict | None = None,
         headers: dict | None = None,
         files: dict | None = None,
         timeout: int = 60) -> tuple[int, dict]:
    h = _h()
    if headers:
        h.update(headers)
    if files:
        # multipart/form-data — let requests pick the boundary; do NOT
        # send our pre-built Content-Type header otherwise it overrides
        # the multipart boundary.
        h.pop("Content-Type", None)
        r = s.post(
            f"{SITE}{path}",
            data=_form_encode_safe(data), files=files,
            headers=h, timeout=timeout,
        )
    else:
        r = s.post(
            f"{SITE}{path}",
            json=json_body, data=_form_encode_safe(data),
            headers=h, timeout=timeout,
        )
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:300]}
    return r.status_code, body


def get(s: requests.Session, path: str,
        params: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
    r = s.get(f"{SITE}{path}", params=params, headers=_h(), timeout=timeout)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:300]}
    return r.status_code, body


def logout(s: requests.Session) -> None:
    try:
        s.post(f"{SITE}/api/method/logout", timeout=10)
    except Exception:
        pass


# ----------------------------------------------------------------- summary

def summary(suite: SuiteRun) -> int:
    elapsed = time.time() - suite.started_at
    out = {
        "suite": suite.name,
        "passed": suite.passed,
        "failed": suite.failed,
        "total": suite.total,
        "elapsed_s": round(elapsed, 2),
        "results": [
            {"name": r.name, "passed": r.passed, "detail": r.detail}
            for r in suite.results
        ],
    }
    (ART / f"{suite.name}.json").write_text(json.dumps(out, indent=2))
    print()
    if suite.failed == 0:
        print(f"[{suite.name}] PASSED — {suite.passed}/{suite.total} in {elapsed:.1f}s")
        return 0
    print(f"[{suite.name}] FAILED — {suite.passed}/{suite.total} (failures: "
          + ", ".join(r.name for r in suite.results if not r.passed)
          + f") in {elapsed:.1f}s")
    return 1


def run(main_fn) -> int:
    """Use as `if __name__ == '__main__': sys.exit(run(main))`."""
    try:
        return int(main_fn() or 0)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"FATAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


def msg(body: Any) -> Any:
    """Frappe wraps under `message`; unwrap if present."""
    if isinstance(body, dict) and "message" in body:
        return body["message"]
    return body


# ============================================================== PERFORMANCE BUDGETS
#
# Single source of truth for endpoint perf goals. Every PERFORMANCE-suite
# assertion reads from this table. Change the budget here once, all
# tests pick it up.
#
# Numbers are dev-machine targets (Mac M-series, single Frappe worker
# under default site config). They are intentionally aggressive enough
# to FORCE caching, frappe.qb / direct SQL, and N-times-N query
# elimination on hot paths. If a budget is exceeded the test fails;
# the developer should profile and either (a) optimise the query, or
# (b) add caching, or (c) request a budget revision in this file.
#
# Latency keys:
#   cold_ms       — first request after a cache flush (single sample)
#   p50_warm_ms   — median of warm samples
#   p95_warm_ms   — 95th percentile of warm samples
#   conc_p50_ms   — median under N concurrent callers (DB-stress signal)
#   throughput_qps — minimum sustained QPS for the concurrency test
#
# An entry of `None` means "unbudgeted (currently)" — the test still
# records the number so we can pick a budget once we have data.

PERF_BUDGETS: dict[str, dict[str, float | None]] = {
    # -------- public-citizen READ surface (must be the snappiest) --------
    "public_submit.get_submission_config": {
        "cold_ms": 200, "p50_warm_ms": 80,  "p95_warm_ms": 150, "conc_p50_ms": 100,
    },
    "public_submit.get_submission_options": {
        "cold_ms": 300, "p50_warm_ms": 150, "p95_warm_ms": 250, "conc_p50_ms": 200,
    },
    "public_submit.get_region_children": {
        # The headline target the user asked for: location lookups
        # ALWAYS under 100 ms warm, even with thousands of regions.
        "cold_ms": 200, "p50_warm_ms": 100, "p95_warm_ms": 150, "conc_p50_ms": 150,
    },
    "public_tracking.track_complaint": {
        "cold_ms": 200, "p50_warm_ms": 100, "p95_warm_ms": 200, "conc_p50_ms": 150,
    },
    "public_metrics.get_public_dashboard": {
        "cold_ms": 1500, "p50_warm_ms": 600, "p95_warm_ms": 1000, "conc_p50_ms": 800,
    },
    "public_reports.get_public_reports": {
        "cold_ms": 800, "p50_warm_ms": 400, "p95_warm_ms": 700, "conc_p50_ms": 600,
    },
    "public_translations.get_translations": {
        "cold_ms": 200, "p50_warm_ms": 50, "p95_warm_ms": 100, "conc_p50_ms": 80,
    },
    "portal_config.get_portal_config": {
        "cold_ms": 200, "p50_warm_ms": 80, "p95_warm_ms": 150, "conc_p50_ms": 100,
    },
    # -------- public-citizen WRITE surface --------------------------------
    "public_submit.submit_grievance": {
        "cold_ms": 800, "p50_warm_ms": 300, "p95_warm_ms": 500, "conc_p50_ms": 400,
    },
    # -------- staff / mobile authenticated surface ------------------------
    "lookup.user_context": {
        "cold_ms": 400, "p50_warm_ms": 150, "p95_warm_ms": 300, "conc_p50_ms": 200,
    },
    "frappe.boot.get_bootinfo": {
        "cold_ms": 1500, "p50_warm_ms": 600, "p95_warm_ms": 1000, "conc_p50_ms": None,
    },
    "sync.pull_changes_cold": {
        "cold_ms": 2500, "p50_warm_ms": None, "p95_warm_ms": None, "conc_p50_ms": None,
    },
    "sync.pull_changes_warm": {
        "cold_ms": None, "p50_warm_ms": 800, "p95_warm_ms": 1500, "conc_p50_ms": 1000,
    },
    "sync.push_changes": {
        "cold_ms": 800, "p50_warm_ms": 400, "p95_warm_ms": 800, "conc_p50_ms": 600,
    },
    "issue.resolve": {
        "cold_ms": 800, "p50_warm_ms": 300, "p95_warm_ms": 500, "conc_p50_ms": 400,
    },
}


# ============================================================== BULK SCALE TARGETS
#
# Minimum scale the suite must seed/assert against. If your dev box
# can't reach these numbers in a reasonable wall clock, lower them
# locally — but do NOT lower them in CI.
#
# 2026-05-09: bumped from {500, 100, 50, 50} → {5000, 1000, 200, 100}
# so the perf suite stresses real volumes:
#   * region_cascade_under_100ms now runs against >5000 siblings
#   * bulk-submit p50/p95 are taken across 1000 sequential calls
#   * concurrent_submit / concurrent_readers hit 200 / 100 callers
# Wall time impact: PERFORMANCE goes from ~22s → ~3 minutes on M-series.
# The CLI import path stays at 100 (admin-regions CLI is a smoke test —
# scaling it up would just slow the suite without exercising the API).
BULK_SCALE = {
    "regions_total":          5000,  # bulk-seeded under ONE leaf cell
    "regions_total_via_cli":   100,  # admin-regions CLI smoke import
    "issues_sequential":      1000,
    "issues_concurrent":       200,
    "concurrent_readers":      100,
}


# ============================================================== CONCURRENCY HELPER

def measure_latencies(fn, n: int = 10) -> list[float]:
    """Call fn() n times sequentially, return per-call latencies in ms."""
    out: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def measure_concurrent(fn, n: int = 50, workers: int = 10) -> tuple[list[float], int]:
    """Run fn() n times across `workers` threads.

    Returns (latencies_ms, error_count). The pool is intentionally
    sized to mimic a small fleet of real clients hammering the box —
    this is the "DB collapse" signal: if the DB is misconfigured or
    a hot query is unindexed, latencies tail out and/or errors spike.
    """
    from concurrent.futures import ThreadPoolExecutor
    latencies: list[float] = []
    errors = 0

    def _one() -> tuple[float, bool]:
        t0 = time.perf_counter()
        try:
            fn()
            err = False
        except Exception:
            err = True
        return (time.perf_counter() - t0) * 1000.0, err

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for ms, err in ex.map(lambda _i: _one(), range(n)):
            latencies.append(ms)
            if err:
                errors += 1
    return latencies, errors


def stats(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "n": 0}
    s = sorted(latencies)
    n = len(s)
    return {
        "n": n,
        "min": s[0],
        "p50": s[int(0.50 * (n - 1))],
        "p95": s[int(0.95 * (n - 1))],
        "p99": s[int(0.99 * (n - 1))],
        "max": s[-1],
    }


def _budget_field_to_pct(budget_field: str) -> str | None:
    """Map a PERF_BUDGETS key like 'p95_warm_ms' to a percentile label."""
    if "p50" in budget_field:
        return "p50"
    if "p95" in budget_field:
        return "p95"
    if "p99" in budget_field:
        return "p99"
    if budget_field == "cold_ms":
        return "cold"
    return None


def perf_detail(observed: float | int, *, unit: str = "ms",
                percentile: str | None = None,
                n: int | None = None,
                budget: float | None = None,
                budget_field: str | None = None,
                inputs: dict | None = None,
                extra: dict | None = None) -> str:
    """Build a structured, regex-friendly + JSON-tail detail string.

    Format:
        observed=<v><unit> [percentile=<p>] [n=<n>]
        ([<v><unit>][ budget <field>=<b><unit>])
        [inputs=(k1=v1,k2=v2,...)] | json={...}

    The legacy `( <v>ms ... budget=<b>ms)` substring is preserved so
    `make_html_report.render_perf_table` keeps regex-matching it.
    """
    inputs = inputs or {}
    payload: dict[str, Any] = {
        "observed": round(float(observed), 3),
        "unit": unit,
    }
    if percentile is not None:
        payload["percentile"] = percentile
    if n is not None:
        payload["n"] = int(n)
    if budget is not None:
        payload["budget"] = float(budget)
    if budget_field is not None:
        payload["budget_field"] = budget_field
    if inputs:
        payload["inputs"] = inputs
    if extra:
        payload.update(extra)

    bud_str = (
        f"{budget:.0f}" if budget is not None
        else ("None" if budget_field is not None else "")
    )
    legacy_paren = (
        f"({float(observed):.1f}{unit}"
        + (f" budget {budget_field}={bud_str}{unit}" if budget_field else "")
        + ")"
    )

    parts = [f"observed={float(observed):.1f}{unit}"]
    if percentile is not None:
        parts.append(f"percentile={percentile}")
    if n is not None:
        parts.append(f"n={int(n)}")
    parts.append(legacy_paren)
    if inputs:
        kv = ",".join(f"{k}={v}" for k, v in inputs.items())
        parts.append(f"inputs=({kv})")
    parts.append(f"json={json.dumps(payload, default=str)}")
    return " ".join(parts[:-1]) + " | " + parts[-1]


def check_budget(suite, label: str, key: str, value_ms: float,
                 budget_field: str, *, n: int | None = None,
                 inputs: dict | None = None) -> bool:
    """Assert latency `value_ms` against PERF_BUDGETS[key][budget_field].

    `label` is the test ID surfaced in the report. Returns True if the
    budget is None (unbudgeted — informational only) OR if value_ms
    is under budget. Always records observed/budget/inputs in the
    detail (in both human-readable + JSON-tail format).
    """
    bud = PERF_BUDGETS.get(key, {}).get(budget_field)
    pct = _budget_field_to_pct(budget_field)
    extra = {"unbudgeted": True} if bud is None else None
    detail = perf_detail(
        value_ms,
        unit="ms",
        percentile=pct,
        n=n,
        budget=bud,
        budget_field=budget_field,
        inputs={**(inputs or {}), "endpoint": key},
        extra=extra,
    )
    if bud is None:
        return suite.ok(label, True, detail)
    return suite.ok(label, value_ms < bud, detail)
