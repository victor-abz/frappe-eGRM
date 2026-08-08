/**
 * k6 load test for the mobile sync API.
 *
 * Covers the two endpoints the app calls on every sync, in the proportions a
 * real fleet produces: many incremental pulls, a few pushes, and the occasional
 * full replay from a device that reinstalled.
 *
 * Thresholds are the interactive-latency budget the app has to live inside, not
 * arbitrary round numbers. An incremental pull happens while the user waits on
 * the sync screen, so it is held to the 1s "keeps the user's flow uninterrupted"
 * bound from Nielsen's response-time limits (ISO 9241-11 usability, same
 * lineage). A paged full replay is background work behind a progress
 * indicator, so it gets the 10s "limit for keeping attention" bound.
 *
 * Run:
 *   cp tests/load/.env.example tests/load/.env   # fill in K6_USER / K6_PASS once
 *   ./tests/load/run.sh
 *
 * or pass the environment explicitly:
 *   K6_BASE=http://egrm.local:8000 K6_USER=... K6_PASS=... \
 *     k6 run tests/load/sync_api.js
 */
/* global __ENV -- injected by the k6 runtime, not a browser/node global */
import http from "k6/http";
import { check, group } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE = __ENV.K6_BASE || "http://egrm.local:8000";
const USER = __ENV.K6_USER;
const PASS = __ENV.K6_PASS;

const pullIncremental = new Trend("pull_incremental_ms", true);
const pullFull = new Trend("pull_full_page_ms", true);
const pushEmpty = new Trend("push_ms", true);
const pagesPerReplay = new Trend("pages_per_replay");
const cursorStalled = new Rate("cursor_stalled");

export const options = {
	scenarios: {
		// The dominant real-world call: a device checking for changes.
		incremental: {
			executor: "ramping-vus",
			exec: "incrementalPull",
			startVUs: 1,
			stages: [
				{ duration: "15s", target: 10 },
				{ duration: "30s", target: 30 },
				{ duration: "15s", target: 0 },
			],
		},
		// A reinstalled device draining its back catalogue page by page.
		replay: {
			executor: "constant-vus",
			exec: "fullReplay",
			vus: 2,
			duration: "60s",
			startTime: "10s",
		},
		push: {
			executor: "constant-arrival-rate",
			exec: "push",
			rate: 5,
			timeUnit: "1s",
			duration: "60s",
			preAllocatedVUs: 5,
		},
	},
	thresholds: {
		pull_incremental_ms: ["p(95)<1000"],
		pull_full_page_ms: ["p(95)<10000"],
		push_ms: ["p(95)<1000"],
		http_req_failed: ["rate<0.01"],
		cursor_stalled: ["rate==0"],
	},
};

export function setup() {
	if (!USER || !PASS) {
		throw new Error("Set K6_USER and K6_PASS (a test account) before running.");
	}
	const res = http.post(`${BASE}/api/method/login`, { usr: USER, pwd: PASS });
	check(res, { "login succeeded": (r) => r.status === 200 });
	return { cookies: res.cookies };
}

function jar(data) {
	const j = http.cookieJar();
	Object.keys(data.cookies).forEach((name) => {
		j.set(BASE, name, data.cookies[name][0].value);
	});
}

const pullUrl = (params) =>
	`${BASE}/api/method/egrm.api.sync.pull_changes?${Object.entries(params)
		.map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
		.join("&")}`;

export function incrementalPull(data) {
	jar(data);
	group("incremental pull", () => {
		// A watermark an hour old: the common steady-state case.
		const since = Date.now() - 3600 * 1000;
		const res = http.get(
			pullUrl({ lastPulledAt: since, counts: JSON.stringify({ grm_projects: 1 }) }),
			{ tags: { name: "pull_incremental" } }
		);
		pullIncremental.add(res.timings.duration);
		check(res, {
			"pull 200": (r) => r.status === 200,
			"has changes": (r) => !!r.json("message.changes"),
		});
	});
}

export function fullReplay(data) {
	jar(data);
	group("paged full replay", () => {
		let cursor = null;
		let pages = 0;
		// Bounded the same way the app bounds it.
		for (let i = 0; i < 50; i += 1) {
			// Continuation pages carry paging=1 and no counts, exactly as the app
			// sends them. Without the flag the server treats each page as a fresh
			// incremental pull and re-runs the entitlement check, so the suite
			// would measure the escalation path rather than the paging path.
			const res = http.get(
				cursor === null
					? pullUrl({ fullSync: 1 })
					: pullUrl({ lastPulledAt: cursor, paging: 1 }),
				{ tags: { name: "pull_full" } }
			);
			pullFull.add(res.timings.duration);
			if (!check(res, { "replay page 200": (r) => r.status === 200 })) return;

			const next = res.json("message.timestamp");
			// The whole pagination contract in one assertion: the cursor must move,
			// or the client would loop on the same page forever.
			cursorStalled.add(cursor !== null && next <= cursor ? 1 : 0);
			cursor = next;
			pages += 1;
			if (!res.json("message.hasMore")) break;
		}
		pagesPerReplay.add(pages);
	});
}

export function push(data) {
	jar(data);
	// Empty push: measures the endpoint's fixed cost — auth, session, transaction
	// setup — which every real push pays on top of its payload.
	const res = http.post(
		`${BASE}/api/method/egrm.api.sync.push_changes`,
		JSON.stringify({ changes: {}, lastPulledAt: Date.now() }),
		{ headers: { "Content-Type": "application/json" }, tags: { name: "push" } }
	);
	pushEmpty.add(res.timings.duration);
	check(res, { "push ok": (r) => r.status === 200 || r.status === 204 });
}
