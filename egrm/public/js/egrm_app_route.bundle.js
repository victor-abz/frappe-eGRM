/**
 * eGRM router shim — companion to ``egrm.utils.app_route_passthrough``.
 *
 * The server-side hook rewrites incoming ``/app/<rest>`` requests to
 * ``/desk/<rest>`` so the desk shell renders without a 301, while the
 * browser URL bar keeps the canonical ``/app/<rest>`` form (which is
 * what AQE's ``UI-0`` Playwright assertion waits for via
 * ``wait_for_url("**\/app**")``).
 *
 * That fixes the *server* side, but the client-side router parses
 * ``window.location.pathname`` to figure out the current route. Frappe's
 * ``frappe.router.strip_prefix`` only strips ``desk/`` — it leaves
 * ``app/`` intact. So a navigation to ``/app/grm-project-wizard`` is
 * parsed as the 2-element route ``["app", "grm-project-wizard"]``, the
 * router treats ``app`` as the page name, calls
 * ``frappe.desk.desk_page.getpage(name="app")``, and renders the
 * "Page app not found" message page.
 *
 * This shim teaches ``strip_prefix`` to peel the leading ``app/`` exactly
 * the way it already peels ``desk/``. After it runs the router parses
 * ``/app/grm-project-wizard`` as ``["grm-project-wizard"]``, which
 * resolves cleanly against ``frappe.boot.page_info``.
 *
 * Idempotent: only patches once even if the bundle is included twice.
 */
(function () {
	if (typeof frappe === "undefined" || !frappe.router) return;
	if (frappe.router.__egrm_app_route_patched) return;

	const _orig = frappe.router.strip_prefix.bind(frappe.router);
	frappe.router.strip_prefix = function (route) {
		let r = _orig(route);
		// Mirror the existing `if (r === "desk") r = r.substr(4)` /
		// `if (r.startsWith("desk/")) r = r.substr(4)` clauses for `app`.
		if (r === "app") r = "";
		if (r.startsWith("app/")) r = r.substr(4);
		return r;
	};
	frappe.router.__egrm_app_route_patched = true;
})();
