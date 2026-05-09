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
 * Phase-card → required duty mapping:
 *   "Intake"     → Intake
 *   "Triage"     → Review OR Assignment
 *   "Resolution" → Investigate & Resolve
 *   "Feedback"   → Feedback
 *   "Oversight"  → Supervise
 *
 * Admin-only cards (require frappe.boot.egrm.is_platform_admin):
 *   "Projects", "Users & Access", "System"
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

    // Cards that only platform admins should see.
    const ADMIN_ONLY_CARDS = new Set([
        "Projects",
        "Users & Access",
        "System",
    ]);

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

        const admin = isPlatformAdmin();

        // Each card-break in the workspace renders as a section with a
        // header containing the card name. Look up by header text.
        const $cards = $(".workspace-page .layout-section, .layout-section");
        $cards.each(function () {
            const $section = $(this);
            const headerText = $section.find(".widget-head .widget-title, .section-head, h4, h5")
                .first().text().trim();

            if (ADMIN_ONLY_CARDS.has(headerText)) {
                if (admin) { $section.show(); } else { $section.hide(); }
                return;
            }

            const requiredDuties = CARD_DUTY_MAP[headerText];
            if (!requiredDuties) return;  // not one of our gated cards
            if (admin || userHasAnyDuty(requiredDuties)) {
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
