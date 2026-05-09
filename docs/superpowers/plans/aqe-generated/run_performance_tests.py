"""SUITE: Performance — endpoint budgets + bulk + concurrency stress.

Three orthogonal axes are exercised:

  1. Per-endpoint latency budgets (cold / p50 warm / p95 warm), pulled
     from `_common.PERF_BUDGETS`. Failing a budget should force the
     developer to add caching, switch to `frappe.qb` / direct SQL, or
     otherwise eliminate the offending hot path.

  2. Region-cascade scaling: BULK_SCALE['regions_total'] extra leaf
     regions are seeded under one Cell of RW-WB before measurement.
     The `public_submit.get_region_children` lookup must STILL clear
     the 100 ms warm budget — this is the headline goal.

  3. Concurrency / DB collapse: hot endpoints are pounded by N parallel
     threads (`measure_concurrent`). p95 must remain inside budget AND
     no request may 5xx. This is the early-warning signal for missing
     indexes, lock-contention, or N+1 hot loops under real load.

Bulk write stress (issue submit / resolve / pull) lives in section 5.

Prereq: ONBOARDING suite must have provisioned RW-WB. Login as
ACTOR_PROJECT_ADMIN for the bulk-seed step (it bypasses public RPCs and
inserts regions via `/api/resource`).
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import requests

from _common import (
    ACTOR_GRM_OFFICER, ACTOR_PROJECT_ADMIN, ART, BULK_SCALE, PROJECT_RW,
    SuiteRun, check_budget, get, login, logout, measure_concurrent,
    measure_latencies, msg, perf_detail, post, run, state_for, stats,
    summary,
)


# ----------------------------------------------------------------- helpers

def _resource_post(s: requests.Session, doctype: str, payload: dict
                   ) -> tuple[int, dict]:
    return post(
        s,
        f"/api/resource/{doctype.replace(' ', '%20')}",
        data=payload,
        timeout=30,
    )


def _count_existing_children(s: requests.Session, project: str,
                             parent_region: str) -> int:
    """Count existing rows under (project, parent_region) so the seed
    step is idempotent across re-runs."""
    code, body = get(
        s,
        "/api/method/frappe.client.get_count",
        params={
            "doctype": "GRM Administrative Region",
            "filters": json.dumps([
                ["project", "=", project],
                ["parent_region", "=", parent_region],
            ]),
        },
        timeout=15,
    )
    if code != 200:
        return 0
    m = msg(body)
    if isinstance(m, dict) and "data" in m:
        m = m["data"]
    try:
        return int(m or 0)
    except (TypeError, ValueError):
        return 0


def bulk_seed_regions(s: requests.Session, suite: SuiteRun, rw: dict,
                      target_count: int) -> dict:
    """Idempotently ensure at least `target_count` Village-level regions
    exist under "Murama Cell" so the region cascade test has real volume.

    Re-runs do NOT explode the table: if `target_count` rows already exist
    we skip the seed entirely.

    Returns {"parent": <cell name>, "level": <village level name>,
             "seeded": <int>, "preexisting": <int>, "total_after": <int>}.
    """
    cell_name = rw["regions"].get("Murama Cell")
    village_level = rw["levels"].get("Village")
    if not (cell_name and village_level):
        suite.ok(
            "PF-bulk_seed.prereq",
            False,
            perf_detail(
                0,
                unit="rows",
                inputs={
                    "missing": "parent_or_level",
                    "cell": str(cell_name),
                    "level": str(village_level),
                },
            ),
        )
        return {"parent": None, "level": None, "seeded": 0,
                "preexisting": 0, "total_after": 0}

    project = rw["project_name"]
    preexisting = _count_existing_children(s, project, cell_name)
    needed = max(0, target_count - preexisting)

    seeded = 0
    t0 = time.perf_counter()
    if needed > 0:
        # Parallelise the seed — each row is an independent insert. We
        # keep workers modest (8) so we don't overwhelm the dev box.
        from concurrent.futures import ThreadPoolExecutor

        # Use a unique suffix per row so re-runs don't collide on
        # `region_name` even when parts of a previous run leaked rows.
        suffix = int(time.time())

        def _one(i: int) -> bool:
            c, _ = _resource_post(s, "GRM Administrative Region", {
                "project": project,
                "region_name": f"Perf-Village-{suffix}-{i:05d}",
                "administrative_level": village_level,
                "parent_region": cell_name,
            })
            return c in (200, 201)

        with ThreadPoolExecutor(max_workers=8) as ex:
            for ok_row in ex.map(_one, range(needed)):
                if ok_row:
                    seeded += 1

    elapsed = time.perf_counter() - t0
    total_after = preexisting + seeded
    rate = seeded / max(elapsed, 0.001)
    suite.ok(
        "PF-bulk_seed.regions_inserted",
        total_after >= target_count,
        perf_detail(
            seeded,
            unit="rows",
            n=needed,
            inputs={
                "parent": cell_name,
                "project": project,
                "level": village_level,
                "preexisting": preexisting,
                "needed": needed,
                "seeded": seeded,
                "total_after": total_after,
                "target": target_count,
                "elapsed_s": round(elapsed, 1),
                "rate_rows_s": int(rate),
                "workers": 8,
            },
        ),
    )
    return {
        "parent": cell_name,
        "level": village_level,
        "seeded": seeded,
        "preexisting": preexisting,
        "total_after": total_after,
    }


# ----------------------------------------------------------------- main

def main() -> int:
    suite = SuiteRun("PERFORMANCE")

    rw = state_for(PROJECT_RW)
    if not rw:
        suite.ok(
            "PF-0.RW_state_present", False,
            perf_detail(0, unit="rows",
                        inputs={"reason": "ONBOARDING must run first",
                                "project_code": PROJECT_RW}),
        )
        return summary(suite)
    rw_proj = rw["project_name"]

    # ---- Step 0: bulk-seed regions as platform admin -------------------
    s_admin = requests.Session()
    code, body = login(s_admin, *ACTOR_PROJECT_ADMIN)
    suite.ok(
        "PF-0.admin_login_for_seed",
        code == 200 and msg(body) == "Logged In",
        perf_detail(
            code, unit="http",
            inputs={"actor": ACTOR_PROJECT_ADMIN[0],
                    "endpoint": "/api/method/login",
                    "msg": str(msg(body))[:60]},
        ),
    )
    seed = bulk_seed_regions(s_admin, suite, rw, BULK_SCALE["regions_total"])
    logout(s_admin)

    # ---- Step 1: officer-side endpoint budgets -------------------------
    s = requests.Session()
    code, body = login(s, *ACTOR_GRM_OFFICER)
    suite.ok(
        "PF-1.officer_login",
        code == 200 and msg(body) == "Logged In",
        perf_detail(
            code, unit="http",
            inputs={"actor": ACTOR_GRM_OFFICER[0],
                    "endpoint": "/api/method/login",
                    "msg": str(msg(body))[:60]},
        ),
    )

    # PF-1: pull_changes cold + warm
    pull_inputs = {
        "endpoint_label": "sync.pull_changes",
        "regions_seeded_under_cell": seed.get("total_after", 0),
        "concurrency": 1,
    }

    def _pull():
        get(s, "/api/method/egrm.api.sync.pull_changes",
            params={"lastPulledAt": "", "schemaVersion": "1",
                    "migration": "null"}, timeout=30)

    cold = measure_latencies(_pull, n=1)[0]
    check_budget(suite, "PF-1.pull_changes_cold",
                 "sync.pull_changes_cold", cold, "cold_ms",
                 n=1, inputs=pull_inputs)

    warm = measure_latencies(_pull, n=5)
    st = stats(warm)
    check_budget(suite, "PF-1.pull_changes_warm_p50",
                 "sync.pull_changes_warm", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=pull_inputs)
    check_budget(suite, "PF-1.pull_changes_warm_p95",
                 "sync.pull_changes_warm", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=pull_inputs)

    # PF-2: lookup.user_context p95
    def _lookup():
        get(s, "/api/method/egrm.api.lookup.user_context", timeout=10)

    samples = measure_latencies(_lookup, n=20)
    st = stats(samples)
    lookup_inputs = {"actor": ACTOR_GRM_OFFICER[0], "concurrency": 1}
    check_budget(suite, "PF-2.user_context_p50",
                 "lookup.user_context", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=lookup_inputs)
    check_budget(suite, "PF-2.user_context_p95",
                 "lookup.user_context", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=lookup_inputs)

    # PF-3: bootinfo (drives whole desk load — must be quick)
    def _boot():
        get(s, "/api/method/frappe.boot.get_bootinfo", timeout=15)

    boot_inputs = {"actor": ACTOR_GRM_OFFICER[0], "concurrency": 1}
    boot_cold = measure_latencies(_boot, n=1)[0]
    check_budget(suite, "PF-3.bootinfo_cold",
                 "frappe.boot.get_bootinfo", boot_cold, "cold_ms",
                 n=1, inputs=boot_inputs)
    boot_warm = measure_latencies(_boot, n=5)
    st = stats(boot_warm)
    check_budget(suite, "PF-3.bootinfo_warm_p50",
                 "frappe.boot.get_bootinfo", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=boot_inputs)

    logout(s)

    # ---- Step 2: public-citizen endpoint budgets -----------------------
    s2 = requests.Session()
    pub_inputs = {"actor": "anonymous", "project": rw_proj, "concurrency": 1}

    def _config():
        get(s2, "/api/method/egrm.api.public_submit.get_submission_config",
            timeout=10)
    cold = measure_latencies(_config, n=1)[0]
    check_budget(suite, "PF-4.config_cold",
                 "public_submit.get_submission_config", cold, "cold_ms",
                 n=1, inputs=pub_inputs)
    warm = measure_latencies(_config, n=10)
    st = stats(warm)
    check_budget(suite, "PF-4.config_warm_p50",
                 "public_submit.get_submission_config", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=pub_inputs)
    check_budget(suite, "PF-4.config_warm_p95",
                 "public_submit.get_submission_config", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=pub_inputs)

    def _options():
        get(s2, "/api/method/egrm.api.public_submit.get_submission_options",
            params={"project": rw_proj}, timeout=10)
    measure_latencies(_options, n=1)
    warm = measure_latencies(_options, n=10)
    st = stats(warm)
    check_budget(suite, "PF-5.options_warm_p50",
                 "public_submit.get_submission_options", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=pub_inputs)
    check_budget(suite, "PF-5.options_warm_p95",
                 "public_submit.get_submission_options", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=pub_inputs)

    # PF-6: track_complaint p95
    def _track():
        get(s2, "/api/method/egrm.api.public_tracking.track_complaint",
            params={"tracking_code": "PERF-NONEXIST"}, timeout=10)
    samples = measure_latencies(_track, n=30)
    st = stats(samples)
    check_budget(suite, "PF-6.track_complaint_p95",
                 "public_tracking.track_complaint", st["p95"], "p95_warm_ms",
                 n=st["n"],
                 inputs={**pub_inputs, "tracking_code": "PERF-NONEXIST",
                         "expect": "404-ish"})

    # PF-7/8: dashboard
    def _dashboard():
        get(s2, "/api/method/egrm.api.public_metrics.get_public_dashboard",
            params={"project_id": rw_proj}, timeout=15)
    cold = measure_latencies(_dashboard, n=1)[0]
    check_budget(suite, "PF-7.dashboard_cold",
                 "public_metrics.get_public_dashboard", cold, "cold_ms",
                 n=1, inputs=pub_inputs)
    warm = measure_latencies(_dashboard, n=5)
    st = stats(warm)
    check_budget(suite, "PF-8.dashboard_warm_p50",
                 "public_metrics.get_public_dashboard", st["p50"], "p50_warm_ms",
                 n=st["n"], inputs=pub_inputs)
    check_budget(suite, "PF-8.dashboard_warm_p95",
                 "public_metrics.get_public_dashboard", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=pub_inputs)

    # PF-11: portal_config + translations (small payload, must be near-zero)
    def _portal():
        get(s2, "/api/method/egrm.api.portal_config.get_portal_config", timeout=10)
    samples = measure_latencies(_portal, n=10)
    st = stats(samples)
    check_budget(suite, "PF-11.portal_config_warm_p95",
                 "portal_config.get_portal_config", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs={"actor": "anonymous", "concurrency": 1})

    def _trans():
        get(s2, "/api/method/egrm.api.public_translations.get_translations",
            params={"lang": "en"}, timeout=10)
    samples = measure_latencies(_trans, n=10)
    st = stats(samples)
    check_budget(suite, "PF-12.translations_warm_p95",
                 "public_translations.get_translations", st["p95"], "p95_warm_ms",
                 n=st["n"],
                 inputs={"actor": "anonymous", "lang": "en", "concurrency": 1})

    # ---- Step 3: REGION CASCADE — locations under 100ms ----------------
    # The headline goal: even with thousands of seeded children,
    # public_submit.get_region_children must answer in <100 ms warm.
    if seed["parent"]:
        cascade_inputs_root = {
            "actor": "anonymous",
            "project": rw_proj,
            "parent_region": "root",
            "rows_under_seeded_cell": seed["total_after"],
        }
        cascade_inputs_deep = {
            "actor": "anonymous",
            "project": rw_proj,
            "parent_region": seed["parent"],
            "rows_under_seeded_cell": seed["total_after"],
        }

        def _kids_root():
            get(s2, "/api/method/egrm.api.public_submit.get_region_children",
                params={"project": rw_proj}, timeout=10)
        warm = measure_latencies(_kids_root, n=10)
        st = stats(warm)
        check_budget(suite, "PF-13.region_children_root_p50",
                     "public_submit.get_region_children", st["p50"], "p50_warm_ms",
                     n=st["n"], inputs=cascade_inputs_root)
        check_budget(suite, "PF-13.region_children_root_p95",
                     "public_submit.get_region_children", st["p95"], "p95_warm_ms",
                     n=st["n"], inputs=cascade_inputs_root)

        def _kids_deep():
            get(s2, "/api/method/egrm.api.public_submit.get_region_children",
                params={"project": rw_proj, "parent_region": seed["parent"]},
                timeout=10)
        warm = measure_latencies(_kids_deep, n=10)
        st = stats(warm)
        # This is the BIG one: the seeded cell now has 5000+ children
        # so any naive "load all then filter" implementation will tail
        # past 100 ms. Force a real index-backed query.
        check_budget(suite, "PF-14.region_children_deep_p50",
                     "public_submit.get_region_children", st["p50"], "p50_warm_ms",
                     n=st["n"], inputs=cascade_inputs_deep)
        check_budget(suite, "PF-14.region_children_deep_p95",
                     "public_submit.get_region_children", st["p95"], "p95_warm_ms",
                     n=st["n"], inputs=cascade_inputs_deep)
        suite.ok(
            "PF-14.children_count_under_seeded_cell",
            True,
            perf_detail(
                seed["total_after"], unit="rows",
                inputs={"parent": seed["parent"],
                        "preexisting": seed["preexisting"],
                        "seeded_this_run": seed["seeded"],
                        "total_after": seed["total_after"]},
            ),
        )

    # ---- Step 4: CONCURRENCY — DB collapse signal ----------------------
    n_conc = BULK_SCALE["concurrent_readers"]
    workers = 10

    def _conc_options():
        get(requests.Session(),  # fresh session per call to avoid keepalive bias
            "/api/method/egrm.api.public_submit.get_submission_options",
            params={"project": rw_proj}, timeout=15)
    lats, errs = measure_concurrent(_conc_options, n=n_conc, workers=workers)
    st = stats(lats)
    conc_inputs_options = {
        "actor": "anonymous", "project": rw_proj,
        "concurrency": workers, "calls": n_conc,
    }
    suite.ok(
        f"PF-15.options_{n_conc}x_no_errors",
        errs == 0,
        perf_detail(errs, unit="errors", n=n_conc, inputs=conc_inputs_options),
    )
    check_budget(suite, f"PF-15.options_{n_conc}x_p50",
                 "public_submit.get_submission_options", st["p50"], "conc_p50_ms",
                 n=st["n"], inputs=conc_inputs_options)
    check_budget(suite, f"PF-15.options_{n_conc}x_p95",
                 "public_submit.get_submission_options", st["p95"], "p95_warm_ms",
                 n=st["n"], inputs=conc_inputs_options)

    if seed["parent"]:
        def _conc_kids():
            get(requests.Session(),
                "/api/method/egrm.api.public_submit.get_region_children",
                params={"project": rw_proj, "parent_region": seed["parent"]},
                timeout=15)
        lats, errs = measure_concurrent(_conc_kids, n=n_conc, workers=workers)
        st = stats(lats)
        conc_inputs_kids = {
            "actor": "anonymous", "project": rw_proj,
            "parent_region": seed["parent"],
            "rows_under_seeded_cell": seed["total_after"],
            "concurrency": workers, "calls": n_conc,
        }
        suite.ok(
            f"PF-16.region_children_{n_conc}x_no_errors",
            errs == 0,
            perf_detail(errs, unit="errors", n=n_conc, inputs=conc_inputs_kids),
        )
        check_budget(suite, f"PF-16.region_children_{n_conc}x_p50",
                     "public_submit.get_region_children", st["p50"], "conc_p50_ms",
                     n=st["n"], inputs=conc_inputs_kids)

    def _conc_track():
        get(requests.Session(),
            "/api/method/egrm.api.public_tracking.track_complaint",
            params={"tracking_code": "PERF-CONC-NONEXIST"}, timeout=15)
    lats, errs = measure_concurrent(_conc_track, n=n_conc, workers=workers)
    st = stats(lats)
    conc_inputs_track = {
        "actor": "anonymous", "tracking_code": "PERF-CONC-NONEXIST",
        "concurrency": workers, "calls": n_conc,
    }
    suite.ok(
        f"PF-17.track_{n_conc}x_no_errors",
        errs == 0,
        perf_detail(errs, unit="errors", n=n_conc, inputs=conc_inputs_track),
    )
    check_budget(suite, f"PF-17.track_{n_conc}x_p50",
                 "public_tracking.track_complaint", st["p50"], "conc_p50_ms",
                 n=st["n"], inputs=conc_inputs_track)

    # ---- Step 5: BULK WRITES — submit + resolve + pull -----------------
    options_body = msg(get(
        s2, "/api/method/egrm.api.public_submit.get_submission_options",
        params={"project": rw_proj}, timeout=10)[1]) or {}
    if isinstance(options_body, dict) and "data" in options_body:
        options_body = options_body["data"]
    cats = (options_body or {}).get("categories", [])
    types = (options_body or {}).get("issue_types", [])
    leaf = next(
        (rw["regions"][n] for n in
         ("Nyamatete Village", "Murama Cell", "Mukarange Sector")
         if n in (rw.get("regions") or {})),
        None,
    )

    issue_ids: list[str] = []
    tracking_codes: list[str] = []
    if cats and types and leaf:
        n_seq = BULK_SCALE["issues_sequential"]
        bulk_inputs = {
            "actor": "anonymous", "project": rw_proj,
            "category": cats[0]["name"],
            "issue_type": types[0]["name"],
            "leaf_region": leaf,
            "concurrency": 1,
        }
        t0 = time.perf_counter()
        per_call: list[float] = []
        for i in range(n_seq):
            t1 = time.perf_counter()
            c, b = post(
                s2,
                "/api/method/egrm.api.public_submit.submit_grievance",
                data={
                    "project": rw_proj,
                    "category": cats[0]["name"],
                    "issue_type": types[0]["name"],
                    "administrative_region": leaf,
                    "description": f"PERF-BULK-{i:04d} bulk submit stress test.",
                    "contact_medium": "anonymous",
                    "citizen_name": f"PERF-{i:04d}",
                    "issue_date": "2026-05-08",
                },
                timeout=15,
            )
            per_call.append((time.perf_counter() - t1) * 1000.0)
            m = msg(b) or {}
            if isinstance(m, dict) and m.get("status") == "success":
                d = m.get("data", {})
                if d.get("name"):
                    issue_ids.append(d["name"])
                if d.get("tracking_code"):
                    tracking_codes.append(d["tracking_code"])
        elapsed = time.perf_counter() - t0
        st = stats(per_call)
        suite.ok(
            f"PF-18.bulk_submit_{n_seq}_succeeded",
            len(issue_ids) == n_seq,
            perf_detail(
                len(issue_ids),
                unit="issues",
                n=n_seq,
                inputs={**bulk_inputs,
                        "submitted": len(issue_ids),
                        "expected": n_seq,
                        "elapsed_s": round(elapsed, 1),
                        "rate_issues_s": int(
                            len(issue_ids) / max(elapsed, 0.001))},
            ),
        )
        check_budget(suite, f"PF-18.bulk_submit_p50",
                     "public_submit.submit_grievance", st["p50"], "p50_warm_ms",
                     n=st["n"], inputs=bulk_inputs)
        check_budget(suite, f"PF-18.bulk_submit_p95",
                     "public_submit.submit_grievance", st["p95"], "p95_warm_ms",
                     n=st["n"], inputs=bulk_inputs)

        # Concurrent submission (the real DB-collapse test).
        n_conc_sub = BULK_SCALE["issues_concurrent"]
        conc_sub_inputs = {**bulk_inputs, "concurrency": 10,
                           "calls": n_conc_sub}

        def _conc_submit():
            post(requests.Session(),
                 "/api/method/egrm.api.public_submit.submit_grievance",
                 data={
                     "project": rw_proj,
                     "category": cats[0]["name"],
                     "issue_type": types[0]["name"],
                     "administrative_region": leaf,
                     "description": "PERF-BULK-CONC submit",
                     "contact_medium": "anonymous",
                     "citizen_name": "PERF-CONC",
                     "issue_date": "2026-05-08",
                 },
                 timeout=20)

        lats, errs = measure_concurrent(_conc_submit, n=n_conc_sub, workers=10)
        st = stats(lats)
        suite.ok(
            f"PF-19.concurrent_submit_{n_conc_sub}_no_errors",
            errs == 0,
            perf_detail(errs, unit="errors", n=n_conc_sub,
                        inputs=conc_sub_inputs),
        )
        check_budget(suite, f"PF-19.concurrent_submit_p50",
                     "public_submit.submit_grievance", st["p50"], "conc_p50_ms",
                     n=st["n"], inputs=conc_sub_inputs)

    # ---- Step 6: bulk RESOLVE (auth as resolver) -----------------------
    if issue_ids:
        from _common import ACTOR_RESOLVER
        s3 = requests.Session()
        code, body = login(s3, *ACTOR_RESOLVER)
        suite.ok(
            "PF-20.resolver_login",
            code == 200 and msg(body) == "Logged In",
            perf_detail(
                code, unit="http",
                inputs={"actor": ACTOR_RESOLVER[0],
                        "endpoint": "/api/method/login",
                        "msg": str(msg(body))[:60]},
            ),
        )

        per_call = []
        n_resolve = min(len(issue_ids), 50)
        for i, iid in enumerate(issue_ids[:n_resolve]):
            t1 = time.perf_counter()
            post(s3,
                 "/api/method/egrm.api.issue.resolve",
                 data={"issue_id": iid,
                       "resolution_text": f"PERF bulk resolution {i}"},
                 timeout=15)
            per_call.append((time.perf_counter() - t1) * 1000.0)
        st = stats(per_call)
        resolve_inputs = {
            "actor": ACTOR_RESOLVER[0],
            "issues_resolved": n_resolve,
            "concurrency": 1,
            "from_pool_size": len(issue_ids),
        }
        check_budget(suite, "PF-20.bulk_resolve_p50",
                     "issue.resolve", st["p50"], "p50_warm_ms",
                     n=st["n"], inputs=resolve_inputs)
        check_budget(suite, "PF-20.bulk_resolve_p95",
                     "issue.resolve", st["p95"], "p95_warm_ms",
                     n=st["n"], inputs=resolve_inputs)

        # ---- Step 7: re-pull after bulk write — measure post-write sync.
        def _pull_after():
            get(s3, "/api/method/egrm.api.sync.pull_changes",
                params={"lastPulledAt": "", "schemaVersion": "1",
                        "migration": "null"}, timeout=30)
        warm = measure_latencies(_pull_after, n=5)
        st = stats(warm)
        pull_after_inputs = {
            "actor": ACTOR_RESOLVER[0],
            "concurrency": 1,
            "after_writes": n_resolve,
        }
        check_budget(suite, "PF-21.pull_after_bulk_p50",
                     "sync.pull_changes_warm", st["p50"], "p50_warm_ms",
                     n=st["n"], inputs=pull_after_inputs)
        check_budget(suite, "PF-21.pull_after_bulk_p95",
                     "sync.pull_changes_warm", st["p95"], "p95_warm_ms",
                     n=st["n"], inputs=pull_after_inputs)
        logout(s3)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
