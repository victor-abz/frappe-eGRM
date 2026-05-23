// ---------------------------------------------------------------------------
// Step 13 — Activate
// ---------------------------------------------------------------------------
class GRMWizardStep13Activate {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }

    async render() {
        if (!this.project) {
            this.$body.html(`
                <div class="grm-wizard-placeholder">
                  <p class="text-muted">${__("Save Step 1 first to create the project.")}</p>
                </div>
            `);
            return;
        }

        // Initial skeleton
        this.$body.html(`
            <div class="grm-step12" style="max-width: 720px;">
              <div class="grm-summary-card" style="border:1px solid var(--border-color, #d1d8dd); border-radius:6px; padding:16px; margin-bottom:16px;">
                <h4 style="margin-top:0;">${__("Project Summary")}</h4>
                <div id="grm-step12-summary"><p class="text-muted">${__("Loading counts...")}</p></div>
              </div>
              <div class="grm-coverage-card" style="border:1px solid var(--border-color, #d1d8dd); border-radius:6px; padding:16px; margin-bottom:16px;">
                <h4 style="margin-top:0;">${__("Region Duty Coverage")}</h4>
                <p class="text-muted small" style="margin-bottom:8px;">${__("Each region must have at least one user covering Intake, Review, and Investigate & Resolve. Duties may be split across multiple users or held by one person.")}</p>
                <div id="grm-step12-coverage"><p class="text-muted">${__("Loading coverage...")}</p></div>
              </div>
              <div id="grm-step12-action"></div>
            </div>
        `);

        const counts = await this.load_counts();
        this.render_summary(counts);
        const coverage = await this.load_coverage();
        this.render_coverage(coverage);
        this.render_action(coverage);
    }

    async load_coverage() {
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.preview_duty_coverage",
                args: { project: this.project.name },
            });
            return r.message || null;
        } catch (e) {
            return null;
        }
    }

    render_coverage(coverage) {
        const $c = this.$body.find("#grm-step12-coverage").empty();
        if (!coverage) {
            $c.html(`<p class="text-muted">${__("Coverage preview unavailable.")}</p>`);
            return;
        }
        const total = coverage.total_regions || 0;
        const covered = coverage.covered_regions || 0;
        const gaps = coverage.gaps || [];
        if (!total) {
            $c.html(`<p class="text-muted">${__("No regions defined yet.")}</p>`);
            return;
        }
        if (!gaps.length) {
            $c.html(`
                <div class="alert alert-success" style="margin:0;">
                  <strong>${__("All regions covered")}</strong>
                  — ${__("{0} of {1} regions have full duty coverage.", [covered, total])}
                </div>
            `);
            return;
        }
        const rows = gaps.slice(0, 50).map(g => `
            <tr>
              <td>${frappe.utils.escape_html(g.region_path || g.region_name)}</td>
              <td>${g.missing_duties.map(d => `<span class="indicator-pill orange">${frappe.utils.escape_html(d)}</span>`).join(" ")}</td>
            </tr>
        `).join("");
        const more = gaps.length > 50 ? `<p class="text-muted small">${__("Showing 50 of {0} gaps.", [gaps.length])}</p>` : "";
        $c.html(`
            <div class="alert alert-warning" style="margin-bottom:8px;">
              <strong>${__("{0} region(s) missing coverage", [gaps.length])}</strong>
              — ${__("{0} of {1} regions fully covered.", [covered, total])}
              ${__("Activation is blocked until every region has Intake, Review, and Investigate & Resolve.")}
            </div>
            <div style="max-height:240px; overflow:auto; border:1px solid var(--border-color, #d1d8dd); border-radius:4px;">
              <table class="table table-sm" style="margin:0;">
                <thead>
                  <tr><th>${__("Region")}</th><th>${__("Missing duties")}</th></tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
            ${more}
        `);
    }

    async load_counts() {
        const project = this.project.name;
        const counts = {
            adm_levels: 0,
            roles: 0,
            categories: 0,
        };
        try {
            counts.adm_levels = await frappe.db.count("GRM Administrative Level Type", {
                filters: { project },
            });
        } catch (e) {
            // ignore
        }
        try {
            counts.roles = await frappe.db.count("GRM Project Role", {
                filters: { project },
            });
        } catch (e) {
            // ignore
        }
        try {
            // Count distinct GRM Issue Categories linked to this project.
            //
            // We query the PARENT doctype (`GRM Issue Category`) with a
            // filter on its `grm_project_link` child table — the same
            // pattern used everywhere else in this wizard (search for
            // `[["GRM Project Link", "project", "=", ...]]`). Querying the
            // child `GRM Project Link` directly via `frappe.client.get_count`
            // raises "Insufficient Permission" for non-System-Manager
            // users because Frappe's child-table permission machinery
            // (has_child_permission) defers to the parent's `valid
            // parentfields`, and `get_count` doesn't pass a parent_doctype
            // — so the platform-admin actor was unable to land on
            // wizard Step 12 (Activate) until this rewrite.
            counts.categories = await frappe.db.count("GRM Issue Category", {
                filters: [["GRM Project Link", "project", "=", project]],
            });
        } catch (e) {
            try {
                counts.categories = await frappe.db.count("GRM Issue Category");
            } catch (_) {
                // ignore
            }
        }
        return counts;
    }

    render_summary(counts) {
        const p = this.project;
        const $s = this.$body.find("#grm-step12-summary").empty();
        $s.html(`
            <div class="form-grid">
              <table class="table table-borderless" style="margin-bottom:0;">
                <tbody>
                  <tr><th style="width:40%;">${__("Project Code")}</th><td>${frappe.utils.escape_html(p.project_code || "")}</td></tr>
                  <tr><th>${__("Title")}</th><td>${frappe.utils.escape_html(p.title || "")}</td></tr>
                  <tr><th>${__("Administrative Levels")}</th><td>${counts.adm_levels}</td></tr>
                  <tr><th>${__("Project Roles")}</th><td>${counts.roles}</td></tr>
                  <tr><th>${__("Issue Categories (linked)")}</th><td>${counts.categories}</td></tr>
                </tbody>
              </table>
            </div>
        `);
    }

    render_action(coverage) {
        const p = this.project;
        const $a = this.$body.find("#grm-step12-action").empty();
        const hasGaps = !!(coverage && (coverage.gaps || []).length);

        // Pre-flight checkbox row — XD-FIDELITY: xd-links Step 11 specifies
        // the activation pre-flight as Frappe-style Yes/No checkboxes
        // (same UX as permission rows). Render the confirmation toggles
        // unconditionally so the screen reads consistently whether the
        // project is already active or pending.
        const already = !!p.is_setup_complete;
        $a.html(`
            <div class="grm-activate-preflight" style="border:1px solid var(--border-color, #d1d8dd); border-radius:6px; padding:16px; margin-bottom:16px;">
              <h4 style="margin-top:0;">${__("Activation pre-flight")}</h4>
              <div class="form-group" style="margin-bottom:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-act-confirm" ${already ? "checked disabled" : ""}>
                  ${__("I confirm the project setup is complete")}
                </label>
              </div>
              <div class="form-group" style="margin-bottom:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-act-notify" ${already ? "checked disabled" : ""}>
                  ${__("Notify project administrators on activation")}
                </label>
              </div>
              <div class="form-group" style="margin-bottom:0;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-act-publish" ${already ? "checked disabled" : ""}>
                  ${__("Publish project to citizen portal")}
                </label>
              </div>
            </div>
        `);

        if (already) {
            $a.append(`
                <div class="alert alert-success" style="margin-bottom:0;">
                  <strong>${__("Project is already active.")}</strong>
                  <a href="/app/grm-project/${encodeURIComponent(p.name)}" class="ml-2">${__("Open project record")}</a>
                </div>
            `);
            $("#grm-next").prop("disabled", true).text(__("Already Active"));
        } else if (hasGaps) {
            $a.append(`
                <div class="alert alert-danger" style="margin-bottom:0;">
                  <strong>${__("Activation blocked")}</strong>
                  — ${__("resolve the duty-coverage gaps above before activating the project.")}
                </div>
            `);
            $("#grm-next").prop("disabled", true).text(__("Activate Project"));
        } else {
            $a.append(`
                <p>${__("Tick the confirmation above, then click \"Activate Project\" to mark setup complete and switch to the Platform workspace.")}</p>
            `);
            $("#grm-next").prop("disabled", false);
        }
    }

    async save() {
        // Step 12 has no per-step persistence — the wizard's complete_wizard()
        // call happens after this returns true (from advance()).
        if (!this.project) {
            frappe.show_alert({ message: __("No project loaded."), indicator: "red" });
            return false;
        }
        if (this.project.is_setup_complete) {
            // Don't re-activate; treat as no-op success but block the activation call.
            frappe.show_alert({ message: __("Project already active."), indicator: "blue" });
            return false;
        }
        const confirmed = this.$body.find("#grm-act-confirm").is(":checked");
        if (!confirmed) {
            frappe.show_alert({
                message: __("Tick \"I confirm the project setup is complete\" to activate."),
                indicator: "orange",
            });
            return false;
        }
        return true;
    }
}

