/**
 * eGRM workspace duty + admin filter.
 *
 * v16 Workspace Link doesn't support display_depends_on — that field is
 * silently dropped during migrate. This shim runs after the desk loads,
 * reads frappe.boot.egrm (populated by egrm.utils.boot.boot_session),
 * and hides:
 *   1. Phase-group cards whose duty the user doesn't hold
 *   2. Admin-only cards (Projects / Users & Access / System) when the
 *      user is not a platform admin
 *
 * Review fix B6: i18n-safe matching. The previous implementation compared
 * the *rendered* header text against literal English keys, which broke
 * the moment the operator switched the site language and Frappe ran the
 * card headers through ``__()``. We now:
 *
 *   1. Stamp ``data-egrm-phase`` onto each section once on the first
 *      pass, using a label-to-phase map that includes BOTH the canonical
 *      English label AND its current ``__()`` translation. That way the
 *      stamping survives a later language change (we'd re-evaluate on
 *      route change), and subsequent passes can match by attribute
 *      instead of by fragile text.
 *   2. Hide / show by ``[data-egrm-phase="..."]`` lookup.
 */
(function () {
	if (typeof frappe === "undefined") return;

	// Canonical-English phase tokens. Each token has:
	//   - english:   the literal Card Break label as stored in workspace JSON.
	//   - duties:    duty list the caller needs ANY of (admins bypass).
	//   - adminOnly: true if the card should be hidden for non-platform admins.
	const PHASES = [
		{ phase: "intake", english: "Intake", duties: ["Intake"], adminOnly: false },
		{ phase: "triage", english: "Triage", duties: ["Review", "Assignment"], adminOnly: false },
		{
			phase: "resolution",
			english: "Resolution",
			duties: ["Investigate & Resolve"],
			adminOnly: false,
		},
		{ phase: "feedback", english: "Feedback", duties: ["Feedback"], adminOnly: false },
		{ phase: "oversight", english: "Oversight", duties: ["Supervise"], adminOnly: false },
		{ phase: "projects", english: "Projects", duties: [], adminOnly: true },
		{ phase: "users", english: "Users & Access", duties: [], adminOnly: true },
		{ phase: "system", english: "System", duties: [], adminOnly: true },
	];

	function translatedLabelMap() {
		// Map both the English label and its __() translation back to the
		// phase token, so we can resolve regardless of site language.
		const m = {};
		PHASES.forEach((p) => {
			m[p.english] = p.phase;
			try {
				const t = typeof __ === "function" ? __(p.english) : p.english;
				if (t && t !== p.english) m[t] = p.phase;
			} catch (_e) {
				/* __ may not yet be loaded; fall back to english */
			}
		});
		return m;
	}

	function phaseConfig(token) {
		return PHASES.find((p) => p.phase === token) || null;
	}

	function isPlatformAdmin() {
		return !!(frappe.boot && frappe.boot.egrm && frappe.boot.egrm.is_platform_admin);
	}

	function userDuties() {
		return (frappe.boot && frappe.boot.egrm && frappe.boot.egrm.duties) || [];
	}

	function userHasAnyDuty(needed) {
		const have = userDuties();
		return needed.some((d) => have.indexOf(d) !== -1);
	}

	function stampPhases() {
		const labelToPhase = translatedLabelMap();
		const $cards = $(".workspace-page .layout-section, .layout-section");
		$cards.each(function () {
			const $section = $(this);
			// Skip if already stamped — keeps idempotency across reapplies.
			if ($section.attr("data-egrm-phase")) return;
			const headerText = $section
				.find(".widget-head .widget-title, .section-head, h4, h5")
				.first()
				.text()
				.trim();
			const phase = labelToPhase[headerText];
			if (phase) $section.attr("data-egrm-phase", phase);
		});
	}

	function applyFilter() {
		// Only act on the eGRM workspace
		const route = frappe.get_route ? frappe.get_route() : null;
		if (!route || route[0] !== "Workspaces" || route[1] !== "eGRM") return;

		stampPhases();

		const admin = isPlatformAdmin();
		$("[data-egrm-phase]").each(function () {
			const $section = $(this);
			const cfg = phaseConfig($section.attr("data-egrm-phase"));
			if (!cfg) return;
			if (cfg.adminOnly) {
				if (admin) {
					$section.show();
				} else {
					$section.hide();
				}
				return;
			}
			if (admin || userHasAnyDuty(cfg.duties)) {
				$section.show();
			} else {
				$section.hide();
			}
		});
	}

	// Apply once on load and on every route change.
	$(document).on("page-change app_ready", applyFilter);
	if (frappe.router) {
		frappe.router.on("change", applyFilter);
	}
	// Also try once after a short delay for first paint.
	setTimeout(applyFilter, 1500);
})();
