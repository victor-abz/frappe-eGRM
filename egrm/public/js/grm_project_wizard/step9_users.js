class GRMWizardStep9Users {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.add_panel = null;       // Single-user add subform
        this.import_panel = null;    // Bulk 4-stage flow
        this.current_mode = "single"; // toggled to "bulk" if list loads with 0 users
        this.render();
    }

    render() {
        if (!this.project) {
            this.$body.html(`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`);
            return;
        }
        // Composition: coverage banner + existing-users list + Add-users panel.
        this.$body.html(`
            <div class="grm-step9-coverage-banner"></div>
            <div class="grm-step9-users-panel"></div>
            <div class="grm-step9-add-section">
              <div class="grm-step9-add-toggle" role="tablist">
                <button type="button" class="btn btn-default active" data-mode="single">${__("Single user")}</button>
                <button type="button" class="btn btn-default" data-mode="bulk">${__("CSV/Excel import")}</button>
              </div>
              <div class="grm-step9-add-content"></div>
            </div>
        `);
        const $list_body = this.$body.find(".grm-step9-users-panel");
        // E.6: when the list finishes its first load and has 0 rows,
        // flip the toggle to "bulk" so the operator lands on the import
        // flow instead of the single-add form.
        this.list_panel = new GRMWizardStep9UsersList(
            $list_body, this.project, this.wizard,
            (total) => {
                if (total === 0 && this.current_mode !== "bulk") {
                    this.set_mode("bulk");
                }
            },
        );

        this.render_add_panel();
        this.refresh_coverage();
    }

    async refresh_coverage() {
        const $banner = this.$body.find(".grm-step9-coverage-banner").empty();
        if (!this.project) return;
        let coverage;
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.preview_duty_coverage",
                args: { project: this.project.name },
            });
            coverage = r.message;
        } catch (e) {
            return; // banner silent on error; activation step will block
        }
        if (!coverage || !coverage.total_regions) return;
        const gaps = coverage.gaps || [];
        if (!gaps.length) {
            $banner.html(`
                <div class="alert alert-success" style="margin-bottom:12px;">
                  <strong>${__("Duty coverage complete")}</strong>
                  — ${__("all {0} region(s) have Intake, Review, and Investigate & Resolve.", [coverage.total_regions])}
                </div>
            `);
            return;
        }
        // Operator can either (a) add users to fix gaps or (b) remove the
        // uncovered regions from the project. The list below renders one
        // checkbox per gap with a master select-all + "Remove selected"
        // action that wires to the ``remove_regions`` RPC.
        const rows = gaps.map(g => `
            <tr data-region="${frappe.utils.escape_html(g.region)}">
              <td style="width:30px;"><input type="checkbox" class="grm-cov-gap-cb"/></td>
              <td><code>${frappe.utils.escape_html(g.region_path || g.region_name)}</code></td>
              <td class="text-muted small">${g.missing_duties.join(", ")}</td>
            </tr>
        `).join("");
        $banner.html(`
            <div class="alert alert-warning grm-cov-banner" style="margin-bottom:12px;">
              <strong>${__("{0} of {1} region(s) missing duty coverage", [gaps.length, coverage.total_regions])}</strong>
              <p class="text-muted small" style="margin:4px 0;">
                ${__("Each region must cover Intake, Review, and Investigate & Resolve duties. Add users below, or remove regions you don't intend to use.")}
              </p>
              <div style="max-height:240px; overflow:auto; background:#fff; border:1px solid #e0e0e0; border-radius:4px; padding:6px 8px; margin-top:8px;">
                <table class="table table-sm" style="margin:0;">
                  <thead>
                    <tr>
                      <th><input type="checkbox" class="grm-cov-select-all"/></th>
                      <th>${__("Region")}</th>
                      <th>${__("Missing duties")}</th>
                    </tr>
                  </thead>
                  <tbody>${rows}</tbody>
                </table>
              </div>
              <div style="margin-top:8px;">
                <button type="button" class="btn btn-sm btn-danger grm-cov-remove" disabled>
                  ${__("Remove selected regions from project")}
                </button>
                <span class="text-muted small" style="margin-left:8px;">
                  ${__("Removal is blocked for any region that still has active users.")}
                </span>
              </div>
            </div>
        `);

        const $select_all = $banner.find(".grm-cov-select-all");
        const $cbs = $banner.find(".grm-cov-gap-cb");
        const $btn = $banner.find(".grm-cov-remove");
        const refresh_btn_state = () => {
            const n = $banner.find(".grm-cov-gap-cb:checked").length;
            $btn.prop("disabled", n === 0)
                .text(n > 0
                    ? __("Remove {0} selected region(s) from project", [n])
                    : __("Remove selected regions from project"));
        };
        $select_all.on("change", (ev) => {
            $cbs.prop("checked", ev.target.checked);
            refresh_btn_state();
        });
        $cbs.on("change", refresh_btn_state);
        $btn.on("click", async () => {
            const ids = $banner.find(".grm-cov-gap-cb:checked")
                .map(function() { return $(this).closest("tr").data("region"); })
                .get()
                .filter(Boolean);
            if (!ids.length) return;

            // Step 1 — preview the exact impact so the operator sees the
            // full cascade before any deletion happens.
            $btn.prop("disabled", true).text(__("Computing impact…"));
            let preview;
            try {
                const pr = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.preview_remove_regions",
                    args: { project: this.project.name, regions: ids },
                });
                preview = (pr && pr.message) || {};
            } catch (e) {
                frappe.show_alert({ message: __("Could not compute removal impact"), indicator: "red" });
                $btn.prop("disabled", false);
                refresh_btn_state();
                return;
            }
            const totals = preview.totals || { regions: 0, descendants: 0, users: 0 };

            // Build a per-row preview list (capped) so the operator can see
            // *which* descendants get pulled in.
            const sample = (preview.rows || [])
                .map(row => {
                    const parts = [`<strong>${frappe.utils.escape_html(row.region_name || row.region)}</strong>`];
                    if (row.descendants) parts.push(__("{0} descendant region(s)", [row.descendants]));
                    if (row.users) parts.push(__("{0} active user(s)", [row.users]));
                    return "<li>" + parts.join(" — ") + "</li>";
                })
                .join("");

            const cascade_needed = totals.users > 0;
            const header = cascade_needed
                ? __("Confirm cascade removal")
                : __("Confirm removal");
            const summary = __(
                "You are about to remove {0} selected region(s). This will also remove {1} descendant region(s) and unassign {2} active user(s) from project '{3}'.",
                [totals.regions, totals.descendants, totals.users, this.project.name]
            );
            const enforced = cascade_needed
                ? __("There is no way to keep the descendants — descendants without an ancestor produce orphan regions, which the wizard refuses to create.")
                : "";
            const body_html = `
                <div>
                    <p>${frappe.utils.escape_html(summary)}</p>
                    ${sample ? `<ul style="margin: 8px 0; padding-left: 18px;">${sample}</ul>` : ""}
                    ${enforced ? `<p style="color:#9e3a3a; margin: 6px 0 0 0;">${frappe.utils.escape_html(enforced)}</p>` : ""}
                </div>
            `;

            const confirmed = await new Promise((resolve) => {
                const d = new frappe.ui.Dialog({
                    title: header,
                    primary_action_label: cascade_needed
                        ? __("Yes, remove regions + descendants + unassign users")
                        : __("Yes, remove"),
                    primary_action: () => { d.hide(); resolve(true); },
                    secondary_action_label: __("Cancel"),
                    secondary_action: () => { d.hide(); resolve(false); },
                });
                d.$body.html(body_html);
                d.show();
                d.$wrapper.find(".btn-modal-secondary").on("click", () => { resolve(false); });
            });
            if (!confirmed) {
                $btn.prop("disabled", false);
                refresh_btn_state();
                return;
            }

            $btn.prop("disabled", true).text(__("Removing…"));
            try {
                const r = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.remove_regions",
                    args: { project: this.project.name, regions: ids, cascade_users: 1 },
                });
                const m = (r && r.message) || {};
                const deleted = (m.deleted || []).length;
                const skipped = (m.skipped || []).length;
                const cascaded_users = m.cascaded_users || 0;
                const cascaded_regions = m.cascaded_regions || 0;
                let msg = __("Removed {0} region(s)", [deleted]);
                if (cascaded_regions) msg += "; " + __("plus {0} descendant region(s)", [cascaded_regions]);
                if (cascaded_users) msg += "; " + __("unassigned {0} user(s)", [cascaded_users]);
                if (skipped) msg += "; " + __("skipped {0}", [skipped]);
                frappe.show_alert({
                    message: msg,
                    indicator: skipped ? "orange" : "green",
                });
            } catch (e) {
                frappe.show_alert({ message: __("Region removal failed"), indicator: "red" });
            } finally {
                this.refresh_coverage();
            }
        });
    }

    render_add_panel() {
        const $section = this.$body.find(".grm-step9-add-section");
        const $content = $section.find(".grm-step9-add-content");

        // Pre-construct both panels — render is cheap because they only
        // hit the network when first switched-to.
        this.add_panel = new GRMWizardStep9UserAdd({
            project: this.project,
            $mount: $content,
            on_added: () => {
                if (this.list_panel && this.list_panel.refresh) {
                    this.list_panel.refresh();
                }
                this.refresh_coverage();
            },
        });
        this.import_panel = new GRMWizardStep9UserImport({
            project: this.project,
            $mount: $content,
            on_completed: () => {
                if (this.list_panel && this.list_panel.refresh) {
                    this.list_panel.refresh();
                }
                this.refresh_coverage();
            },
        });

        // Initial mode (single by default; flipped by list-panel callback
        // when the project has 0 users).
        this._render_mode($content);

        $section.find(".grm-step9-add-toggle button").on("click", (ev) => {
            const $btn = $(ev.currentTarget);
            const mode = $btn.data("mode");
            this.set_mode(mode);
        });
    }

    set_mode(mode) {
        if (mode !== "single" && mode !== "bulk") return;
        this.current_mode = mode;
        const $section = this.$body.find(".grm-step9-add-section");
        $section.find(".grm-step9-add-toggle button").removeClass("active");
        $section.find(`.grm-step9-add-toggle button[data-mode="${mode}"]`).addClass("active");
        const $content = $section.find(".grm-step9-add-content");
        $content.empty();
        this._render_mode($content);
    }

    _render_mode($content) {
        if (this.current_mode === "bulk") {
            this.import_panel.render();
        } else {
            this.add_panel.render();
        }
    }

    async save() {
        // Gate: every region must have at least one user covering Intake,
        // Review, and Investigate & Resolve. Step 13 already blocks the
        // final "Activate" click — we enforce here too so the operator
        // can't sail past Steps 10/11/12 only to be stopped at the end.
        if (!this.project) return true;
        let coverage;
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.preview_duty_coverage",
                args: { project: this.project.name },
            });
            coverage = r.message;
        } catch (e) {
            // Network/RPC failure — fall back to letting Step 13 catch it.
            return true;
        }
        const gaps = (coverage && coverage.gaps) || [];
        if (!gaps.length) return true;

        const sample = gaps.slice(0, 5).map(g =>
            `<li><code>${frappe.utils.escape_html(g.region_path || g.region_name)}</code>: ${g.missing_duties.join(", ")}</li>`
        ).join("");
        const more = gaps.length > 5
            ? `<li class="text-muted">${__("...and {0} more", [gaps.length - 5])}</li>`
            : "";
        frappe.msgprint({
            title: __("Duty coverage incomplete"),
            indicator: "red",
            message: `
                <p>${__("Each region must have at least one user covering Intake, Review, and Investigate & Resolve.")}</p>
                <p>${__("{0} of {1} region(s) are missing coverage:", [gaps.length, coverage.total_regions])}</p>
                <ul>${sample}${more}</ul>
                <p>${__("Add or reassign users above before continuing.")}</p>
            `,
        });
        // Refresh the banner so the gaps stay visible while operator fixes them.
        this.refresh_coverage();
        return false;
    }
}

