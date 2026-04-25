/**
 * eGRM workspace duty filter.
 *
 * v16 Workspace Link doesn't support display_depends_on — that field is
 * silently dropped during migrate. This shim runs after the desk loads,
 * reads frappe.boot.egrm.duties (populated by egrm.utils.boot.boot_session),
 * and hides phase-group cards in the eGRM workspace whose duty the user
 * doesn't hold.
 *
 * Phase-card → required duty mapping:
 *   "Intake"     → Intake
 *   "Triage"     → Review OR Assignment
 *   "Resolution" → Investigate & Resolve
 *   "Feedback"   → Feedback
 *   "Oversight"  → Supervise
 *
 * If the user holds none of the duties for a card, that card and all its
 * links are hidden. Bypass entirely for System Manager + GRM Platform
 * Administrator (they always see everything).
 */
(function () {
    if (typeof frappe === "undefined") return;

    // Card → array of duties; user needs ANY duty in the array to see the card.
    const CARD_DUTY_MAP = {
        "Intake":     ["Intake"],
        "Triage":     ["Review", "Assignment"],
        "Resolution": ["Investigate & Resolve"],
        "Feedback":   ["Feedback"],
        "Oversight":  ["Supervise"],
    };

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

    function applyFilter() {
        // Only act on the eGRM workspace
        const route = frappe.get_route ? frappe.get_route() : null;
        if (!route || route[0] !== "Workspaces" || route[1] !== "eGRM") return;
        if (isPlatformAdmin()) return;  // platform admins see everything

        // Each card-break in the workspace renders as a section with a
        // header containing the card name. Look up by header text.
        const $cards = $(".workspace-page .layout-section, .layout-section");
        $cards.each(function () {
            const $section = $(this);
            const headerText = $section.find(".widget-head .widget-title, .section-head, h4, h5")
                .first().text().trim();
            const requiredDuties = CARD_DUTY_MAP[headerText];
            if (!requiredDuties) return;  // not one of our gated cards
            if (!userHasAnyDuty(requiredDuties)) {
                $section.hide();
            } else {
                $section.show();
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
