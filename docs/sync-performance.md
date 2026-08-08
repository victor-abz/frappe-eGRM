# Mobile sync performance

How `egrm.api.sync.pull_changes` and `push_changes` perform, what was measured,
and how to re-measure. Every number here came from a run on the local bench
(`egrm.local`, MariaDB 10.6.22, macOS) — none are estimates. Where a number is
an extrapolation it says so.

## Budget

There is no ISO figure to quote: ISO/IEC 25010 names *time behaviour* as a
quality characteristic but sets no thresholds. The budget below comes from the
response-time limits that are actually standard practice — Nielsen's 0.1 s /
1 s / 10 s perception limits and the RAIL model's 100 ms guidance — applied to
what this endpoint is:

| Case | Target | Why |
| --- | --- | --- |
| Incremental pull (app foreground, nothing or little changed) | p95 < 200 ms | Runs on every foreground. Has to feel like it didn't happen. |
| One page of a full replay | p95 < 500 ms | Background, progress-reported, but must not look stalled. |
| Push | p95 < 1 s | User-initiated; a spinner is acceptable, a timeout is not. |
| Any single response body | < ~2 MB | Transferred over rural mobile data and parsed into WatermelonDB on the UI thread. |

## Where it stands

Incremental pull, 50k-issue dataset, 30 samples per row after 3 warm-ups:

| Device state | Records | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| up to date | 0 | 41.6 ms | 62.6 ms | 62.8 ms |
| 1 hour behind | 6 | 52.9 ms | 103.2 ms | 138.8 ms |
| 1 day behind | 14 | 50.3 ms | 103.3 ms | 215.1 ms |
| 7 days behind | 27 | 46.4 ms | 80.5 ms | 90.7 ms |
| 30 days behind | 27 | 55.8 ms | 88.4 ms | 102.4 ms |

The important property is not the absolute number but that it is **flat**: a
device 30 days behind costs the same as one that is up to date. Before this
work, latency scaled with the watermark's age and with the user's total
entitlement rather than with the number of records actually being delivered.

Full replay of 50,117 records, paginated at `PULL_PAGE_SIZE = 1000`: 51 pages,
p50 166 ms per page, **8.8 s total**. The same replay before this work took
**192 s** at 500 records/page, or a single 102.2 MB response unpaginated.

## What was slow, and why

Four separate problems, each found by profiling rather than by inspection.

### 1. Attachment scoping materialised the user's whole entitlement

`optimize_attachment_sync` filtered attachments with
`parent.isin(all_accessible_issue_ids)`. pypika renders every element of an
`IN` list through a Python call, so for a user entitled to 50k issues the
server spent about a second building the SQL string — twice per pull, before
MariaDB saw anything. cProfile on one page pull:

```
2.731s  pull_changes
2.719s    get_changes_since
2.588s      optimize_attachment_sync          <- 95% of the pull
0.922s        prepare_query / pypika get_sql  <- building the string
0.886s        100059 calls terms.py:743 <genexpr>
1.086s        Connection.query                <- executing a 50k-element IN
```

Replaced with an `IN (SELECT ...)` subquery, so the ID set never crosses into
Python and MariaDB resolves it as a semi-join (`type=eq_ref` on PRIMARY).

| | Old (IN list) | New (subquery) |
| --- | --- | --- |
| Scope query, 50,003 accessible issues | 905 ms | **1.2 ms** |
| Whole page pull | 2732 ms | **150 ms** |

The subquery also fixed two correctness defects, verified on seeded rows
covering six scoping cases: the old filter used *directly assigned* regions
while the issue query used the BFS-*expanded* set, so it **missed** attachments
on issues in descendant regions; and it never applied the draft-privacy rule,
so it **leaked** attachments belonging to other users' drafts.

### 2. Attachment time-window queries had no index

Frappe ships child tables indexed on `parent` only. Both attachment streams
filter on `creation`/`modified`, so both full-scanned. Parent scoping cannot
rescue them — that is the wide side of the query, not the selective one.
Measured on 500k attachment rows spread over ~347 days, one-day-old watermark
(1446 matching rows):

| | created stream | updated stream |
| --- | --- | --- |
| no index | 461.6 ms | 436.6 ms |
| with indexes | **11.6 ms** | **11.4 ms** |

`EXPLAIN`: `type=ALL key=NULL rows=390897` → `type=range rows=1446`.

### 3. Tombstones were queried once per table, unindexed

`Deleted Document` was asked "what was deleted since X" once for each of the 15
synced doctypes. On a site with only 39k tombstones that was **486 ms of a
572 ms** pull — 85% — and this table is append-only and never pruned, so it
gets worse forever.

Collapsed to one query, plus an index on `(deleted_doctype, creation)`. Frappe
indexes `creation` alone and the planner won't use it: tombstones cluster in
recent history, so `creation > watermark` isn't selective, while
`deleted_doctype` — the column that is — had no index.

| | Batched query |
| --- | --- |
| 15 queries, no index | 486 ms |
| 1 query, no index | 38.2 ms |
| 1 query, with index | **0.4 ms** |

A pull from a device 7 days behind went from 464.8 ms to 46.4 ms.

### 4. Reference-count index had its columns in the wrong order

The reconciliation check sizes the project-linked reference tables with
`count(distinct parent) ... group by parenttype`. Leading the index with
`parenttype` — the GROUP BY key — hands MariaDB pre-grouped rows and the
filesort disappears. Measured on 1M link rows across 5000 projects:

| Projects in scope | `(project, …)` | `(parenttype, …)` |
| --- | --- | --- |
| 3 | 6.9 ms | 1.8 ms |
| 10 | 23.1 ms | 5.7 ms |
| 40 | 325.0 ms | **22.4 ms** |

`EXPLAIN`: project-first `rows: 8000` + `Using filesort`; parenttype-first
`rows: 600` + `Using where; Using index`.

The result is fronted by `site_cache` (`REFERENCE_COUNT_TTL`), so a cache hit
is a dict lookup. `site_cache` was chosen over `redis_cache` deliberately:
`redis_cache` keys on `hash()`, which is per-process randomised for strings, so
its keys differ across gunicorn workers.

## Choosing the page size

Post-fix sweep over the same 50k dataset:

| Page size | Pages | p50 | p95 | Total replay | Bytes/page |
| --- | --- | --- | --- | --- | --- |
| unpaged | 1 | 3242 ms | 3242 ms | 3242 ms | 102.2 MB |
| 5000 | 11 | 423 ms | 559 ms | 4817 ms | 10.2 MB |
| 2000 | 26 | 225 ms | 244 ms | 6278 ms | 4.1 MB |
| **1000** | **51** | **166 ms** | **185 ms** | **8755 ms** | **2.0 MB** |
| 500 | 101 | 135 ms | 155 ms | 13888 ms | 1.0 MB |
| 250 | 201 | 119 ms | 152 ms | 24640 ms | 0.5 MB |

Every size clears the latency budget, so the binding constraint is the phone,
not the server: at ~2.1 KB per record the response has to cross a rural
connection and be parsed into WatermelonDB. 1000 is the largest page that keeps
that near 2 MB, and gets there in 37% less total replay time than 500.

Note the ~100 ms floor per pull: the 13 reference tables and the tombstone
lookup are paid per *request*, not per record, which is why halving the page
size does not halve page latency. Before the fixes above that floor was
~1900 ms and completely independent of page size — smaller pages were strictly
worse.

## Concurrency

30 pulls per worker, each worker its own process and DB connection, on the dev
laptop:

| Workers | p50 | p95 | Throughput |
| --- | --- | --- | --- |
| 1 | 43.2 ms | 65.2 ms | — |
| 5 | 133.8 ms | 289.8 ms | ~15 req/s |
| 10 | 213.0 ms | 423.3 ms | ~21 req/s |
| 20 | 396.3 ms | 636.8 ms | ~21 req/s |
| 30 | 573.2 ms | 941.8 ms | ~21 req/s |

Throughput plateaus around 21 req/s while p50 rises linearly with worker count
— the signature of a saturated machine, not a lock. This is a laptop running
MariaDB and 30 Python processes at once; the figure is a floor, not a capacity
estimate. What matters for capacity is per-request cost, which is now ~42 ms
instead of ~1900 ms, so the same hardware serves roughly 45× the devices.

A no-op pull is still 37 queries and ~15 ms of DB time; most of the remaining
~40 ms is Frappe query-builder overhead in Python. Cutting it further means
hand-writing SQL for 14 tables, which is not worth the risk at these numbers.

## Correctness guarantees the pagination rests on

In Frappe, `modified` is set equal to `creation` on insert and only moves
forward. So `modified > watermark` is exactly the union of the `created` and
`updated` streams, which is what lets one watermark page a response carrying
both streams across 14 tables. Every page delivers
`watermark < modified <= boundary`; the client advances to `boundary`; the next
page resumes strictly after it.

The page boundary is rounded **up** to the next whole millisecond. It leaves as
a datetime but reaches the client as integer milliseconds, while `modified`
carries microseconds — truncating would leave the boundary record still
matching `modified > watermark`, so it would be re-sent forever, and if every
record on a page shared that millisecond the cursor would never advance at all.

`_entitlement_widened_since` applies a cooldown keyed on
`sha1(user|widened_at)`. Without it, pages 2..N of a replay arrive as ordinary
incremental pulls whose watermark is still older than the assignment row, so
each one re-escalated to a full replay and refetched page one forever.

## Reproducing

Correctness (asserts paged output equals unpaginated output, is idempotent, and
that the cursor strictly advances):

```bash
cd /path/to/bench/sites
../env/bin/python /path/to/test_pull.py
```

Last run, 50,117 records:

```
RESULT_UNPAGED records=50117 hasMore=False 3630.5ms
RESULT_PAGED pages=11 distinct_records=50117
RESULT_MATCH PASS
RESULT_IDEMPOTENT PASS
RESULT_ADVANCE PASS
```

HTTP-level load test (`tests/load/sync_api.js`, k6) — covers what the in-process
benchmarks cannot: real HTTP framing, gunicorn worker contention, and the push
path under a constant arrival rate.

```bash
K6_BASE=http://egrm.local:8000 K6_USER=<user> K6_PASS=<password> \
  k6 run tests/load/sync_api.js
```

Three scenarios (`incremental` ramping 1→30 VUs, `replay` looping pages while
asserting the cursor advances, `push` at 5 req/s) with thresholds
`pull_incremental_ms p(95)<1000`, `pull_full_page_ms p(95)<10000`,
`push_ms p(95)<1000`, `http_req_failed rate<0.01`, `cursor_stalled rate==0`.

**This has not been run yet** — it needs credentials, which have to be supplied
by whoever runs it. The thresholds above are deliberately looser than the
budget at the top of this document: they are regression tripwires for CI, not
targets.

## Gotchas found while measuring

- The dev site's Frappe timezone is `Asia/Kolkata` while MariaDB `now()`
  returns UTC+2. Anything that seeds rows with raw SQL `now()` will be stamped
  hours away from what Frappe considers now, and time-window queries will
  silently miss them. Seed with `frappe.utils.now()`.
- `frappe.utils.caching.request_cache` indexes `_cache[func][args_key]`, so a
  harness that stubs `frappe.local.request_cache` must use
  `defaultdict(dict)`, not `{}`.
- `frappe.db.sql` does no `%` interpolation when called without parameters, so
  `%%` stays `%%` and MariaDB rejects it. Avoid `%` in unparameterised SQL.
- `bench console` (IPython) breaks lambda closures; run benchmark scripts
  directly under `env/bin/python` with `frappe.init()` + `frappe.connect()`,
  from the `sites/` directory.
