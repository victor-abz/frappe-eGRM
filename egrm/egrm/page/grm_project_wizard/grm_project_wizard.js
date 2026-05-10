frappe.pages["grm-project-wizard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Setup Wizard"),
        single_column: true,
    });
    new GRMProjectWizard(page);
};

// Display order is dependency-driven, NOT class-name order:
//   Categories (now display 5) needs Roles + Departments to exist first,
//   so User Types and Departments are promoted to display 3 and 4. The
//   underlying step classes keep their original numeric names — only the
//   slot they occupy in `step_class()` and the title shown to the user
//   changes. See comments above `step_class()` for the full mapping.
const STEP_TITLES = [
    "",
    "Project Information",            //  1
    "Administrative Levels & Regions", //  2
    "User Types",                     //  3 (was 7) — must precede Categories
    "Departments",                    //  4 (was 8) — must precede Categories
    "Issue Categories",               //  5 (was 3)
    "Issue Types",                    //  6 (was 4)
    "Citizen Groups",                 //  7 (was 5)
    "Notification Templates",         //  8 (was 6)
    "Users",                          //  9
    "Issue Routing",                  // 10
    "SLAs",                           // 11
    "Issue Statuses",                 // 12
    "Activate",                       // 13
];

const TOTAL_STEPS = 13;

// ---------------------------------------------------------------------------
// Reusable bulk-selection helper for wizard tables that use the simple HTML
// `<table class="table table-borderless">` markup (Steps 5, 6, 7, 8, 9, 11, 12).
// Steps 3 and 4 use the Frappe div-grid pattern and inline their own bulk
// wiring — see `bind_bulk_select` / `refresh_bulk_actions` on those classes.
//
// Caller responsibilities:
//   1. Maintain `this.selected = new Set()` on the step instance and pass it in.
//   2. Render `${grm_render_bulk_toolbar(key)}` above the table.
//   3. Add a leading checkbox cell to the header + each row:
//          <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all"></th>
//          <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check"></td>
//      Each <tr> must carry `data-name="{row.name}"`.
//   4. After mounting, call `grm_wire_bulk_table($wrap, opts)`.
//
// The helper is idempotent: it namespaces handlers (`.grm-bulk`) and rebinds
// safely on every re-render.
// ---------------------------------------------------------------------------
function grm_render_bulk_toolbar(key) {
    return `
      <div class="grm-bulk-actions" data-grm-bulk-for="${key}" hidden>
        <span class="grm-bulk-count"></span>
        <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__("Delete")}</button>
        <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__("Clear selection")}</button>
      </div>
    `;
}

function grm_wire_bulk_table($wrap, opts) {
    const { selected, row_names, key, delete_one, on_done } = opts;
    const singular = opts.singular || __("row");
    const plural = opts.plural || (singular + "s");
    const confirm_msg = opts.confirm_msg || ((n) => n === 1
        ? __("Delete this {0}?", [singular])
        : __("Delete {0} selected {1}?", [n, plural]));

    const $bar = $wrap.find(`.grm-bulk-actions[data-grm-bulk-for='${key}']`);
    const $tbl = $wrap.find("table");

    function refresh() {
        const n = selected.size;
        $bar.attr("hidden", n === 0 ? "hidden" : null);
        $bar.find(".grm-bulk-count").text(
            n === 0 ? "" : (n === 1 ? __("1 selected") : __("{0} selected", [n])),
        );
        $bar.find(".grm-bulk-delete").text(
            n <= 1 ? __("Delete") : __("Delete {0}", [n]),
        );
        const total = row_names.length;
        const $all = $tbl.find(".grm-bulk-all");
        if (total > 0) {
            $all.prop("checked", n === total);
            $all.prop("indeterminate", n > 0 && n < total);
        }
        $tbl.find(".grm-bulk-row-check").each(function () {
            const name = $(this).closest("tr").attr("data-name");
            $(this).prop("checked", !!name && selected.has(name));
        });
    }

    $wrap.off(".grm-bulk")
        .on("change.grm-bulk", ".grm-bulk-all", function () {
            const checked = $(this).prop("checked");
            if (checked) row_names.forEach((n) => selected.add(n));
            else selected.clear();
            refresh();
        })
        .on("change.grm-bulk", ".grm-bulk-row-check", function () {
            const name = $(this).closest("tr").attr("data-name");
            if (!name) return;
            if ($(this).prop("checked")) selected.add(name);
            else selected.delete(name);
            refresh();
        })
        .on("click.grm-bulk", ".grm-bulk-clear", () => {
            selected.clear();
            refresh();
        })
        .on("click.grm-bulk", ".grm-bulk-delete", async () => {
            const names = [...selected];
            if (!names.length) return;
            const proceed = await new Promise((res) =>
                frappe.confirm(confirm_msg(names.length), () => res(true), () => res(false)),
            );
            if (!proceed) return;
            const errs = [];
            frappe.dom.freeze(__("Deleting…"));
            for (const name of names) {
                try { await delete_one(name); }
                catch (e) { errs.push(name); }
            }
            frappe.dom.unfreeze();
            selected.clear();
            if (errs.length) {
                frappe.show_alert({
                    message: __("Could not delete {0} {1} — they may still be referenced.",
                        [errs.length, errs.length === 1 ? singular : plural]),
                    indicator: "red",
                });
            } else {
                frappe.show_alert({
                    message: __("{0} {1} deleted.",
                        [names.length, names.length === 1 ? singular : plural]),
                    indicator: "green",
                });
            }
            if (on_done) await on_done();
        });

    refresh();
}

class GRMProjectWizard {
    constructor(page) {
        this.page = page;
        this.project_name = frappe.utils.get_url_arg("project");
        this.current_step = 1;
        this.project = null;
        this.render_shell();
        this.load_project();
    }

    render_shell() {
        $(this.page.body).html(`
            <div class="grm-wizard">
              <div class="grm-wizard-header">
                <div id="grm-stepper" class="grm-wizard-stepper"></div>
                <h2 id="grm-step-title" class="grm-wizard-title"></h2>
              </div>
              <div id="grm-step-body" class="grm-wizard-body"></div>
              <div class="grm-wizard-footer">
                <button class="btn btn-default" id="grm-prev">${__("Back")}</button>
                <span id="grm-step-status" class="text-muted small"></span>
                <button class="btn btn-primary" id="grm-next">${__("Continue")}</button>
              </div>
            </div>
        `);
        $("#grm-prev").on("click", () => this.goto_step(this.current_step - 1));
        $("#grm-next").on("click", () => this.advance());
        // Stepper dots are clickable shortcuts to any step. Useful for reviewing
        // existing data on already-saved projects. Navigation is direct (no
        // implicit save of the current step) — for save-and-advance, use
        // Continue. Disabled dots (e.g. when project hasn't been saved yet)
        // are inert via the native button [disabled] attribute.
        $("#grm-stepper").on("click", ".grm-step", (e) => {
            const $btn = $(e.currentTarget);
            if ($btn.is(":disabled") || $btn.attr("aria-disabled") === "true") return;
            const n = parseInt($btn.attr("data-step"), 10);
            if (!Number.isFinite(n) || n === this.current_step) return;
            this.goto_step(n);
        });
    }

    async load_project() {
        if (this.project_name) {
            try {
                const r = await frappe.db.get_doc("GRM Project", this.project_name);
                this.project = r;
                this.current_step = Math.max(1, Math.min(TOTAL_STEPS, r.current_setup_step || 1));
            } catch (e) {
                frappe.show_alert({ message: __("Project not found"), indicator: "red" });
            }
        }
        // ---- AQE test-only override -------------------------------------
        // The AQE UI-SCREENSHOTS suite captures one PNG per wizard step
        // for fidelity review. It needs a *deterministic* way to land on
        // any step without driving the full multi-RPC click flow. When
        // the URL carries `?aqe_force_step=N` we honour it (clamped to
        // [1, TOTAL_STEPS]) without persisting it back to the project's
        // `current_setup_step`. This is purely a renderer override —
        // unrelated to the production "save & continue" flow.
        const forced = parseInt(frappe.utils.get_url_arg("aqe_force_step"), 10);
        if (Number.isFinite(forced) && forced >= 1 && forced <= TOTAL_STEPS) {
            this.current_step = forced;
            this._aqe_forced = true;
        }
        this.render_step();
    }

    render_step() {
        $("#grm-step-title").text(`${this.current_step}. ${STEP_TITLES[this.current_step]}`);
        this.render_stepper();
        this.render_step_body();
        this.update_footer();
    }

    render_stepper() {
        // Stepper dots are clickable buttons (Option C — pulsing halo on active).
        // CSS sizes them as solid circles; the visible label is the tooltip.
        // Until Step 1 is saved (no project yet) only the current step is enabled,
        // so users can't jump into a step that has nothing to render.
        const $s = $("#grm-stepper").empty();
        const has_project = !!(this.project && this.project.name);
        for (let i = 1; i <= TOTAL_STEPS; i++) {
            const cls = i < this.current_step ? "done" : i === this.current_step ? "active" : "pending";
            const title = `${i}. ${STEP_TITLES[i] || ""}`;
            const aria_label = `${__("Go to step")} ${title}`;
            const aria_current = i === this.current_step ? 'aria-current="step"' : "";
            const disabled = !has_project && i !== this.current_step ? 'disabled aria-disabled="true"' : "";
            $s.append(
                `<button type="button" class="grm-step ${cls}" data-step="${i}" `
                + `title="${frappe.utils.escape_html(title)}" `
                + `aria-label="${frappe.utils.escape_html(aria_label)}" `
                + `${aria_current} ${disabled}></button>`,
            );
        }
    }

    step_class(n) {
        // NOTE: class names retain their *original* step number (e.g.
        // GRMWizardStep3IssueCategories) but the *display* slot they
        // occupy was reordered so data dependencies are honoured. The
        // wizard always asks for things you'll need before the step
        // that consumes them. Class-name N != display-slot key.
        const map = {
            1:  GRMWizardStep1ProjectInfo,           // 1 → Project Information
            2:  GRMWizardStep2AdminUnits,            // 2 → Admin Levels & Regions
            3:  GRMWizardStep7ProjectRoles,          // 3 → User Types  (was 7)
            4:  GRMWizardStep8Departments,           // 4 → Departments (was 8)
            5:  GRMWizardStep3IssueCategories,       // 5 → Categories  (was 3, needs roles+depts)
            6:  GRMWizardStep4IssueTypes,            // 6 → Issue Types (was 4)
            7:  GRMWizardStep5CitizenLookups,        // 7 → Citizen Groups (was 5)
            8:  GRMWizardStep6NotificationTemplates, // 8 → Notif Templates (was 6)
            9:  GRMWizardStep9Users,                 // 9 → Users
            10: GRMWizardStep10Routing,              // 10 → Issue Routing
            11: GRMWizardStep11SLAs,                 // 11 → SLAs
            12: GRMWizardStep12IssueStatuses,        // 12 → Issue Statuses
            13: GRMWizardStep13Activate,             // 13 → Activate
        };
        return map[n] || null;
    }

    render_step_body() {
        const $body = $("#grm-step-body").empty();
        // Wipe any page-header primary/secondary actions from the previous step
        // so they never leak across steps. Steps that need actions render them
        // inside the form body (see grm-step7-footer in Step 3 for the pattern).
        if (this.page) {
            try { this.page.clear_primary_action && this.page.clear_primary_action(); } catch (e) { /* ignore */ }
            try { this.page.clear_secondary_action && this.page.clear_secondary_action(); } catch (e) { /* ignore */ }
        }
        const StepClass = this.step_class(this.current_step);
        if (!StepClass) {
            $body.html(`
                <div class="grm-wizard-placeholder">
                  <p class="text-muted">${__("Step component pending — see plan tasks 3.2-B / 3.2-C")}</p>
                  ${this.project
                      ? `<p>${__("Project")}: <strong>${frappe.utils.escape_html(this.project.name)}</strong></p>`
                      : `<p>${__("(no project loaded)")}</p>`}
                </div>
            `);
            this.step_instance = null;
            return;
        }
        this.step_instance = new StepClass($body, this.project, this);
    }

    update_footer() {
        $("#grm-prev").prop("disabled", this.current_step === 1);
        if (this.current_step === TOTAL_STEPS) {
            $("#grm-next").text(__("Activate Project"));
        } else {
            $("#grm-next").text(__("Continue"));
        }
        $("#grm-step-status").text(
            this.project ? `${this.current_step} / ${TOTAL_STEPS}` : __("Save Step 1 to begin"),
        );
    }

    async advance() {
        if (this.step_instance && typeof this.step_instance.save === "function") {
            const ok = await this.step_instance.save();
            if (!ok) return;
        }
        if (this.current_step < TOTAL_STEPS) {
            this.goto_step(this.current_step + 1);
        } else {
            await this.complete_wizard();
        }
    }

    goto_step(n) {
        if (n < 1 || n > TOTAL_STEPS) return;
        this.current_step = n;
        if (this.project && this.project.name) {
            frappe.db.set_value("GRM Project", this.project.name, "current_setup_step", n);
        }
        this.render_step();
    }

    async complete_wizard() {
        if (!this.project) {
            frappe.show_alert({ message: __("No project to activate"), indicator: "red" });
            return;
        }
        try {
            await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.activate_project",
                args: { project: this.project.name },
            });
            frappe.show_alert({ message: __("Project activated"), indicator: "green" });
            frappe.set_route("Workspaces", "Platform");
        } catch (e) {
            // frappe.call already shows the error; nothing to do
        }
    }
}

// ---------------------------------------------------------------------------
// Step 1 — Project Information
// ---------------------------------------------------------------------------
class GRMWizardStep1ProjectInfo {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }

    render() {
        const p = this.project || {};
        const code_disabled = this.project ? "disabled" : "";
        const code_warning = this.project
            ? `<small class="text-muted">${__("Project code cannot be changed after creation.")}</small>`
            : `<small class="text-warning">${__("Heads up: project code becomes the record name and cannot be changed after save.")}</small>`;

        this.$body.html(`
            <div class="grm-step1-form" style="max-width: 760px;">

              <p class="text-muted">${__("Tell us about your project. The information below will appear across the platform — citizen-facing portals, mobile apps, and notification templates.")}</p>

              <h4 class="mt-4">${__("Identity")}</h4>
              <p class="text-muted small">${__("These fields identify your project to staff and citizens.")}</p>
              <div class="form-group">
                <label class="control-label reqd">${__("Project Code")}</label>
                <input type="text" class="form-control" id="grm-f-project_code"
                       value="${frappe.utils.escape_html(p.project_code || "")}" ${code_disabled}>
                ${code_warning}
              </div>
              <div class="form-group">
                <label class="control-label reqd">${__("Project Title")}</label>
                <input type="text" class="form-control" id="grm-f-title"
                       value="${frappe.utils.escape_html(p.title || "")}">
              </div>
              <div class="form-group">
                <label class="control-label">${__("Description")}</label>
                <textarea class="form-control" id="grm-f-description" rows="3">${frappe.utils.escape_html(p.description || "")}</textarea>
              </div>

              <h4 class="mt-4">${__("Schedule")}</h4>
              <p class="text-muted small">${__("Optional. Used in dashboards and to gate intake outside the project window.")}</p>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Start Date")}</label>
                    <input type="date" class="form-control" id="grm-f-start_date"
                           value="${frappe.utils.escape_html(p.start_date || "")}">
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("End Date")}</label>
                    <input type="date" class="form-control" id="grm-f-end_date"
                           value="${frappe.utils.escape_html(p.end_date || "")}">
                  </div>
                </div>
              </div>

              <h4 class="mt-4">${__("Locale")}</h4>
              <p class="text-muted small">${__("How dates, numbers, and currency are formatted across the platform. Default Language drives label translations for citizens and staff.")}</p>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Country")}</label>
                    <div id="grm-f-country-wrap"></div>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Default Language")}</label>
                    <div id="grm-f-default_language-wrap"></div>
                  </div>
                </div>
              </div>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Number Format")}</label>
                    <select class="form-control" id="grm-f-number_format">
                      <option value="#,###.##" ${ (p.number_format || "#,###.##") === "#,###.##" ? "selected" : "" }>1,234.56 (en-US)</option>
                      <option value="#.###,##" ${ p.number_format === "#.###,##" ? "selected" : "" }>1.234,56 (de-DE)</option>
                      <option value="# ###.##"  ${ p.number_format === "# ###.##"  ? "selected" : "" }>1 234.56 (fr-FR)</option>
                      <option value="#,##,###.##" ${ p.number_format === "#,##,###.##" ? "selected" : "" }>1,23,456.78 (Indic)</option>
                    </select>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Date Format")}</label>
                    <select class="form-control" id="grm-f-date_format">
                      ${["yyyy-mm-dd","dd-mm-yyyy","mm-dd-yyyy","dd/mm/yyyy","mm/dd/yyyy"].map(fmt =>
                        `<option value="${fmt}" ${ (p.date_format || "yyyy-mm-dd") === fmt ? "selected" : "" }>${fmt}</option>`).join("")}
                    </select>
                  </div>
                </div>
              </div>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Currency")}</label>
                    <div id="grm-f-currency-wrap"></div>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Time Zone")}</label>
                    <input type="text" class="form-control" id="grm-f-time_zone"
                           placeholder="Africa/Kigali"
                           value="${frappe.utils.escape_html(p.time_zone || "")}">
                  </div>
                </div>
              </div>

              <h4 class="mt-4">${__("Operational Defaults")}</h4>
              <p class="text-muted small">${__("Project-wide behavioural defaults. You can adjust these later from project settings.")}</p>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Auto Escalation Days")}</label>
                    <input type="number" min="0" class="form-control" id="grm-f-auto_escalation_days"
                           value="${p.auto_escalation_days != null ? p.auto_escalation_days : 7}">
                    <small class="text-muted">${__("Days before an unresolved issue auto-escalates to the next tier.")}</small>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="checkbox">
                      <input type="checkbox" id="grm-f-enable_citizen_feedback" ${p.enable_citizen_feedback ? "checked" : ""}>
                      ${__("Enable Citizen Feedback")}
                    </label>
                    <small class="text-muted d-block">${__("Allow citizens to rate the resolution of their complaints.")}</small>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <label class="checkbox">
                  <input type="checkbox" id="grm-f-is_active" ${(p.is_active == null ? 1 : p.is_active) ? "checked" : ""}>
                  ${__("Is Active")}
                </label>
                <small class="text-muted d-block">${__("Inactive projects are hidden from intake screens but stay queryable in reports.")}</small>
              </div>
            </div>
        `);

        this._mount_link_controls(p);
    }

    _mount_link_controls(p) {
        const make = (parent_id, fieldname, doctype, value) => {
            const parent = this.$body.find(`#${parent_id}`)[0];
            if (!parent) return;
            try {
                const ctl = frappe.ui.form.make_control({
                    df: { fieldtype: "Link", fieldname, options: doctype, label: "" },
                    parent,
                    render_input: true,
                });
                ctl.set_value(value || "");
                this[`_ctl_${fieldname}`] = ctl;
            } catch (e) {
                // Fallback: plain text input if make_control fails (older Frappe versions)
                $(parent).html(`<input type="text" class="form-control" data-fb="${fieldname}" value="${frappe.utils.escape_html(value || "")}">`);
            }
        };
        make("grm-f-country-wrap",          "country",          "Country",  p.country);
        make("grm-f-default_language-wrap", "default_language", "Language", p.default_language || "en");
        make("grm-f-currency-wrap",         "currency",         "Currency", p.currency);
    }

    read_form() {
        const get = (id) => this.$body.find(`#${id}`).val();
        const checked = (id) => this.$body.find(`#${id}`).is(":checked") ? 1 : 0;
        const trim = (v) => (v == null ? "" : String(v).trim());
        const link_value = (fieldname, fallback_id) => {
            const ctl = this[`_ctl_${fieldname}`];
            if (ctl && typeof ctl.get_value === "function") return trim(ctl.get_value());
            return trim(this.$body.find(`[data-fb="${fieldname}"]`).val());
        };
        const auto_esc = parseInt(get("grm-f-auto_escalation_days"), 10);
        return {
            project_code: trim(get("grm-f-project_code")),
            title: trim(get("grm-f-title")),
            description: trim(get("grm-f-description")),
            start_date: trim(get("grm-f-start_date")) || null,
            end_date: trim(get("grm-f-end_date")) || null,
            country: link_value("country"),
            default_language: link_value("default_language") || "en",
            number_format: trim(get("grm-f-number_format")) || "#,###.##",
            date_format: trim(get("grm-f-date_format")) || "yyyy-mm-dd",
            currency: link_value("currency"),
            time_zone: trim(get("grm-f-time_zone")) || "",
            is_active: checked("grm-f-is_active"),
            enable_citizen_feedback: checked("grm-f-enable_citizen_feedback"),
            auto_escalation_days: isNaN(auto_esc) ? 7 : auto_esc,
        };
    }

    validate(values) {
        const errors = [];
        if (!values.project_code) errors.push(__("Project Code is required."));
        if (!values.title) errors.push(__("Title is required."));
        if (values.start_date && values.end_date && values.end_date < values.start_date) {
            errors.push(__("End Date must be on or after Start Date."));
        }
        if (values.auto_escalation_days < 0) {
            errors.push(__("Auto Escalation Days must be non-negative."));
        }
        return errors;
    }

    async save() {
        const values = this.read_form();
        const errors = this.validate(values);
        if (errors.length) {
            frappe.show_alert({ message: errors.join("\n"), indicator: "red" });
            return false;
        }
        try {
            if (!this.project) {
                const payload = Object.assign({ doctype: "GRM Project" }, values);
                // Strip nulls — frappe.db.insert doesn't like null for optional dates
                Object.keys(payload).forEach((k) => {
                    if (payload[k] === null) delete payload[k];
                });
                const doc = await frappe.db.insert(payload);
                this.wizard.project = doc;
                this.wizard.project_name = doc.name;
                this.project = doc;
                // Update URL so reload preserves state
                const url = new URL(window.location.href);
                url.searchParams.set("project", doc.name);
                window.history.replaceState({}, "", url.toString());
                frappe.show_alert({ message: __("Project created: {0}", [doc.name]), indicator: "green" });
            } else {
                // Update each changed field individually
                for (const [k, v] of Object.entries(values)) {
                    if (k === "project_code") continue; // immutable after creation
                    if (this.project[k] !== v) {
                        await frappe.db.set_value("GRM Project", this.project.name, k, v);
                        this.project[k] = v;
                    }
                }
            }
            return true;
        } catch (e) {
            // frappe surfaces the error already; nothing more to do
            return false;
        }
    }
}

// ---------------------------------------------------------------------------
// Step 2 — Administrative Levels & Regions (composite of Levels + Regions tabs)
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminUnits {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }

    render() {
        if (!this.project) {
            this.$body.html(`
                <div class="grm-wizard-placeholder">
                  <p class="text-muted">${__("Save Step 1 first to create the project.")}</p>
                </div>
            `);
            return;
        }
        this.$body.html(`
            <div class="grm-step2-admin">
              <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item"><a class="nav-link active" data-toggle="tab" href="#grm-tab-levels">${__("Levels")}</a></li>
                <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#grm-tab-regions">${__("Regions")}</a></li>
              </ul>
              <div class="tab-content pt-3">
                <div class="tab-pane fade show active" id="grm-tab-levels"></div>
                <div class="tab-pane fade" id="grm-tab-regions"></div>
              </div>
            </div>
        `);
        this.levels_inner = new GRMWizardStep2AdminLevelsInner(this.$body.find("#grm-tab-levels"), this.project, this.wizard);
        this.regions_inner = new GRMWizardStep2AdminRegionsInner(this.$body.find("#grm-tab-regions"), this.project, this.wizard);
    }

    async save() {
        if (!this.levels_inner) return true;
        const ok1 = await this.levels_inner.save();
        if (!ok1) return false;
        if (this.regions_inner) {
            return this.regions_inner.save();
        }
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 2 — Regions tab (bulk CSV upload of administrative regions)
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminRegionsInner {
    constructor($container, project, wizard) {
        this.$container = $container;
        this.project = project;
        this.wizard = wizard;
        this.parsed = null;
        this.render();
    }

    render() {
        this.$container.html(`
            <p class="text-muted">${__("Upload a CSV with one column per administrative level (e.g. Province, District, Sector). The highest level is auto-created from the project's country.")}</p>
            <div class="form-group">
              <label>${__("Highest level (single value, applied to all rows)")}</label>
              <input type="text" class="form-control" id="grm-rg-highest" placeholder="Country" value="Country">
            </div>
            <div class="form-group">
              <label>${__("CSV file")}</label>
              <input type="file" accept=".csv" id="grm-rg-file" class="form-control-file">
            </div>
            <button class="btn btn-default btn-sm" id="grm-rg-preview">${__("Preview")}</button>
            <button class="btn btn-primary btn-sm" id="grm-rg-import" disabled>${__("Import Regions")}</button>
            <div id="grm-rg-result" class="mt-3"></div>
        `);
        this.$container.find("#grm-rg-preview").on("click", () => this.preview());
        this.$container.find("#grm-rg-import").on("click",  () => this.do_import());
    }

    async _read_file() {
        const file = this.$container.find("#grm-rg-file")[0].files[0];
        if (!file) {
            frappe.show_alert({ message: __("Pick a CSV first."), indicator: "orange" });
            return null;
        }
        return await file.text();
    }

    async preview() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.parse_admin_regions_csv",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        this.parsed = r.message;
        this._render_preview();
    }

    _render_preview() {
        const p = this.parsed || {};
        const $r = this.$container.find("#grm-rg-result").empty();
        if (p.errors && p.errors.length) {
            $r.append(`<div class="alert alert-danger"><strong>${__("Errors")}:</strong><ul>${p.errors.map(e => `<li>${frappe.utils.escape_html(e)}</li>`).join("")}</ul></div>`);
            this.$container.find("#grm-rg-import").prop("disabled", true);
            return;
        }
        const cols = p.level_columns || [];
        $r.append(`<div class="alert alert-info">${__("Detected {0} rows across levels: {1}", [p.total_rows || 0, cols.join(" → ")])}</div>`);
        const $tbl = $(`<div class="form-grid"><table class="table table-borderless"><thead><tr>${cols.map(c => `<th>${frappe.utils.escape_html(c)}</th>`).join("")}</tr></thead><tbody></tbody></table></div>`);
        (p.preview || []).forEach(row => {
            $tbl.find("tbody").append(`<tr>${cols.map(c => `<td>${frappe.utils.escape_html(row[c] || "")}</td>`).join("")}</tr>`);
        });
        $r.append($tbl);
        this.$container.find("#grm-rg-import").prop("disabled", false);
    }

    async do_import() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_insert_admin_regions",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        const m = r.message || {};
        const $r = this.$container.find("#grm-rg-result").empty();
        $r.append(`<div class="alert alert-success">${__("Imported {0} regions ({1} updated). {2} errors.", [m.created || 0, m.updated || 0, (m.errors || []).length])}</div>`);
        if (m.errors && m.errors.length) {
            $r.append(`<ul>${m.errors.map(e => `<li class="text-danger">${frappe.utils.escape_html(e)}</li>`).join("")}</ul>`);
        }
    }

    async save() {
        // The Regions tab does not gate step navigation — bulk upload is optional.
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 9 — Users (bulk creation: CSV upload + auto-generate per region + activation codes)
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Step 9 — Users (Phase C composition + list panel)
//
// Outer class `GRMWizardStep9Users` is a thin composition that mounts:
//   - GRMWizardStep9UsersList  (Phase C)
//   - GRMWizardStep9UserAdd    (Phase D)
//   - GRMWizardStep9UserImport (Phase E)
//
// The list panel is doctype-driven: row data comes from the
// `list_project_users` endpoint and pill metadata is rendered inline.
// Pill clicks open a small popover anchored to the pill (Awesomplete-
// backed Frappe Link control) that calls `update_assignment_field` and
// refreshes the affected row in place.
// ---------------------------------------------------------------------------

const GRM_STEP9_PAGE_SIZE = 25;

class GRMWizardStep9UsersList {
    constructor($body, project, wizard, on_first_load) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.on_first_load = on_first_load || null;
        this._first_load_fired = false;
        this.search = "";
        this.filter_level = "";
        this.filter_role = "";
        this.filter_status = "";
        this.start = 0;
        this.limit = GRM_STEP9_PAGE_SIZE;
        this.rows = [];
        this.total = 0;
        this.summary = { active: 0, pending: 0, draft: 0, unmapped: 0 };
        this.selected = new Set();
        this.project_levels = [];
        this.project_roles = [];
        this._popover = null;
        this._search_timer = null;
        this._init();
    }

    async _init() {
        this.$body.html(`
            <div class="grm-step9-users-list">
              <div class="grm-step9-list-header"></div>
              <div class="grm-step9-list-controls"></div>
              <div class="grm-step9-list-table"></div>
            </div>
        `);
        await this._load_meta();
        await this.refresh();
        // Notify the composition class once, after the first load — so it
        // can flip the Add-panel toggle to "bulk" if the project has no
        // users yet (E.6 empty-state default).
        if (!this._first_load_fired) {
            this._first_load_fired = true;
            if (this.on_first_load) {
                try { this.on_first_load(this.total); } catch (e) { /* non-fatal */ }
            }
        }
    }

    async _load_meta() {
        // Level types + roles drive the filter dropdowns + role-pill picker.
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.get_assignment_field_meta",
                args: { project: this.project.name },
            });
            const m = r.message || {};
            this.project_levels = m.project_levels || [];
            this.project_roles = m.project_roles || [];
        } catch (e) {
            // Non-fatal: filter dropdowns will just be sparse.
            this.project_levels = [];
            this.project_roles = [];
        }
    }

    async refresh() {
        const $hdr = this.$body.find(".grm-step9-list-header");
        const $ctl = this.$body.find(".grm-step9-list-controls");
        const $tbl = this.$body.find(".grm-step9-list-table");
        $tbl.html(`<p class="text-muted">${__("Loading…")}</p>`);
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.list_project_users",
                args: {
                    project: this.project.name,
                    search: this.search || null,
                    level_type: this.filter_level || null,
                    role: this.filter_role || null,
                    status: this.filter_status || null,
                    start: this.start,
                    limit: this.limit,
                },
            });
            const m = r.message || {};
            this.rows = m.rows || [];
            this.total = m.total || 0;
            this.summary = m.summary || this.summary;
        } catch (e) {
            $tbl.html(`<div class="alert alert-danger">${__("Could not load users.")}</div>`);
            return;
        }

        this._render_header($hdr);
        if (this.total === 0 && !this.search && !this.filter_level && !this.filter_role && !this.filter_status) {
            // Empty state: drop search/filter row entirely; the Add panel
            // below this one (Phase D) is where the user starts.
            $ctl.empty();
            $tbl.html(`
              <div class="grm-step9-empty">
                <p class="text-muted">${__("No users assigned to this project yet. Add users below.")}</p>
              </div>
            `);
            return;
        }
        this._render_controls($ctl);
        this._render_table($tbl);
    }

    _render_header($hdr) {
        const total_label = this.total === 1
            ? __("1 assigned")
            : __("{0} assigned", [this.total]);
        const summary_bits = [];
        if (this.summary.active)  summary_bits.push(__("{0} active", [this.summary.active]));
        if (this.summary.pending) summary_bits.push(__("{0} pending", [this.summary.pending]));
        if (this.summary.draft)   summary_bits.push(__("{0} draft", [this.summary.draft]));
        if (this.summary.unmapped) summary_bits.push(__("{0} unmapped", [this.summary.unmapped]));
        const summary_html = summary_bits.length
            ? ` &middot; <span class="text-muted">${summary_bits.join(" &middot; ")}</span>`
            : "";
        $hdr.html(`
          <h5 class="grm-step9-list-title">
            ${__("Project users")}
            <span class="text-muted">&middot; ${total_label}${summary_html}</span>
          </h5>
        `);
    }

    _render_controls($ctl) {
        const level_options = [`<option value="">${__("All levels")}</option>`]
            .concat((this.project_levels || []).map((l) =>
                `<option value="${frappe.utils.escape_html(l.name)}"${l.name === this.filter_level ? " selected" : ""}>${frappe.utils.escape_html(l.level_name || l.name)}</option>`
            )).join("");
        const role_options = [`<option value="">${__("All roles")}</option>`]
            .concat((this.project_roles || []).map((r) =>
                `<option value="${frappe.utils.escape_html(r.name)}"${r.name === this.filter_role ? " selected" : ""}>${frappe.utils.escape_html(r.role_name || r.name)}</option>`
            )).join("");
        const status_values = ["Draft", "Pending Activation", "Activated", "Suspended", "Expired"];
        const status_options = [`<option value="">${__("All statuses")}</option>`]
            .concat(status_values.map((s) =>
                `<option value="${s}"${s === this.filter_status ? " selected" : ""}>${__(s)}</option>`
            )).join("");
        const page_total = Math.max(1, Math.ceil(this.total / this.limit));
        const page_idx = Math.floor(this.start / this.limit) + 1;
        const range_from = this.total === 0 ? 0 : this.start + 1;
        const range_to = Math.min(this.start + this.rows.length, this.total);
        $ctl.html(`
          <div class="grm-step9-list-controls-row">
            <input type="search" class="form-control form-control-sm grm-step9-search"
                   placeholder="${__("Search name / email / position")}"
                   value="${frappe.utils.escape_html(this.search)}">
            <select class="form-control form-control-sm grm-step9-level-filter">${level_options}</select>
            <select class="form-control form-control-sm grm-step9-role-filter">${role_options}</select>
            <select class="form-control form-control-sm grm-step9-status-filter">${status_options}</select>
            <div class="grm-step9-pager">
              <button class="btn btn-default btn-xs grm-step9-prev" ${this.start === 0 ? "disabled" : ""}>${__("Prev")}</button>
              <span class="grm-step9-pager-label">${__("{0}-{1} of {2}", [range_from, range_to, this.total])}</span>
              <button class="btn btn-default btn-xs grm-step9-next" ${page_idx >= page_total ? "disabled" : ""}>${__("Next")}</button>
            </div>
          </div>
          ${grm_render_bulk_toolbar("step9_users")}
          <div class="grm-step9-bulk-extras" hidden>
            <button class="btn btn-xs btn-default grm-step9-bulk-role">${__("Change role")}</button>
            <button class="btn btn-xs btn-default grm-step9-bulk-status">${__("Change status")}</button>
            <button class="btn btn-xs btn-default grm-step9-bulk-deactivate">${__("Deactivate")}</button>
          </div>
        `);

        // Wire search + filter handlers — search is debounced.
        $ctl.find(".grm-step9-search").on("input", (ev) => {
            const v = $(ev.currentTarget).val();
            if (this._search_timer) clearTimeout(this._search_timer);
            this._search_timer = setTimeout(() => {
                this.search = v;
                this.start = 0;
                this.refresh();
            }, 250);
        });
        $ctl.find(".grm-step9-level-filter").on("change", (ev) => {
            this.filter_level = $(ev.currentTarget).val();
            this.start = 0;
            this.refresh();
        });
        $ctl.find(".grm-step9-role-filter").on("change", (ev) => {
            this.filter_role = $(ev.currentTarget).val();
            this.start = 0;
            this.refresh();
        });
        $ctl.find(".grm-step9-status-filter").on("change", (ev) => {
            this.filter_status = $(ev.currentTarget).val();
            this.start = 0;
            this.refresh();
        });
        $ctl.find(".grm-step9-prev").on("click", () => {
            if (this.start === 0) return;
            this.start = Math.max(0, this.start - this.limit);
            this.refresh();
        });
        $ctl.find(".grm-step9-next").on("click", () => {
            if (this.start + this.limit >= this.total) return;
            this.start += this.limit;
            this.refresh();
        });

        // Bulk extras (visible only when ≥1 selected — toggled by
        // grm_wire_bulk_table's refresh callback below).
        $ctl.find(".grm-step9-bulk-role").on("click", () => this._bulk_change("role"));
        $ctl.find(".grm-step9-bulk-status").on("click", () => this._bulk_change("activation_status"));
        $ctl.find(".grm-step9-bulk-deactivate").on("click", () => this._bulk_deactivate());
    }

    _render_table($tbl) {
        if (!this.rows.length) {
            $tbl.html(`<p class="text-muted">${__("No users match the current filters.")}</p>`);
            return;
        }
        const head = `
          <thead>
            <tr>
              <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all"></th>
              <th>${__("Name / Email")}</th>
              <th>${__("Position")}</th>
              <th>${__("Role")}</th>
              <th>${__("Level")}</th>
              <th>${__("Region")}</th>
              <th>${__("Status")}</th>
            </tr>
          </thead>
        `;
        const body_rows = this.rows.map((r) => this._render_row(r)).join("");
        $tbl.html(`
          <table class="table table-borderless grm-users-table">${head}<tbody>${body_rows}</tbody></table>
        `);
        // Wire pill clicks
        $tbl.find(".grm-pill[data-editable='1']").on("click", (ev) => {
            ev.preventDefault();
            const $pill = $(ev.currentTarget);
            this._open_pill_popover($pill);
        });
        // Wire bulk-table selection (toolbar + delete handler).
        const row_names = this.rows.map((r) => r.name);
        grm_wire_bulk_table(this.$body, {
            selected: this.selected,
            row_names,
            key: "step9_users",
            singular: __("user"),
            plural: __("users"),
            confirm_msg: (n) => n === 1
                ? __("Remove the selected user from this project?")
                : __("Remove {0} selected users from this project?", [n]),
            delete_one: async (name) => {
                await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_remove_assignments",
                    args: { names: JSON.stringify([name]) },
                });
            },
            on_done: () => this.refresh(),
        });
        // Toggle the bulk-extras row in lock-step with the toolbar.
        const $extras = this.$body.find(".grm-step9-bulk-extras");
        const $bar = this.$body.find(`.grm-bulk-actions[data-grm-bulk-for='step9_users']`);
        const sync_extras = () => $extras.attr("hidden", $bar.attr("hidden") || null);
        // Hook into the same change events the toolbar listens on.
        this.$body.on("change.grm-step9-extras", ".grm-bulk-row-check, .grm-bulk-all", () => setTimeout(sync_extras, 0));
        this.$body.on("click.grm-step9-extras", ".grm-bulk-clear", () => setTimeout(sync_extras, 0));
        sync_extras();
    }

    _render_row(r) {
        const name_email = `
          <div class="grm-step9-name">${frappe.utils.escape_html(r.user_full_name || r.user || "")}</div>
          <div class="grm-step9-email text-muted">${frappe.utils.escape_html(r.user_email || "")}</div>
        `;
        const position = frappe.utils.escape_html(r.position_title || "");
        const role_pill = this._pill({
            field: "role",
            value: r.role || "",
            label: r.role_name || r.role || "",
            kind: "role",
            assignment: r.name,
        });
        // Level pill: read-only — derived from the region's administrative_level.
        const level_pill = this._pill({
            field: "level",
            value: r.administrative_level || "",
            label: r.level_name || "",
            kind: "level",
            assignment: r.name,
            readonly: true,
        });
        const region_pill = this._pill({
            field: "administrative_region",
            value: r.administrative_region || "",
            label: r.region_name || "",
            kind: "region",
            assignment: r.name,
        });
        const status_pill = this._pill({
            field: "activation_status",
            value: r.activation_status || "Draft",
            label: r.activation_status || "Draft",
            kind: `status-${(r.activation_status || "draft").toLowerCase().replace(/\s+/g, "-")}`,
            assignment: r.name,
        });
        return `
          <tr data-name="${frappe.utils.escape_html(r.name)}">
            <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
            <td>${name_email}</td>
            <td>${position}</td>
            <td>${role_pill}</td>
            <td>${level_pill}</td>
            <td>${region_pill}</td>
            <td>${status_pill}</td>
          </tr>
        `;
    }

    _pill({ field, value, label, kind, assignment, readonly }) {
        const empty = !value && !label;
        const disp = empty ? __("(unset)") : label;
        const editable = readonly ? "" : `data-editable="1"`;
        const empty_attr = empty ? `data-empty="true"` : "";
        const ro_class = readonly ? " grm-pill-readonly" : "";
        return `
          <button type="button"
                  class="grm-pill grm-pill-${kind}${ro_class}"
                  ${editable}
                  ${empty_attr}
                  data-field="${frappe.utils.escape_html(field)}"
                  data-value="${frappe.utils.escape_html(value || "")}"
                  data-assignment="${frappe.utils.escape_html(assignment || "")}">
            ${frappe.utils.escape_html(disp)}
          </button>
        `;
    }

    // -- Popover ----------------------------------------------------------

    _close_popover() {
        if (this._popover) {
            try { this._popover.remove(); } catch (e) { /* ignore */ }
            this._popover = null;
        }
        $(document).off(".grm-step9-pop");
    }

    _open_pill_popover($pill) {
        this._close_popover();
        const field = $pill.data("field");
        const assignment = $pill.data("assignment");
        const current_value = String($pill.data("value") || "");
        const rect = $pill[0].getBoundingClientRect();
        const $pop = $(`<div class="grm-pill-popover"></div>`).appendTo("body");
        $pop.css({
            position: "absolute",
            top: rect.bottom + window.scrollY + 4,
            left: rect.left + window.scrollX,
            "z-index": 1050,
        });
        this._popover = $pop;

        // Close on outside click / escape.
        setTimeout(() => {
            $(document).on("click.grm-step9-pop", (ev) => {
                if ($pop[0].contains(ev.target) || $pill[0].contains(ev.target)) return;
                this._close_popover();
            });
            $(document).on("keydown.grm-step9-pop", (ev) => {
                if (ev.key === "Escape") this._close_popover();
            });
        }, 0);

        if (field === "activation_status") {
            // Native <select> for the small fixed option set.
            const opts = ["Draft", "Pending Activation", "Activated", "Suspended"];
            $pop.html(`
              <label class="grm-pill-pop-label">${__("Status")}</label>
              <select class="form-control form-control-sm grm-step9-pop-select">
                ${opts.map((o) => `<option value="${o}"${o === current_value ? " selected" : ""}>${__(o)}</option>`).join("")}
              </select>
            `);
            $pop.find("select").on("change", async (ev) => {
                const v = $(ev.currentTarget).val();
                await this._save_field(assignment, field, v);
            });
            return;
        }

        // Link-control popover for role / region / department.
        const ctl_meta = this._link_control_meta(field);
        if (!ctl_meta) {
            this._close_popover();
            return;
        }
        $pop.html(`<label class="grm-pill-pop-label">${ctl_meta.label}</label><div class="grm-step9-pop-ctrl"></div>`);
        const parent = $pop.find(".grm-step9-pop-ctrl")[0];
        let ctl;
        try {
            ctl = frappe.ui.form.make_control({
                df: {
                    fieldtype: "Link",
                    fieldname: field,
                    label: "",
                    options: ctl_meta.doctype,
                    get_query: ctl_meta.get_query,
                },
                parent,
                render_input: true,
            });
            ctl.set_value(current_value || "");
            ctl.$input && ctl.$input.focus();
        } catch (e) {
            // Fallback: plain text input.
            $(parent).html(`<input type="text" class="form-control form-control-sm" value="${frappe.utils.escape_html(current_value)}">`);
        }
        $pop.on("change", "input, select", async (ev) => {
            // Awesomplete fires a "change" with the selected value in the input.
            let v = "";
            if (ctl && typeof ctl.get_value === "function") {
                v = ctl.get_value();
            } else {
                v = $(ev.currentTarget).val();
            }
            await this._save_field(assignment, field, v);
        });
    }

    _link_control_meta(field) {
        const project = this.project.name;
        if (field === "role") {
            return {
                label: __("Role"),
                doctype: "GRM Project Role",
                get_query: () => ({ filters: { project, is_active: 1 } }),
            };
        }
        if (field === "administrative_region") {
            return {
                label: __("Administrative Region"),
                doctype: "GRM Administrative Region",
                get_query: () => ({ filters: { project } }),
            };
        }
        if (field === "department") {
            return {
                label: __("Department"),
                doctype: "GRM Issue Department",
                get_query: () => ({ filters: { project } }),
            };
        }
        return null;
    }

    async _save_field(assignment, field, value) {
        try {
            await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.update_assignment_field",
                args: { name: assignment, fieldname: field, value: value || "" },
            });
            frappe.show_alert({ message: __("Updated."), indicator: "green" });
            this._close_popover();
            // Re-fetch the current page so the row reflects new joined fields.
            await this.refresh();
        } catch (e) {
            // Frappe surfaces the error toast already.
        }
    }

    // -- Bulk actions -----------------------------------------------------

    async _bulk_change(field) {
        const names = [...this.selected];
        if (!names.length) return;
        const meta = this._link_control_meta(field);
        if (field === "activation_status") {
            const value = await this._prompt_select(
                __("Change status"),
                ["Draft", "Pending Activation", "Activated", "Suspended"],
            );
            if (!value) return;
            await this._do_bulk(names, field, value);
            return;
        }
        if (!meta) return;
        const value = await this._prompt_link(meta);
        if (!value) return;
        await this._do_bulk(names, field, value);
    }

    async _bulk_deactivate() {
        const names = [...this.selected];
        if (!names.length) return;
        await this._do_bulk(names, "is_active", 0);
    }

    async _do_bulk(names, field, value) {
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_update_assignments",
                args: { names: JSON.stringify(names), fieldname: field, value },
            });
            const m = r.message || {};
            const errs = m.errors || [];
            if (errs.length) {
                frappe.show_alert({
                    message: __("Updated {0}; {1} failed.", [m.updated || 0, errs.length]),
                    indicator: "orange",
                });
            } else {
                frappe.show_alert({
                    message: __("Updated {0} users.", [m.updated || 0]),
                    indicator: "green",
                });
            }
            this.selected.clear();
            await this.refresh();
        } catch (e) {
            // Frappe surfaces the error already.
        }
    }

    _prompt_select(title, options) {
        return new Promise((resolve) => {
            const d = new frappe.ui.Dialog({
                title,
                fields: [{
                    fieldname: "value",
                    fieldtype: "Select",
                    label: __("Value"),
                    options: options.join("\n"),
                    reqd: 1,
                }],
                primary_action_label: __("Apply"),
                primary_action: (values) => {
                    d.hide();
                    resolve(values.value);
                },
            });
            d.onhide = () => resolve(null);
            d.show();
        });
    }

    _prompt_link(meta) {
        return new Promise((resolve) => {
            const d = new frappe.ui.Dialog({
                title: meta.label,
                fields: [{
                    fieldname: "value",
                    fieldtype: "Link",
                    label: meta.label,
                    options: meta.doctype,
                    get_query: meta.get_query,
                    reqd: 1,
                }],
                primary_action_label: __("Apply"),
                primary_action: (values) => {
                    d.hide();
                    resolve(values.value);
                },
            });
            d.onhide = () => resolve(null);
            d.show();
        });
    }
}


// ---------------------------------------------------------------------------
// Step 9 (Phase D) — Single-add form
//
// `GRMWizardStep9UserAdd` is the "Single user" face of the Add panel below
// the users list. It's *doctype-driven*: required vs optional pills come
// from the same `get_assignment_field_meta` payload the bulk-import mapper
// uses (plan §Engineering Conventions clause 2). The region picker is a
// cascade — one Link control per project level (highest first), each
// filtered to its parent's children. When the operator picks a Project
// Role with `admin_level` set, the cascade levels below that admin_level
// are read-only and cleared (plan §D.2).
// ---------------------------------------------------------------------------

class GRMWizardStep9UserAdd {
    constructor(opts) {
        this.project = opts.project;          // GRM Project doc-ish ({name, ...})
        this.$mount = opts.$mount;            // jQuery wrapper for the slot
        this.on_added = opts.on_added || (() => {}); // callback when a row is created
        this.field_meta = null;               // populated on first render()
        this.controls = {};                   // user / role / department / position_title
        this.region_cascade_controls = [];    // one Link control per level (high→low)
    }

    async render() {
        // Skeleton first so spinners are visible while we fetch meta.
        this.$mount.html(`
            <div class="grm-step9-add-form">
              <h5>${__("Add a single user")}</h5>
              <div class="grm-step9-add-loading text-muted">${__("Loading…")}</div>
            </div>
        `);

        if (!this.field_meta) {
            try {
                const r = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.get_assignment_field_meta",
                    args: { project: this.project.name },
                });
                this.field_meta = r.message || {};
            } catch (e) {
                this.$mount.find(".grm-step9-add-loading").replaceWith(
                    `<div class="alert alert-danger">${__("Could not load form metadata.")}</div>`
                );
                return;
            }
        }

        // Replace skeleton with the real form layout. The slots match the
        // controls we mount below in `build_controls`.
        this.$mount.find(".grm-step9-add-form").html(`
            <h5>${__("Add a single user")}</h5>
            <div class="row">
              <div class="col-md-6"><div class="form-group" data-field="user"></div></div>
              <div class="col-md-6"><div class="form-group" data-field="role"></div></div>
            </div>
            <div class="row">
              <div class="col-md-6"><div class="form-group" data-field="administrative_region"></div></div>
              <div class="col-md-6"><div class="form-group" data-field="department"></div></div>
            </div>
            <div class="row">
              <div class="col-md-12"><div class="form-group" data-field="position_title"></div></div>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-primary grm-step9-add-submit">${__("Add user")}</button>
              <button type="button" class="btn btn-default grm-step9-add-clear">${__("Clear")}</button>
            </div>
        `);

        this.controls = {};
        this.region_cascade_controls = [];
        this.build_controls();
        this.wire_actions();
    }

    /** Look up `fieldname` in `assignment_fields[]` and report `reqd`. */
    _is_assignment_required(fieldname) {
        const f = (this.field_meta.assignment_fields || []).find(
            (x) => x.fieldname === fieldname
        );
        return !!(f && f.reqd);
    }

    /** Inject a red asterisk after the label text iff the field is required. */
    _label_with_reqd(label, required) {
        return required
            ? `${label} <span class="text-danger">*</span>`
            : label;
    }

    build_controls() {
        // user — Link to User. The doctype marks `user` as reqd, but we
        // read from the meta payload to avoid hard-coding the flag.
        const user_required = this._is_assignment_required("user");
        this.controls.user = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link",
                options: "User",
                label: this._label_with_reqd(__("User"), user_required),
                reqd: user_required ? 1 : 0,
                placeholder: __("Search by email or name"),
            },
            parent: this.$mount.find('[data-field="user"]')[0],
            render_input: true,
        });

        // role — Link to GRM Project Role, filtered to the active roles
        // for THIS project. Picking a role triggers the region cascade
        // reset below (`on_role_change`).
        const role_required = this._is_assignment_required("role");
        this.controls.role = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link",
                options: "GRM Project Role",
                label: this._label_with_reqd(__("Role"), role_required),
                reqd: role_required ? 1 : 0,
                get_query: () => ({
                    filters: { project: this.project.name, is_active: 1 },
                }),
                onchange: () => this.on_role_change(),
            },
            parent: this.$mount.find('[data-field="role"]')[0],
            render_input: true,
        });

        // administrative_region — D.2 cascading picker (one Link per level).
        this.build_region_cascade();

        // department — Link to GRM Issue Department scoped to this project.
        // The doctype validator additionally checks the project link table,
        // but the simple `project` filter is good enough for the picker.
        this.controls.department = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link",
                options: "GRM Issue Department",
                label: __("Department"),
                get_query: () => ({ filters: { project: this.project.name } }),
            },
            parent: this.$mount.find('[data-field="department"]')[0],
            render_input: true,
        });

        // position_title — free-text Data field.
        this.controls.position_title = frappe.ui.form.make_control({
            df: { fieldtype: "Data", label: __("Position") },
            parent: this.$mount.find('[data-field="position_title"]')[0],
            render_input: true,
        });
    }

    build_region_cascade() {
        const $parent = this.$mount.find('[data-field="administrative_region"]');
        const region_required = this._is_assignment_required("administrative_region");
        $parent.html(`
            <label>${this._label_with_reqd(__("Region"), region_required)}</label>
            <div class="grm-region-cascade"></div>
        `);

        const $cascade = $parent.find(".grm-region-cascade");
        this.region_cascade_controls = [];

        // Levels arrive ordered by `level_order ASC` from the server, i.e.
        // highest level (smallest number, e.g. Province=1) first. We mount
        // one Link control per level; each filters to children of the
        // level above.
        const levels = this.field_meta.project_levels || [];
        levels.forEach((level, idx) => {
            const $slot = $('<div class="grm-region-cascade-slot"></div>').appendTo($cascade);
            const ctrl = frappe.ui.form.make_control({
                df: {
                    fieldtype: "Link",
                    options: "GRM Administrative Region",
                    label: level.level_name || level.name,
                    placeholder: __("Pick {0}", [level.level_name || level.name]),
                    get_query: () => {
                        const filters = {
                            project: this.project.name,
                            administrative_level: level.name,
                        };
                        if (idx > 0) {
                            const parent_value = this.region_cascade_controls[idx - 1]
                                && this.region_cascade_controls[idx - 1].get_value();
                            if (parent_value) {
                                filters.parent_region = parent_value;
                            } else {
                                // No parent picked yet — return nothing so
                                // the dropdown reads "no matches" rather
                                // than offering every region in the project.
                                return { filters: { name: ["=", "__none__"] } };
                            }
                        }
                        return { filters };
                    },
                    onchange: () => {
                        // Picking a value at level `idx` invalidates any
                        // selection at deeper levels — clear them so the
                        // submit value reflects the deepest *consistent*
                        // ancestry.
                        for (let j = idx + 1; j < this.region_cascade_controls.length; j++) {
                            const lower = this.region_cascade_controls[j];
                            if (lower && lower.set_value) lower.set_value("");
                        }
                    },
                },
                parent: $slot[0],
                render_input: true,
            });
            this.region_cascade_controls.push(ctrl);
        });
    }

    /**
     * Walk the cascade from the deepest level back to the highest and
     * return the first non-empty value — that's the most-specific region
     * the operator has picked.
     */
    get_selected_region() {
        for (let i = this.region_cascade_controls.length - 1; i >= 0; i--) {
            const v = this.region_cascade_controls[i] && this.region_cascade_controls[i].get_value();
            if (v) return v;
        }
        return null;
    }

    on_role_change() {
        const role_id = this.controls.role && this.controls.role.get_value();
        if (!role_id) {
            // No role picked → no cascade restriction.
            this.set_cascade_min_level(null);
            return;
        }
        // Avoid a get_value() round-trip: the role meta we already loaded
        // includes `admin_level` for every active project role.
        const meta = (this.field_meta.project_roles || []).find((r) => r.name === role_id);
        if (meta) {
            this.set_cascade_min_level(meta.admin_level || null);
            return;
        }
        // Fall back to the DB if the role isn't in the cached meta (rare —
        // happens only if a role was added between page load and click).
        frappe.db.get_value("GRM Project Role", role_id, "admin_level").then((r) => {
            const role_admin_level = (r && r.message && r.message.admin_level) || null;
            this.set_cascade_min_level(role_admin_level);
        });
    }

    /**
     * Disable cascade slots strictly *below* the role's `admin_level`.
     * The role's `admin_level` is the lowest level the role can be
     * assigned at, so picking deeper would violate the server's
     * `create_assignment` invariant — block it in the UI to match.
     */
    set_cascade_min_level(role_admin_level) {
        const levels = this.field_meta.project_levels || [];
        if (!role_admin_level) {
            // No restriction — every slot is editable.
            this.region_cascade_controls.forEach((ctrl) => {
                if (ctrl && ctrl.df) ctrl.df.read_only = 0;
                if (ctrl && ctrl.refresh) ctrl.refresh();
            });
            return;
        }
        const role_level_idx = levels.findIndex((l) => l.name === role_admin_level);
        if (role_level_idx === -1) return;

        this.region_cascade_controls.forEach((ctrl, idx) => {
            if (!ctrl || !ctrl.df) return;
            const should_disable = idx > role_level_idx;
            ctrl.df.read_only = should_disable ? 1 : 0;
            if (should_disable && ctrl.set_value) ctrl.set_value("");
            if (ctrl.refresh) ctrl.refresh();
        });
    }

    wire_actions() {
        this.$mount.find(".grm-step9-add-submit").on("click", () => this.submit());
        this.$mount.find(".grm-step9-add-clear").on("click", () => this.clear_form());
    }

    async submit() {
        const user = this.controls.user && this.controls.user.get_value();
        const role = this.controls.role && this.controls.role.get_value();
        if (!user || !role) {
            frappe.msgprint({
                title: __("Required fields missing"),
                message: __("User and Role are required."),
                indicator: "red",
            });
            return;
        }
        const region = this.get_selected_region();
        const department = this.controls.department && this.controls.department.get_value();
        const position_title = this.controls.position_title && this.controls.position_title.get_value();

        frappe.dom.freeze(__("Adding user…"));
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.create_assignment",
                args: {
                    project: this.project.name,
                    user,
                    role,
                    administrative_region: region,
                    department: department || null,
                    position_title: position_title || null,
                },
            });
            frappe.show_alert({ message: __("User added."), indicator: "green" });
            this.clear_form();
            this.on_added(r.message);
        } catch (e) {
            // frappe.call already surfaces the error toast; nothing to do.
        } finally {
            frappe.dom.unfreeze();
        }
    }

    clear_form() {
        // `set_value("")` on a Link clears it; on Data writes empty.
        Object.values(this.controls).forEach((c) => {
            if (c && c.set_value) c.set_value("");
        });
        (this.region_cascade_controls || []).forEach((c) => {
            if (c && c.set_value) c.set_value("");
        });
    }
}


// ---------------------------------------------------------------------------
// Phase E — `GRMWizardStep9UserImport` 4-stage bulk-import flow
// ---------------------------------------------------------------------------
// Wraps the Phase B Data Import endpoints (`download_user_template`,
// `auto_detect_user_import_mapping`, `prepare_user_import`,
// `start_user_import`, `poll_user_import`) with a stage-driven UI:
//   1. template — pick CSV or XLSX template download
//   2. upload   — drag-drop / browse a filled-in file
//   3. mapping  — confirm/edit the column → target mapping
//   4. preview  — review resolved rows + start import + poll progress
// On import completion the `on_completed` callback refreshes the list.
// ---------------------------------------------------------------------------

const GRM_STEP9_BULK_POLL_MS = 1500;
const GRM_STEP9_BULK_PREVIEW_LIMIT = 50;
const GRM_STEP9_BULK_MAX_FILE_MB = 10;

class GRMWizardStep9UserImport {
    constructor(opts) {
        this.project = opts.project;
        this.$mount = opts.$mount;
        this.on_completed = opts.on_completed || (() => {});
        this.stage = "template"; // template | upload | mapping | preview
        this.uploaded_file_url = null;
        this.uploaded_file_name = "";
        this.headers = [];
        this.mapping = {}; // {header: {target, level_type, ...}}
        this.project_meta = null;
        this.validation = null;
        this.preview_rows = [];
        this.total_rows = 0;
        this.preview = null;        // result of `prepare_user_import`
        this.regions_to_create = [];
        this.data_import_name = null;
        this.poll_handle = null;
    }

    render() {
        // Fresh skeleton — re-rendered if user navigates away from this
        // panel and back. Per-stage state is preserved on `this`.
        this.$mount.html(`
            <div class="grm-step9-add-form grm-step9-bulk">
              <h5>${__("Bulk import users")}</h5>
              <div class="grm-step9-bulk-stages">
                <div class="grm-stage" data-stage="template">${__("1. Template")}</div>
                <div class="grm-stage" data-stage="upload">${__("2. Upload")}</div>
                <div class="grm-stage" data-stage="mapping">${__("3. Map columns")}</div>
                <div class="grm-stage" data-stage="preview">${__("4. Preview & Import")}</div>
              </div>
              <div class="grm-step9-bulk-content"></div>
            </div>
        `);
        this._refresh_stage_pills();
        this._render_stage();
    }

    _refresh_stage_pills() {
        const $stages = this.$mount.find(".grm-stage");
        $stages.removeClass("active done");
        const order = ["template", "upload", "mapping", "preview"];
        const cur_idx = order.indexOf(this.stage);
        $stages.each((i, el) => {
            const $el = $(el);
            const stage = $el.data("stage");
            const idx = order.indexOf(stage);
            if (idx === cur_idx) $el.addClass("active");
            else if (idx < cur_idx) $el.addClass("done");
        });
    }

    set_stage(stage) {
        // Cancel any pending poll when leaving the preview stage.
        if (this.stage === "preview" && stage !== "preview" && this.poll_handle) {
            clearTimeout(this.poll_handle);
            this.poll_handle = null;
        }
        this.stage = stage;
        this._refresh_stage_pills();
        this._render_stage();
    }

    _render_stage() {
        const $content = this.$mount.find(".grm-step9-bulk-content").empty();
        switch (this.stage) {
            case "template": this._render_template_stage($content); break;
            case "upload":   this._render_upload_stage($content); break;
            case "mapping":  this._render_mapping_stage($content); break;
            case "preview":  this._render_preview_stage($content); break;
        }
    }

    // --- Stage 1: template ---------------------------------------------------
    _render_template_stage($content) {
        $content.html(`
            <p>${__("Download a project-tailored template, fill it in with your users, then upload below.")}</p>
            <p class="text-muted small">${__("Columns include your project's admin levels (e.g. Province / District / Sector), required user fields (email, first name, last name), and required assignment fields (role).")}</p>
            <div class="btn-group" role="group">
              <button type="button" class="btn btn-default grm-template-csv">${__("Download CSV template")}</button>
              <button type="button" class="btn btn-default grm-template-xlsx">${__("Download Excel template")}</button>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-primary grm-stage-next">${__("Continue to upload")}</button>
            </div>
        `);
        $content.find(".grm-template-csv").on("click", () => this._download_template("csv"));
        $content.find(".grm-template-xlsx").on("click", () => this._download_template("xlsx"));
        $content.find(".grm-stage-next").on("click", () => this.set_stage("upload"));
    }

    _download_template(format) {
        // Frappe whitelisted methods that write to `frappe.response` with
        // type=binary are served correctly via /api/method/. Open in a
        // new window so the browser downloads it.
        const project = this.project && this.project.name;
        if (!project) return;
        const params = new URLSearchParams({ project: project, format: format });
        const url = `/api/method/egrm.egrm.page.grm_project_wizard.grm_project_wizard.download_user_template?${params.toString()}`;
        window.open(url, "_blank");
    }

    // --- Stage 2: upload -----------------------------------------------------
    _render_upload_stage($content) {
        const status_html = this.uploaded_file_url
            ? `<p class="grm-upload-status text-success">${__("Uploaded: {0}", [frappe.utils.escape_html(this.uploaded_file_name)])}</p>`
            : `<p class="grm-upload-status text-muted"></p>`;
        $content.html(`
            <div class="grm-step9-upload-zone">
              <div class="grm-upload-icon">⬆</div>
              <p>${__("Drag your CSV or Excel file here, or click to browse.")}</p>
              <button type="button" class="btn btn-default grm-upload-browse">${__("Choose file")}</button>
            </div>
            ${status_html}
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
            </div>
        `);

        const $zone = $content.find(".grm-step9-upload-zone");
        $content.find(".grm-upload-browse").on("click", () => this._open_uploader());
        $zone.on("click", (e) => {
            // Browse-on-zone-click — but ignore clicks that bubbled up from
            // the inner button (which already opens the uploader).
            if ($(e.target).closest(".grm-upload-browse").length) return;
            this._open_uploader();
        });
        $zone.on("dragover", (e) => {
            e.preventDefault();
            $zone.addClass("dragging");
        });
        $zone.on("dragleave", (e) => {
            e.preventDefault();
            $zone.removeClass("dragging");
        });
        $zone.on("drop", (e) => {
            e.preventDefault();
            $zone.removeClass("dragging");
            const files = e.originalEvent && e.originalEvent.dataTransfer
                ? e.originalEvent.dataTransfer.files
                : null;
            if (files && files.length) {
                this._upload_with_files([files[0]]);
            }
        });
        $content.find(".grm-stage-back").on("click", () => this.set_stage("template"));
    }

    _open_uploader() {
        new frappe.ui.FileUploader({
            folder: "Home/Attachments",
            allow_multiple: false,
            disable_file_browser: false,
            allow_toggle_private: false,
            restrictions: {
                allowed_file_types: [".csv", ".xlsx", ".xls"],
                max_file_size: GRM_STEP9_BULK_MAX_FILE_MB * 1024 * 1024,
            },
            on_success: (file_doc) => this._handle_file_doc(file_doc),
        });
    }

    _upload_with_files(files) {
        new frappe.ui.FileUploader({
            files: files,
            folder: "Home/Attachments",
            allow_multiple: false,
            allow_toggle_private: false,
            restrictions: {
                allowed_file_types: [".csv", ".xlsx", ".xls"],
                max_file_size: GRM_STEP9_BULK_MAX_FILE_MB * 1024 * 1024,
            },
            on_success: (file_doc) => this._handle_file_doc(file_doc),
        });
    }

    async _handle_file_doc(file_doc) {
        if (!file_doc || !file_doc.file_url) return;
        this.uploaded_file_url = file_doc.file_url;
        this.uploaded_file_name = file_doc.file_name || file_doc.file_url;
        const $status = this.$mount.find(".grm-upload-status");
        $status
            .removeClass("text-muted text-danger text-success")
            .addClass("text-muted")
            .text(__("Analyzing {0}…", [this.uploaded_file_name]));

        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.auto_detect_user_import_mapping",
                args: { project: this.project.name, file_url: this.uploaded_file_url },
            });
            const m = r.message || {};
            this.headers = m.headers || [];
            this.mapping = m.mapping || {};
            this.project_meta = m.project_meta || {};
            this.validation = m.validation || { ok: false, missing_required: [], errors: [], warnings: [] };
            this.preview_rows = m.preview_rows || [];
            this.total_rows = m.total_rows || 0;
            this.set_stage("mapping");
        } catch (e) {
            $status.removeClass("text-muted text-success").addClass("text-danger")
                .text(__("Could not analyze the file. {0}", [e && e.message ? e.message : ""]));
        }
    }

    // --- Stage 3: mapping ----------------------------------------------------
    _build_target_options() {
        // Mapper dropdown options: skip, User.<field>, Assignment.<field>,
        // administrative_region. Drives the mapping table's <select>s.
        const meta = this.project_meta || {};
        const user_fields = meta.user_fields || [];
        const assignment_fields = meta.assignment_fields || [];

        const options = [{ value: "(skip)", label: __("(skip)") }];

        // Curated subset of User fields — the mapper offers the ones a
        // bulk-import operator is likely to provide. Email/first/last are
        // required (the doctype enforces that); the rest are optional.
        const user_relevant = new Set([
            "email", "first_name", "last_name", "full_name", "username",
            "mobile_no", "phone", "gender",
        ]);
        user_fields.forEach((f) => {
            if (!user_relevant.has(f.fieldname)) return;
            const star = f.reqd ? " *" : "";
            options.push({
                value: `User.${f.fieldname}`,
                label: `${__("User")} → ${f.label}${star}`,
                reqd: !!f.reqd,
            });
        });

        // Assignment fields — exclude framework/system/audit fields and
        // administrative_region (handled separately as a sentinel target).
        const skip_assignment = new Set([
            "project", "user", "name", "owner", "creation",
            "modified", "modified_by", "docstatus", "idx",
            "activation_code", "activation_status", "activation_expires_on",
            "code_sent_on", "activated_on", "activation_attempts",
            "administrative_region",
        ]);
        assignment_fields.forEach((f) => {
            if (skip_assignment.has(f.fieldname)) return;
            if (f.read_only) return;
            const star = f.reqd ? " *" : "";
            options.push({
                value: `Assignment.${f.fieldname}`,
                label: `${__("Assignment")} → ${f.label}${star}`,
                reqd: !!f.reqd,
            });
        });

        options.push({
            value: "administrative_region",
            label: __("Administrative region"),
            reqd: false,
        });
        return options;
    }

    _render_mapping_stage($content) {
        const target_options = this._build_target_options();
        const meta = this.project_meta || {};
        const project_levels = meta.project_levels || [];

        const target_options_html = (selected) => target_options.map((t) => {
            const sel = (t.value === selected) ? "selected" : "";
            return `<option value="${frappe.utils.escape_html(t.value)}" ${sel}>${frappe.utils.escape_html(t.label)}</option>`;
        }).join("");

        const level_options_html = (selected) => project_levels.map((l) => {
            const val = l.name;
            const sel = (val === selected) ? "selected" : "";
            return `<option value="${frappe.utils.escape_html(val)}" ${sel}>${frappe.utils.escape_html(l.level_name || val)}</option>`;
        }).join("");

        const sample_for = (header) => {
            const i = this.headers.indexOf(header);
            const first = this.preview_rows && this.preview_rows[0];
            if (i < 0 || !first || i >= first.length) return "";
            return first[i] == null ? "" : String(first[i]);
        };

        const rows_html = this.headers.map((h) => {
            const m = this.mapping[h] || { target: "(skip)", level_type: null };
            const is_region = m.target === "administrative_region";
            const level_html = is_region ? `
                <select class="form-control form-control-sm grm-level-select" data-header="${frappe.utils.escape_html(h)}">
                  <option value="">${__("(pick level)")}</option>
                  ${level_options_html(m.level_type || "")}
                </select>
            ` : "";
            const warn_html = m.warning
                ? `<span class="text-warning">⚠ ${frappe.utils.escape_html(m.warning)}</span>`
                : "";
            const sample = sample_for(h);
            return `
              <tr data-header="${frappe.utils.escape_html(h)}">
                <td><code>${frappe.utils.escape_html(h)}</code></td>
                <td><code class="text-muted small">${frappe.utils.escape_html(sample)}</code></td>
                <td>
                  <select class="form-control form-control-sm grm-target-select" data-header="${frappe.utils.escape_html(h)}">
                    ${target_options_html(m.target)}
                  </select>
                </td>
                <td class="grm-level-cell">${level_html}</td>
                <td>${warn_html}</td>
              </tr>
            `;
        }).join("");

        const validation_banner = this._render_validation_banner();
        const total_rows_label = this.total_rows === 1
            ? __("1 data row detected")
            : __("{0} data rows detected", [this.total_rows]);

        $content.html(`
            <p>${__("Map each column from your file to a target field. Required fields are marked with an asterisk.")} <span class="text-muted">${total_rows_label}.</span></p>
            <div class="grm-mapper-banner">${validation_banner}</div>
            <div class="grm-mapper-table-wrap">
              <table class="grm-mapper-table">
                <thead>
                  <tr>
                    <th>${__("Source column")}</th>
                    <th>${__("Sample")}</th>
                    <th>${__("Target field")}</th>
                    <th>${__("Level type")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>${rows_html}</tbody>
              </table>
            </div>
            <div class="grm-mapper-options">
              <label>
                <input type="checkbox" class="grm-auto-create-regions" checked>
                ${__("Auto-create missing administrative regions")}
              </label>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
              <button type="button" class="btn btn-primary grm-stage-next" ${this.validation && this.validation.ok ? "" : "disabled"}>${__("Continue to preview")}</button>
            </div>
        `);

        $content.on("change", ".grm-target-select", (e) => {
            const $sel = $(e.currentTarget);
            const header = $sel.data("header");
            const target = $sel.val();
            this.mapping[header] = this.mapping[header] || {};
            this.mapping[header].target = target;
            // Reset level_type when switching away from region.
            if (target !== "administrative_region") {
                this.mapping[header].level_type = null;
            }
            this._revalidate();
            this._render_mapping_stage($content);
        });
        $content.on("change", ".grm-level-select", (e) => {
            const $sel = $(e.currentTarget);
            const header = $sel.data("header");
            this.mapping[header] = this.mapping[header] || {};
            this.mapping[header].level_type = $sel.val() || null;
            this._revalidate();
            // Re-render to update the validation banner / Continue button.
            this._render_mapping_stage($content);
        });
        $content.find(".grm-stage-back").on("click", () => this.set_stage("upload"));
        $content.find(".grm-stage-next").on("click", () => this._start_preview());
    }

    _revalidate() {
        // Doctype-driven required set: Assignment.* with reqd=1 (excluding
        // project) plus the User minimum (email/first/last OR full_name).
        const meta = this.project_meta || {};
        const assignment_fields = meta.assignment_fields || [];
        const required = assignment_fields
            .filter((f) => f.reqd && f.fieldname !== "project" && f.fieldname !== "administrative_region")
            .map((f) => `Assignment.${f.fieldname}`);

        const targets_in_use = new Set();
        const errors = [];
        const level_seen = new Map(); // level_type -> [headers]
        Object.entries(this.mapping || {}).forEach(([header, m]) => {
            const t = m && m.target;
            if (!t || t === "(skip)") return;
            targets_in_use.add(t);
            if (t === "administrative_region") {
                if (!m.level_type) {
                    errors.push(__("Column '{0}' is mapped to administrative region but has no level type selected.", [header]));
                } else {
                    const arr = level_seen.get(m.level_type) || [];
                    arr.push(header);
                    level_seen.set(m.level_type, arr);
                }
            }
        });
        // At-most-one column per level-type.
        for (const [lt, headers] of level_seen.entries()) {
            if (headers.length > 1) {
                errors.push(__("Multiple columns mapped to admin level '{0}': {1}. Pick exactly one.", [lt, headers.join(", ")]));
            }
        }

        const missing_required = required.filter((r) => !targets_in_use.has(r));
        // User minimum: either full_name OR (email + first + last).
        const has_full_name = targets_in_use.has("User.full_name");
        if (!has_full_name) {
            ["User.email", "User.first_name", "User.last_name"].forEach((t) => {
                if (!targets_in_use.has(t)) missing_required.push(t);
            });
        }

        this.validation = {
            ok: missing_required.length === 0 && errors.length === 0,
            missing_required: missing_required,
            errors: errors,
            warnings: [],
        };
    }

    _render_validation_banner() {
        const v = this.validation || { ok: false, missing_required: [], errors: [] };
        if (v.ok) {
            return `<div class="alert alert-success">${__("Mapping is complete — ready to preview.")}</div>`;
        }
        const parts = [];
        if (v.missing_required && v.missing_required.length) {
            parts.push(`<div>${__("Map these required fields before continuing:")} <code>${v.missing_required.map(frappe.utils.escape_html).join(", ")}</code></div>`);
        }
        if (v.errors && v.errors.length) {
            parts.push(v.errors.map((e) => `<div>${frappe.utils.escape_html(e)}</div>`).join(""));
        }
        return `<div class="alert alert-warning">${parts.join("")}</div>`;
    }

    // --- Stage 4: preview + import ------------------------------------------
    async _start_preview() {
        const $content = this.$mount.find(".grm-step9-bulk-content");
        const auto_create = this.$mount.find(".grm-auto-create-regions").is(":checked");

        // Build the wire-format mappings the server endpoint expects.
        const header_mapping = {};
        const level_mapping = {};
        Object.entries(this.mapping || {}).forEach(([header, m]) => {
            if (!m || !m.target) return;
            header_mapping[header] = m.target;
            if (m.target === "administrative_region" && m.level_type) {
                level_mapping[header] = m.level_type;
            }
        });

        frappe.dom.freeze(__("Preparing preview…"));
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.prepare_user_import",
                args: {
                    project: this.project.name,
                    file_url: this.uploaded_file_url,
                    header_mapping: JSON.stringify(header_mapping),
                    level_mapping: JSON.stringify(level_mapping),
                    auto_create_regions: auto_create ? 1 : 0,
                },
            });
            this.preview = r.message || {};
            this.data_import_name = this.preview.data_import || null;
            this.regions_to_create = this.preview.regions_to_create || [];
            this.set_stage("preview");
        } catch (e) {
            // frappe.call already surfaces server errors via dialog.
        } finally {
            frappe.dom.unfreeze();
        }
    }

    _render_preview_stage($content) {
        const p = this.preview || {};
        const preview_rows = (p.preview || []).slice(0, GRM_STEP9_BULK_PREVIEW_LIMIT);
        const headers = preview_rows.length ? Object.keys(preview_rows[0]) : [];
        const header_html = headers.map((h) => `<th>${frappe.utils.escape_html(h)}</th>`).join("");
        const rows_html = preview_rows.map((row) =>
            `<tr>${headers.map((h) => `<td>${frappe.utils.escape_html(String(row[h] == null ? "" : row[h]))}</td>`).join("")}</tr>`
        ).join("");

        const regions_html = (this.regions_to_create && this.regions_to_create.length) ? `
            <div class="alert alert-info">
              <strong>${__("Regions that will be created:")}</strong>
              ${this.regions_to_create.map((r) => {
                  // Server may return [level_type, value] pairs OR
                  // [level_type, value, parent] triples.
                  const lt = Array.isArray(r) ? r[0] : (r && r.level_type) || "";
                  const v = Array.isArray(r) ? r[1] : (r && r.value) || "";
                  return `<code>${frappe.utils.escape_html(lt)}=${frappe.utils.escape_html(v)}</code>`;
              }).join(", ")}
            </div>` : "";

        const errors_html = (p.errors && p.errors.length) ? `
            <div class="alert alert-warning">
              ${p.errors.map((e) => `<div>${frappe.utils.escape_html(String(e))}</div>`).join("")}
            </div>` : "";

        const warnings_html = (p.warnings && p.warnings.length) ? `
            <div class="alert alert-info">
              ${p.warnings.map((w) => `<div>${frappe.utils.escape_html(String(w))}</div>`).join("")}
            </div>` : "";

        const summary = __("{0} rows ready, {1} skipped (of {2} total).",
            [p.rows_ready || 0, p.rows_skipped || 0, p.rows_total || 0]);
        const can_start = !!(this.data_import_name && (p.rows_ready || 0) > 0);
        const start_disabled = can_start ? "" : "disabled";
        const no_import_hint = !can_start && (p.rows_ready === 0)
            ? `<p class="text-muted">${__("No rows are ready to import. Adjust your mapping or input file and try again.")}</p>`
            : "";

        $content.html(`
            <p><strong>${frappe.utils.escape_html(summary)}</strong></p>
            ${regions_html}
            ${errors_html}
            ${warnings_html}
            ${headers.length ? `
              <div class="grm-preview-table-wrap">
                <table class="grm-preview-table">
                  <thead><tr>${header_html}</tr></thead>
                  <tbody>${rows_html}</tbody>
                </table>
              </div>
            ` : `<p class="text-muted">${__("No preview rows available.")}</p>`}
            ${no_import_hint}
            <div class="grm-import-progress" hidden>
              <progress class="grm-progress-bar" value="0" max="100"></progress>
              <p class="grm-progress-text text-muted"></p>
              <pre class="grm-progress-log small text-muted"></pre>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
              <button type="button" class="btn btn-success grm-import-start" ${start_disabled}>${__("Start import")}</button>
            </div>
        `);

        $content.find(".grm-stage-back").on("click", () => this.set_stage("mapping"));
        $content.find(".grm-import-start").on("click", () => this._start_import());
    }

    async _start_import() {
        if (!this.data_import_name) return;
        const $progress = this.$mount.find(".grm-import-progress");
        $progress.removeAttr("hidden");
        this.$mount.find(".grm-import-start").prop("disabled", true);
        this.$mount.find(".grm-stage-back").prop("disabled", true);
        this.$mount.find(".grm-progress-text").text(__("Starting import…"));
        try {
            await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.start_user_import",
                args: { data_import: this.data_import_name },
            });
            this._poll_progress();
        } catch (e) {
            this.$mount.find(".grm-progress-text")
                .removeClass("text-muted").addClass("text-danger")
                .text(__("Could not start the import."));
            this.$mount.find(".grm-import-start").prop("disabled", false);
            this.$mount.find(".grm-stage-back").prop("disabled", false);
        }
    }

    _poll_progress() {
        const tick = async () => {
            let s = null;
            try {
                const r = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.poll_user_import",
                    args: { data_import: this.data_import_name },
                });
                s = r.message || {};
            } catch (e) {
                this.$mount.find(".grm-progress-text").text(__("Polling failed."));
                return;
            }
            const succeeded = s.succeeded || 0;
            const failed = s.failed || 0;
            const done = succeeded + failed;
            const expected = (this.preview && this.preview.rows_ready) || 1;
            const pct = Math.min(100, Math.round((done / expected) * 100));
            this.$mount.find(".grm-progress-bar").val(pct);
            this.$mount.find(".grm-progress-text").text(
                __("{0}: {1} succeeded, {2} failed", [s.status || "", succeeded, failed])
            );
            if (s.import_log_preview) {
                this.$mount.find(".grm-progress-log").text(s.import_log_preview);
            }
            const terminal = ["Success", "Partial Success", "Error", "Failed"];
            if (terminal.indexOf(s.status) >= 0) {
                const indicator = s.status === "Success" ? "green"
                    : (s.status === "Failed" || s.status === "Error") ? "red"
                    : "orange";
                frappe.show_alert({
                    message: __("Import {0}: {1} succeeded, {2} failed", [s.status, succeeded, failed]),
                    indicator: indicator,
                });
                this.$mount.find(".grm-stage-back").prop("disabled", false);
                try { this.on_completed(); } catch (e) { /* non-fatal */ }
                return;
            }
            this.poll_handle = setTimeout(tick, GRM_STEP9_BULK_POLL_MS);
        };
        tick();
    }
}


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
        // Composition: existing-users list + Add-users panel (Single + Bulk).
        this.$body.html(`
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
            },
        });
        this.import_panel = new GRMWizardStep9UserImport({
            project: this.project,
            $mount: $content,
            on_completed: () => {
                if (this.list_panel && this.list_panel.refresh) {
                    this.list_panel.refresh();
                }
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
        // User creation is optional per step. Continue freely.
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 10 — Issue Routing finalization (review per-category routing)
// ---------------------------------------------------------------------------
class GRMWizardStep10Routing {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.categories = [];
        this.departments = [];
        this.roles = [];
        this.render();
    }

    async render() {
        if (!this.project) {
            this.$body.html(`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`);
            return;
        }
        this.$body.html(`<p class="text-muted">${__("Loading…")}</p>`);
        await this._load();
        this._render_table();
    }

    async _load() {
        try {
            const [cats, depts, roles] = await Promise.all([
                frappe.db.get_list("GRM Issue Category", {
                    filters: [["GRM Project Link", "project", "=", this.project.name]],
                    fields: ["name", "category_name", "label", "routing_target_type", "assigned_department", "assigned_role"],
                    limit: 0,
                }),
                frappe.db.get_list("GRM Issue Department", {
                    filters: { project: this.project.name },
                    fields: ["name", "department_name"],
                    limit: 0,
                }),
                frappe.db.get_list("GRM Project Role", {
                    filters: { project: this.project.name, is_active: 1 },
                    fields: ["name", "role_name"],
                    limit: 0,
                }),
            ]);
            this.categories = cats || [];
            this.departments = depts || [];
            this.roles = roles || [];
        } catch (e) {
            this.categories = [];
            this.departments = [];
            this.roles = [];
        }
    }

    _opt(value, label, selected) {
        const sel = (selected != null && String(selected) === String(value)) ? "selected" : "";
        return `<option value="${frappe.utils.escape_html(value || "")}" ${sel}>${frappe.utils.escape_html(label || "")}</option>`;
    }

    _render_table() {
        if (!this.categories.length) {
            this.$body.html(`<p class="text-muted">${__("No issue categories defined yet — go back to Step 5 to add some.")}</p>`);
            return;
        }
        const dept_opts = this.departments.map(d => `<option value="${frappe.utils.escape_html(d.name)}">${frappe.utils.escape_html(d.department_name || d.name)}</option>`).join("");
        const role_opts = this.roles.map(r => `<option value="${frappe.utils.escape_html(r.name)}">${frappe.utils.escape_html(r.role_name || r.name)}</option>`).join("");
        const rows = this.categories.map(c => {
            const tt = c.routing_target_type || "Department";
            const dept_options = `<option value="">— ${__("None")} —</option>` + dept_opts.replace(`value="${frappe.utils.escape_html(c.assigned_department)}"`, `value="${frappe.utils.escape_html(c.assigned_department)}" selected`);
            const role_options = `<option value="">— ${__("None")} —</option>` + role_opts.replace(`value="${frappe.utils.escape_html(c.assigned_role)}"`, `value="${frappe.utils.escape_html(c.assigned_role)}" selected`);
            return `
              <tr data-cat="${frappe.utils.escape_html(c.name)}">
                <td>${frappe.utils.escape_html(c.label || c.category_name || c.name)}</td>
                <td>
                  <select class="form-control form-control-sm grm-r-type">
                    <option value="Department" ${tt === "Department" ? "selected" : ""}>${__("Department")}</option>
                    <option value="Role"       ${tt === "Role"       ? "selected" : ""}>${__("Role")}</option>
                  </select>
                </td>
                <td>
                  <select class="form-control form-control-sm grm-r-target-dept" ${tt === "Role" ? "style='display:none'" : ""}>
                    ${dept_options}
                  </select>
                  <select class="form-control form-control-sm grm-r-target-role" ${tt === "Department" ? "style='display:none'" : ""}>
                    ${role_options}
                  </select>
                </td>
              </tr>`;
        }).join("");
        this.$body.html(`
            <p class="text-muted">${__("Finalise where each category's complaints are routed. Choose a Department for organisational routing, or a Role for cross-department workflows.")}</p>
            <div class="form-grid">
              <table class="table table-borderless">
                <thead><tr><th>${__("Category")}</th><th style="width:160px;">${__("Route To")}</th><th>${__("Target")}</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
        `);
        this.$body.on("change", ".grm-r-type", (e) => {
            const $tr = $(e.target).closest("tr");
            const t = $(e.target).val();
            $tr.find(".grm-r-target-dept").toggle(t === "Department");
            $tr.find(".grm-r-target-role").toggle(t === "Role");
        });
    }

    async save() {
        const tasks = [];
        const me = this;
        this.$body.find("tbody tr").each(function () {
            const $tr = $(this);
            const cat = $tr.data("cat");
            const t = $tr.find(".grm-r-type").val();
            const target = t === "Department"
                ? $tr.find(".grm-r-target-dept").val()
                : $tr.find(".grm-r-target-role").val();
            if (!target) return;
            tasks.push(frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.update_category_routing",
                args: { project: me.project.name, category: cat, target_type: t, target },
            }));
        });
        try { await Promise.all(tasks); return true; }
        catch (e) { return false; }
    }
}

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
              <div id="grm-step12-action"></div>
            </div>
        `);

        const counts = await this.load_counts();
        this.render_summary(counts);
        this.render_action();
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

    render_action() {
        const p = this.project;
        const $a = this.$body.find("#grm-step12-action").empty();

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
        } else {
            $a.append(`
                <p>${__("Tick the confirmation above, then click \"Activate Project\" to mark setup complete and switch to the Platform workspace.")}</p>
            `);
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

// ---------------------------------------------------------------------------
// Step 3 — Administrative Levels
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminLevelsInner {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.editing = null;
        this.adding = false;
        this.selected = new Set();
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
        this.$body.html(`
            <div class="grm-step3" style="max-width: 960px;">
              <div class="grm-step3-intro" style="margin-bottom: 16px;">
                <p>${__("Administrative Levels are the geographic / organizational hierarchy used to route GRM cases (e.g. National &rarr; Region &rarr; District &rarr; Sector &rarr; Cell).")}</p>
                <p class="text-muted small">${__("Lower level_order = higher in the tree (1 = root). Each level defines its own SLA defaults: acknowledgment, resolution, reminder lead time, and auto-escalation.")}</p>
              </div>
              <div id="grm-step3-table-wrap"></div>
              <div id="grm-step3-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step3-add">+ ${__("Add Level")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step3-add").on("click", () => this.start_add());
        await this.load_and_render_table();
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project: this.project.name },
                fields: [
                    "name",
                    "level_name",
                    "level_order",
                    "acknowledgment_days",
                    "resolution_days",
                    "reminder_before_days",
                    "auto_escalate",
                ],
                limit: 0,
                order_by: "level_order asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step3-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No administrative levels yet — click \"Add Level\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Level Name")}</th>
                <th style="width:80px;">${__("Order")}</th>
                <th style="width:90px;">${__("Ack Days")}</th>
                <th style="width:90px;">${__("Res Days")}</th>
                <th style="width:120px;">${__("Reminder Before")}</th>
                <th style="width:110px;">${__("Auto Escalate")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => this.render_row_html(r)).join("");
        $w.html(
            grm_render_bulk_toolbar("levels")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        // Wire up actions via delegation
        $w.find("button.grm-edit").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });
        $w.find("button.grm-save-edit").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.save_edit(name);
        });
        $w.find("button.grm-cancel-edit").on("click", () => {
            this.editing = null;
            this.render_table();
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "levels",
            singular: __("level"),
            plural: __("levels"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected administrative level?")
                : __("Delete {0} selected administrative levels?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Administrative Level Type", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    render_row_html(r) {
        const editing = this.editing === r.name;
        if (editing) {
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"></td>
                <td><input type="text" class="form-control input-xs" id="grm-e-level_name" value="${frappe.utils.escape_html(r.level_name || "")}"></td>
                <td><input type="number" min="1" class="form-control input-xs" id="grm-e-level_order" value="${r.level_order != null ? r.level_order : ""}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-acknowledgment_days" value="${r.acknowledgment_days != null ? r.acknowledgment_days : 7}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-resolution_days" value="${r.resolution_days != null ? r.resolution_days : 30}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-reminder_before_days" value="${r.reminder_before_days != null ? r.reminder_before_days : 2}"></td>
                <td><input type="checkbox" id="grm-e-auto_escalate" ${r.auto_escalate ? "checked" : ""}></td>
                <td>
                  <button class="btn btn-xs btn-primary grm-save-edit" data-name="${frappe.utils.escape_html(r.name)}">${__("Save")}</button>
                  <button class="btn btn-xs btn-default grm-cancel-edit">${__("Cancel")}</button>
                </td>
              </tr>
            `;
        }
        return `
          <tr data-name="${frappe.utils.escape_html(r.name)}">
            <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
            <td>${frappe.utils.escape_html(r.level_name || "")}</td>
            <td>${r.level_order != null ? r.level_order : ""}</td>
            <td>${r.acknowledgment_days != null ? r.acknowledgment_days : ""}</td>
            <td>${r.resolution_days != null ? r.resolution_days : ""}</td>
            <td>${r.reminder_before_days != null ? r.reminder_before_days : ""}</td>
            <td>${r.auto_escalate ? __("Yes") : __("No")}</td>
            <td>
              <button class="grm-row-action grm-edit" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
              <button class="grm-row-action grm-row-action-danger grm-delete" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
            </td>
          </tr>
        `;
    }

    start_edit(name) {
        this.editing = name;
        this.adding = false;
        this.$body.find("#grm-step3-form-wrap").empty();
        this.render_table();
    }

    async save_edit(name) {
        const $row = this.$body.find(`#grm-step3-table-wrap tr[data-name="${CSS.escape(name)}"]`);
        const orig = this.rows.find((x) => x.name === name);
        if (!orig) return;
        const level_name = ($row.find("#grm-e-level_name").val() || "").trim();
        const level_order = parseInt($row.find("#grm-e-level_order").val(), 10);
        const ack = parseInt($row.find("#grm-e-acknowledgment_days").val(), 10);
        const res = parseInt($row.find("#grm-e-resolution_days").val(), 10);
        const rem = parseInt($row.find("#grm-e-reminder_before_days").val(), 10);
        const auto = $row.find("#grm-e-auto_escalate").is(":checked") ? 1 : 0;

        if (!level_name) {
            frappe.show_alert({ message: __("Level Name is required."), indicator: "red" });
            return;
        }
        if (isNaN(level_order) || level_order < 1) {
            frappe.show_alert({ message: __("Level Order must be an integer >= 1."), indicator: "red" });
            return;
        }
        // Local uniqueness check (excluding self)
        const dup = this.rows.find(
            (x) => x.name !== name && (x.level_name || "").toLowerCase() === level_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Level Name '{0}' already exists for this project.", [level_name]), indicator: "red" });
            return;
        }

        const updates = {
            level_name,
            level_order,
            acknowledgment_days: isNaN(ack) ? 7 : ack,
            resolution_days: isNaN(res) ? 30 : res,
            reminder_before_days: isNaN(rem) ? 2 : rem,
            auto_escalate: auto,
        };
        try {
            // Use a single get_doc + frappe.client.save to update level_name (which is the autoname)
            // safely. Per-field set_value can't change the document name itself.
            const doc = await frappe.db.get_doc("GRM Administrative Level Type", name);
            Object.assign(doc, updates);
            await frappe.call({ method: "frappe.client.save", args: { doc } });
            frappe.show_alert({ message: __("Level updated."), indicator: "green" });
            this.editing = null;
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(__("Delete level {0}?", [name]), async () => {
            try {
                await frappe.db.delete_doc("GRM Administrative Level Type", name);
                frappe.show_alert({ message: __("Level deleted."), indicator: "green" });
                if (this.editing === name) this.editing = null;
                await this.load_and_render_table();
            } catch (e) {
                // frappe surfaces the error
            }
        });
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        const $w = this.$body.find("#grm-step3-form-wrap").empty();
        $w.html(`
            <div class="grm-step3-add card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${__("New Administrative Level")}</h5>
              <div class="row">
                <div class="col-md-4">
                  <label class="control-label reqd">${__("Level Name")}</label>
                  <input type="text" class="form-control" id="grm-n-level_name">
                </div>
                <div class="col-md-2">
                  <label class="control-label reqd">${__("Order")}</label>
                  <input type="number" min="1" class="form-control" id="grm-n-level_order">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Ack Days")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-acknowledgment_days" value="7">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Res Days")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-resolution_days" value="30">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Reminder Before")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-reminder_before_days" value="2">
                </div>
              </div>
              <div class="form-group" style="margin-top:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-n-auto_escalate" checked>
                  ${__("Auto Escalate")}
                </label>
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-n-save">${__("Save Level")}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-n-save").on("click", () => this.save_new());
        $w.find("#grm-n-cancel").on("click", () => {
            this.adding = false;
            $w.empty();
        });
    }

    async save_new() {
        const $w = this.$body.find("#grm-step3-form-wrap");
        const level_name = ($w.find("#grm-n-level_name").val() || "").trim();
        const level_order = parseInt($w.find("#grm-n-level_order").val(), 10);
        const ack = parseInt($w.find("#grm-n-acknowledgment_days").val(), 10);
        const res = parseInt($w.find("#grm-n-resolution_days").val(), 10);
        const rem = parseInt($w.find("#grm-n-reminder_before_days").val(), 10);
        const auto = $w.find("#grm-n-auto_escalate").is(":checked") ? 1 : 0;

        if (!level_name) {
            frappe.show_alert({ message: __("Level Name is required."), indicator: "red" });
            return;
        }
        if (isNaN(level_order) || level_order < 1) {
            frappe.show_alert({ message: __("Level Order must be an integer >= 1."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => (x.level_name || "").toLowerCase() === level_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Level Name '{0}' already exists for this project.", [level_name]), indicator: "red" });
            return;
        }

        try {
            await frappe.db.insert({
                doctype: "GRM Administrative Level Type",
                project: this.project.name,
                level_name,
                level_order,
                acknowledgment_days: isNaN(ack) ? 7 : ack,
                resolution_days: isNaN(res) ? 30 : res,
                reminder_before_days: isNaN(rem) ? 2 : rem,
                auto_escalate: auto,
            });
            frappe.show_alert({ message: __("Level created."), indicator: "green" });
            this.adding = false;
            $w.empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    async save() {
        // Rows are persisted inline as the user edits — Continue just advances.
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 4 — Project Roles
// ---------------------------------------------------------------------------
const GRM_DEFAULT_DUTIES = [
    { name: "Intake", label: "Intake" },
    { name: "Review", label: "Review" },
    { name: "Assignment", label: "Assignment" },
    { name: "Investigate & Resolve", label: "Investigate & Resolve" },
    { name: "Feedback", label: "Feedback" },
    { name: "Supervise", label: "Supervise" },
];

class GRMWizardStep7ProjectRoles {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];          // [{name, role_name, admin_level, is_active, duties: Set<string>}]
        this.admin_levels = [];  // [{name, level_name}]
        this.duties = [];        // [{name, label, lifecycle_phase}]
        this.render();
    }

    async render() {
        if (!this.project) {
            this.$body.html(`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`);
            return;
        }
        this.$body.html(`
            <div class="grm-step7-roles">
              <div class="grm-step7-intro" style="margin-bottom: 12px;">
                <p>${__("Define the project's user types (e.g. \"District GRM Officer\") and tick the duties each role performs in the case lifecycle.")}</p>
                <p class="text-muted small">${__("Tick a checkbox to grant the role that duty — saves immediately.")}</p>
              </div>
              <div class="grm-perm-engine table-responsive" style="min-height: 120px;"></div>
              <div class="grm-step7-footer" style="margin-top: 12px; display: flex; gap: 8px; align-items: center;">
                <button type="button" id="grm-step7-add-role" class="btn btn-default btn-sm">+ ${__("Add Role")}</button>
              </div>
            </div>
        `);
        this.body = this.$body.find(".grm-perm-engine");
        this.install_page_actions();
        this.add_check_events();
        this.$body.find("#grm-step7-add-role").on("click", () => this.show_add_role_dialog());
        await this.load_lookups();
        await this.refresh();
    }

    install_page_actions() {
        // Primary actions live inside the step body (.grm-step7-footer) so they stay
        // co-located with the form and never leak into adjacent steps. Clear any
        // page-header actions that earlier renders (or other steps) may have set.
        if (this.wizard && this.wizard.page) {
            try { this.wizard.page.clear_primary_action && this.wizard.page.clear_primary_action(); } catch (e) { /* ignore */ }
            try { this.wizard.page.clear_secondary_action && this.wizard.page.clear_secondary_action(); } catch (e) { /* ignore */ }
        }
    }

    async load_lookups() {
        try {
            this.admin_levels = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project: this.project.name },
                fields: ["name", "level_name"],
                limit: 0,
                order_by: "level_order asc",
            });
        } catch (e) {
            this.admin_levels = [];
        }
        try {
            const duty_rows = await frappe.db.get_list("GRM Duty", {
                fields: ["name", "duty_name", "label", "lifecycle_phase"],
                limit: 0,
                order_by: "lifecycle_phase asc",
            });
            this.duties = (duty_rows && duty_rows.length)
                ? duty_rows.map((d) => ({
                    name: d.name,
                    label: d.label || d.duty_name || d.name,
                    lifecycle_phase: d.lifecycle_phase || "",
                }))
                : GRM_DEFAULT_DUTIES.slice();
        } catch (e) {
            this.duties = GRM_DEFAULT_DUTIES.slice();
        }
    }

    async refresh() {
        try {
            const list_rows = await frappe.db.get_list("GRM Project Role", {
                filters: { project: this.project.name },
                fields: ["name", "role_name", "admin_level", "is_active"],
                limit: 0,
                order_by: "role_name asc",
            });
            const docs = await Promise.all(
                list_rows.map((r) => frappe.db.get_doc("GRM Project Role", r.name).catch(() => null)),
            );
            this.rows = list_rows.map((r, i) => {
                const doc = docs[i];
                const duties = new Set(
                    doc && Array.isArray(doc.duties) ? doc.duties.map((d) => d.duty).filter(Boolean) : [],
                );
                return Object.assign({}, r, { duties });
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        if (!this.rows.length) {
            this.body.html(`
                <p class="text-muted">${__("No roles yet — click \"+ Add Role\" below to create the first one.")}</p>
            `);
            this.selected = new Set();
            return;
        }
        // Mirror Frappe's child-table grid markup + .form-grid-container.column-limit-reached
        // wrapper (see /app/doctype/<X>#permissions_tab):
        //   .form-grid-container.column-limit-reached > .form-grid > .grid-heading-row > .grid-row >
        //     .data-row.row.m-0 > [.row-check, .row-index, .col.grid-static-col[.col-xs-N]...]
        // Using these classes lets us inherit ALL of Frappe's grid CSS
        // (common/grid.scss + element/checkbox.scss) — including the per-col-xs-N
        // explicit widths and 31/40px sticky structural cols — without redefining anything.
        // (No trailing decorative cog — `_actions` is the last child; the
        // `:last-child → 30px sticky` rule is unset for `.grm-perm-table` in
        // grm_project_wizard.css.)
        if (!this.selected) this.selected = new Set();
        // Drop selected names that no longer exist (e.g., after a delete).
        const existing = new Set(this.rows.map((r) => r.name));
        for (const n of [...this.selected]) if (!existing.has(n)) this.selected.delete(n);

        const esc = frappe.utils.escape_html;
        const duty_heads = (this.duties || []).map((d) => {
            const tip = d.lifecycle_phase ? `title="${esc(d.lifecycle_phase)}"` : "";
            return `
                <div class="col grid-static-col text-center grm-duty-col" ${tip} data-fieldname="duty:${esc(d.name)}" data-fieldtype="Check">
                  <div class="static-area ellipsis">${esc(d.label)}</div>
                </div>`;
        }).join("");

        this.body.html(`
            <div class="grm-bulk-actions" data-grm-bulk-for="perm" hidden>
              <span class="grm-bulk-count"></span>
              <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__("Delete")}</button>
              <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__("Clear selection")}</button>
            </div>
            <div class="form-grid-container column-limit-reached">
              <div class="form-grid grm-perm-table">
                <div class="grid-heading-row">
                  <div class="grid-row">
                    <div class="data-row row m-0">
                      <div class="row-check sortable-handle col">
                        <input type="checkbox" class="grid-row-check grm-row-check-all" tabindex="-1">
                      </div>
                      <div class="row-index sortable-handle grid-static-col col"><span>${__("No.")}</span></div>
                      <div class="col grid-static-col col-xs-3" data-fieldname="role_name" data-fieldtype="Data">
                        <div class="static-area ellipsis reqd">${__("Role")}</div>
                      </div>
                      <div class="col grid-static-col col-xs-2" data-fieldname="admin_level" data-fieldtype="Link">
                        <div class="static-area ellipsis">${__("Admin Level")}</div>
                      </div>
                      ${duty_heads}
                      <div class="col grid-static-col text-right" data-fieldname="_actions"></div>
                    </div>
                  </div>
                </div>
                <div class="grid-body">
                  <div class="rows"></div>
                </div>
              </div>
            </div>
        `);
        const $rows = this.body.find(".grid-body > .rows");
        this.rows.forEach((row, idx) => {
            const $r = $(`
                <div class="grid-row" data-name="${esc(row.name)}">
                  <div class="data-row row m-0"></div>
                </div>
            `).appendTo($rows);
            const $dr = $r.find(".data-row");
            const checked = this.selected.has(row.name) ? "checked" : "";
            $(`<div class="row-check sortable-handle col"><input type="checkbox" class="grid-row-check" tabindex="-1" ${checked}></div>`).appendTo($dr);
            $(`<div class="row-index sortable-handle grid-static-col col"><span>${idx + 1}</span></div>`).appendTo($dr);
            this.add_static_col($dr, row.role_name || row.name, "col-xs-3");
            this.add_admin_level_col($dr, row);
            for (const d of this.duties) {
                this.add_duty_check_col($dr, row, d);
            }
            this.add_delete_col($dr, row);
        });
        this.bind_bulk_select();
        this.refresh_bulk_actions();
    }

    bind_bulk_select() {
        // Idempotent: re-bound on every render. Use a namespaced delegated
        // handler so re-renders don't double-fire.
        this.body.off("change.grm-bulk").on("change.grm-bulk", ".grid-row-check", (e) => {
            const $chk = $(e.currentTarget);
            const $headRow = $chk.closest(".grid-heading-row");
            const isHeader = $headRow.length > 0;
            const checked = $chk.prop("checked");
            if (isHeader) {
                this.selected = checked ? new Set(this.rows.map((r) => r.name)) : new Set();
                this.body.find(".grid-body .grid-row-check").prop("checked", checked);
            } else {
                const name = $chk.closest(".grid-row").attr("data-name");
                if (!name) return;
                if (checked) this.selected.add(name);
                else this.selected.delete(name);
            }
            this.refresh_bulk_actions();
        });
        this.body.off("click.grm-bulk").on("click.grm-bulk", ".grm-bulk-delete", () => this.confirm_bulk_delete());
        this.body.on("click.grm-bulk", ".grm-bulk-clear", () => {
            this.selected = new Set();
            this.body.find(".grid-row-check").prop("checked", false);
            this.refresh_bulk_actions();
        });
    }

    refresh_bulk_actions() {
        const n = this.selected.size;
        const $bar = this.body.find(".grm-bulk-actions[data-grm-bulk-for='perm']");
        $bar.attr("hidden", n === 0 ? "hidden" : null);
        $bar.find(".grm-bulk-count").text(
            n === 0 ? "" : (n === 1 ? __("1 row selected") : __("{0} rows selected", [n])),
        );
        $bar.find(".grm-bulk-delete").text(n === 1 ? __("Delete row") : __("Delete {0} rows", [n]));
        const total = this.rows.length;
        const $all = this.body.find(".grm-row-check-all");
        if (total > 0) {
            $all.prop("checked", n === total);
            $all.prop("indeterminate", n > 0 && n < total);
        }
    }

    async confirm_bulk_delete() {
        const names = [...this.selected];
        if (!names.length) return;
        const msg = names.length === 1
            ? __("Delete role {0}?", [names[0]])
            : __("Delete {0} selected roles?", [names.length]);
        const proceed = await new Promise((res) => frappe.confirm(msg, () => res(true), () => res(false)));
        if (!proceed) return;
        const errs = [];
        frappe.dom.freeze(__("Deleting…"));
        for (const name of names) {
            try {
                await new Promise((resolve, reject) => {
                    frappe.call({
                        method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_delete",
                        args: { role: name },
                        callback: (r) => (r && r.exc ? reject(r.exc) : resolve()),
                        error: (e) => reject(e),
                    });
                });
            } catch (e) {
                errs.push(name);
            }
        }
        frappe.dom.unfreeze();
        this.selected = new Set();
        if (errs.length) {
            frappe.show_alert({
                message: __("Could not delete {0} role(s) — they may still be referenced.", [errs.length]),
                indicator: "red",
            });
        } else {
            frappe.show_alert({ message: __("{0} role(s) deleted.", [names.length]), indicator: "green" });
        }
        await this.refresh();
    }

    add_static_col($dr, text, sizing = "") {
        const cls = `col grid-static-col ${sizing}`.trim();
        return $(`<div class="${cls}"><div class="static-area ellipsis"></div></div>`)
            .appendTo($dr)
            .find(".static-area")
            .text(text || "")
            .end();
    }

    format_admin_level(value) {
        if (!value) return "";
        const found = (this.admin_levels || []).find((l) => l.name === value);
        return found ? (found.level_name || value) : value;
    }

    add_admin_level_col($dr, row) {
        const $col = $(`
            <div class="col grid-static-col col-xs-2 grm-edit-cell" data-fieldname="admin_level">
              <div class="static-area ellipsis"></div>
            </div>
        `).appendTo($dr);
        const $sa = $col.find(".static-area");
        const label = this.format_admin_level(row.admin_level);
        if (label) {
            $sa.text(label);
        } else {
            $sa.html(`<span class="grm-edit-placeholder">${__("Click to set")}</span>`);
        }
        $col.on("click", () => this.show_admin_level_dialog(row));
        return $col;
    }

    add_duty_check_col($dr, row, duty) {
        const checked = row.duties.has(duty.name) ? "checked" : "";
        // Frappe-native check cell: <div class='col grid-static-col text-center'>
        //   <div class='static-area ellipsis'><input type='checkbox'></div></div>
        // The <input> inherits Frappe's --checkbox-size from element/checkbox.scss.
        const $col = $(`
            <div class="col grid-static-col text-center grm-duty-cell" data-fieldname="duty:${frappe.utils.escape_html(duty.name)}" data-fieldtype="Check">
              <div class="static-area ellipsis">
                <input type="checkbox" ${checked}>
              </div>
            </div>
        `).appendTo($dr);
        $col.find("input")
            .attr("data-role", row.name)
            .attr("data-duty", duty.name)
            .attr("aria-label", duty.label);
        return $col;
    }

    show_admin_level_dialog(row) {
        const options = ["", ...(this.admin_levels || []).map((l) => l.name)].join("\n");
        const d = new frappe.ui.Dialog({
            title: __("Edit Admin Level — {0}", [row.role_name || row.name]),
            fields: [
                {
                    fieldtype: "Select",
                    label: __("Administrative Level"),
                    fieldname: "admin_level",
                    options: options,
                    default: row.admin_level || "",
                    description: __("Leave blank for project-wide roles."),
                },
            ],
        });
        d.set_primary_action(__("Save"), async () => {
            const v = d.get_value("admin_level") || null;
            try {
                await frappe.db.set_value("GRM Project Role", row.name, "admin_level", v);
                row.admin_level = v;
                d.hide();
                this.render_table();
            } catch (e) {
                frappe.msgprint({ title: __("Error"), message: e.message || e, indicator: "red" });
            }
        });
        d.show();
    }

    add_delete_col($dr, row) {
        const $col = $(`<div class="col grid-static-col text-right" data-fieldname="_actions"></div>`).appendTo($dr);
        $(`<button class="grm-row-action grm-row-action-danger btn-remove-perm" title="${__("Delete role")}">${frappe.utils.icon("close", "sm")}</button>`)
            .appendTo($col)
            .attr("data-name", row.name)
            .on("click", (e) => {
                e.stopPropagation();
                this.confirm_delete(row);
            });
        return $col;
    }

    add_check_events() {
        // Single delegated handler — survives re-renders because it's bound on this.body.
        const me = this;
        this.body.on("click", "input[type='checkbox']", function () {
            const $chk = $(this);
            const role = $chk.attr("data-role");
            const duty = $chk.attr("data-duty");
            if (!role || !duty) return;
            const value = $chk.prop("checked") ? 1 : 0;
            frappe.dom.freeze();
            frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_toggle_duty",
                args: { role, duty, value },
                callback: (r) => {
                    frappe.dom.unfreeze();
                    if (r.exc) {
                        $chk.prop("checked", !$chk.prop("checked"));
                        return;
                    }
                    const row = me.rows.find((x) => x.name === role);
                    if (row) {
                        if (value) row.duties.add(duty);
                        else row.duties.delete(duty);
                    }
                },
            });
        });
    }

    show_add_role_dialog() {
        const d = new frappe.ui.Dialog({
            title: __("Add User Type"),
            fields: [
                {
                    fieldtype: "Data",
                    label: __("Role Name"),
                    fieldname: "role_name",
                    reqd: 1,
                    description: __("e.g. District GRM Officer"),
                },
                {
                    fieldtype: "Select",
                    label: __("Administrative Level (optional)"),
                    fieldname: "admin_level",
                    options: ["", ...this.admin_levels.map((l) => l.name)].join("\n"),
                    description: __("Bind this role to an admin level (e.g. District). Leave blank for project-wide roles."),
                },
            ],
        });
        d.set_primary_action(__("Add"), () => {
            const args = d.get_values();
            if (!args || !args.role_name) return;
            frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_add",
                args: {
                    project: this.project.name,
                    role_name: args.role_name,
                    admin_level: args.admin_level || null,
                },
                callback: (r) => {
                    if (r.exc) return;
                    d.hide();
                    this.refresh();
                },
            });
        });
        d.show();
    }

    confirm_delete(row) {
        frappe.confirm(
            __("Delete role {0}? This cannot be undone.", [row.role_name || row.name]),
            () => {
                frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_delete",
                    args: { role: row.name },
                    callback: (r) => {
                        if (!r.exc) this.refresh();
                    },
                });
            },
        );
    }

    async save() {
        // Grid is auto-saved per-click. Validate that at least one role exists with at least one duty.
        const ok_rows = this.rows.filter((r) => r.duties && r.duties.size > 0);
        if (!ok_rows.length) {
            frappe.throw(__("Define at least one role with at least one duty before continuing."));
        }
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 9 — SLAs
// ---------------------------------------------------------------------------
class GRMWizardStep11SLAs {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];            // current values shown in inputs (from server)
        this.snapshot = {};        // {name: {acknowledgment_days, resolution_days, auto_escalate}}
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
        this.$body.html(`
            <div class="grm-step9" style="max-width: 960px;">
              <div class="grm-step9-intro" style="margin-bottom: 16px;">
                <p>${__("SLAs are tuned per administrative level. Adjust the acknowledgment and resolution targets and toggle auto-escalation for each level.")}</p>
                <p class="text-muted small">${__("Acknowledgment Days: how long before the case must be acknowledged. Resolution Days: how long before it must be resolved. Resolution must be >= Acknowledgment.")}</p>
              </div>
              <div id="grm-step9-table-wrap"></div>
              <div id="grm-step9-error" class="text-danger small" style="margin-top:8px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-primary btn-sm" id="grm-step9-save-all">${__("Save All")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step9-save-all").on("click", () => this.save_all());
        await this.load_and_render_table();
    }

    async load_and_render_table() {
        try {
            const rows = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project: this.project.name },
                fields: ["name", "level_name", "level_order", "acknowledgment_days", "resolution_days", "auto_escalate"],
                limit: 0,
                order_by: "level_order asc",
            });
            this.rows = rows;
            this.snapshot = {};
            for (const r of rows) {
                this.snapshot[r.name] = {
                    acknowledgment_days: r.acknowledgment_days,
                    resolution_days: r.resolution_days,
                    auto_escalate: r.auto_escalate,
                };
            }
        } catch (e) {
            this.rows = [];
            this.snapshot = {};
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step9-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No administrative levels defined yet — go back to Step 2 to add them.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th>${__("Level Name")}</th>
                <th style="width:80px;">${__("Order")}</th>
                <th style="width:160px;">${__("Acknowledgment Days")}</th>
                <th style="width:160px;">${__("Resolution Days")}</th>
                <th style="width:120px;">${__("Auto Escalate")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.level_name || "")}</td>
              <td>${r.level_order != null ? r.level_order : ""}</td>
              <td><input type="number" min="0" class="form-control input-xs grm-s9-ack" value="${r.acknowledgment_days != null ? r.acknowledgment_days : 7}"></td>
              <td><input type="number" min="1" class="form-control input-xs grm-s9-res" value="${r.resolution_days != null ? r.resolution_days : 30}"></td>
              <td><input type="checkbox" class="grm-s9-auto" ${r.auto_escalate ? "checked" : ""}></td>
            </tr>
        `).join("");
        $w.html(`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`);
    }

    read_table() {
        const out = [];
        const $w = this.$body.find("#grm-step9-table-wrap");
        $w.find("tbody tr").each(function () {
            const $tr = $(this);
            const name = $tr.data("name");
            const ack = parseInt($tr.find(".grm-s9-ack").val(), 10);
            const res = parseInt($tr.find(".grm-s9-res").val(), 10);
            const auto = $tr.find(".grm-s9-auto").is(":checked") ? 1 : 0;
            out.push({ name, acknowledgment_days: ack, resolution_days: res, auto_escalate: auto });
        });
        return out;
    }

    validate(values) {
        const errors = [];
        for (const v of values) {
            if (isNaN(v.acknowledgment_days) || v.acknowledgment_days < 0) {
                errors.push(__("Row {0}: Acknowledgment Days must be >= 0.", [v.name]));
            }
            if (isNaN(v.resolution_days) || v.resolution_days < 1) {
                errors.push(__("Row {0}: Resolution Days must be >= 1.", [v.name]));
            }
            if (!isNaN(v.acknowledgment_days) && !isNaN(v.resolution_days) && v.resolution_days < v.acknowledgment_days) {
                errors.push(__("Row {0}: Resolution Days must be >= Acknowledgment Days.", [v.name]));
            }
        }
        return errors;
    }

    async save_all() {
        const ok = await this._do_save();
        if (ok) {
            frappe.show_alert({ message: __("SLAs saved."), indicator: "green" });
        }
        return ok;
    }

    async _do_save() {
        const $err = this.$body.find("#grm-step9-error").empty();
        if (!this.rows.length) {
            // Nothing to save; treat as success (Step 9 isn't blocking when no levels exist)
            return true;
        }
        const values = this.read_table();
        const errors = this.validate(values);
        if (errors.length) {
            $err.html(errors.map((e) => `<div>${frappe.utils.escape_html(e)}</div>`).join(""));
            frappe.show_alert({ message: __("SLA validation failed — see errors above."), indicator: "red" });
            return false;
        }
        try {
            for (const v of values) {
                const orig = this.snapshot[v.name] || {};
                const diffs = {};
                if (orig.acknowledgment_days !== v.acknowledgment_days) diffs.acknowledgment_days = v.acknowledgment_days;
                if (orig.resolution_days !== v.resolution_days) diffs.resolution_days = v.resolution_days;
                if ((orig.auto_escalate ? 1 : 0) !== (v.auto_escalate ? 1 : 0)) diffs.auto_escalate = v.auto_escalate;
                for (const [field, val] of Object.entries(diffs)) {
                    await frappe.db.set_value("GRM Administrative Level Type", v.name, field, val);
                }
            }
            // Refresh snapshot
            for (const v of values) {
                this.snapshot[v.name] = {
                    acknowledgment_days: v.acknowledgment_days,
                    resolution_days: v.resolution_days,
                    auto_escalate: v.auto_escalate,
                };
            }
            return true;
        } catch (e) {
            return false;
        }
    }

    async save() {
        return await this._do_save();
    }
}

// ---------------------------------------------------------------------------
// Step 5 — Issue Categories & Routing
// ---------------------------------------------------------------------------
class GRMWizardStep3IssueCategories {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.departments = [];
        this.project_roles = [];
        this.admin_levels = [];
        this.editing = null;
        this.adding = false;
        this.selected = new Set();
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
        this.$body.html(`
            <div class="grm-step5" style="max-width: 1100px;">
              <div class="grm-step5-intro" style="margin-bottom: 16px;">
                <p>${__("Issue Categories define the kinds of grievances this project handles, plus the default routing (which department or role picks them up, escalation paths, and confidentiality).")}</p>
                <p class="text-muted small">${__("Each category routes to either a Department (organisational) or a Role (cross-department workflow). Step 10 lets you review and re-assign at the end.")}</p>
              </div>
              <div id="grm-step5-notice"></div>
              <div id="grm-step5-table-wrap"></div>
              <div id="grm-step5-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step5-add" disabled>+ ${__("Add Category")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step5-add").on("click", () => this.start_add());
        await this.load_lookups();
        await this.load_and_render_table();
        this.render_notice();
    }

    render_notice() {
        const $n = this.$body.find("#grm-step5-notice").empty();
        if (!this.departments.length) {
            $n.html(`
                <div class="alert alert-warning" style="margin-bottom:12px;">
                  ${__("No departments defined yet — go back to Step 4 first to add departments, then return to this step.")}
                </div>
            `);
            this.$body.find("#grm-step5-add").prop("disabled", true);
        } else {
            this.$body.find("#grm-step5-add").prop("disabled", false);
        }
    }

    async load_lookups() {
        const project = this.project.name;
        try {
            this.departments = await frappe.db.get_list("GRM Issue Department", {
                filters: [["GRM Project Link", "project", "=", project]],
                fields: ["name", "department_name"],
                limit: 0,
                order_by: "department_name asc",
            });
        } catch (e) {
            this.departments = [];
        }
        try {
            this.project_roles = await frappe.db.get_list("GRM Project Role", {
                filters: { project, is_active: 1 },
                fields: ["name", "role_name"],
                limit: 0,
                order_by: "role_name asc",
            });
        } catch (e) {
            this.project_roles = [];
        }
        try {
            this.admin_levels = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project },
                fields: ["name", "level_name"],
                limit: 0,
                order_by: "level_order asc",
            });
        } catch (e) {
            this.admin_levels = [];
        }
    }

    role_options(selected) {
        const opts = [`<option value="">${__("(select)")}</option>`];
        for (const r of (this.project_roles || [])) {
            const sel = r.name === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(r.name)}"${sel}>${frappe.utils.escape_html(r.role_name || r.name)}</option>`);
        }
        return opts.join("");
    }

    role_label(name) {
        const r = (this.project_roles || []).find((x) => x.name === name);
        return r ? (r.role_name || r.name) : (name || "");
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Issue Category", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: [
                    "name",
                    "category_name",
                    "label",
                    "abbreviation",
                    "routing_target_type",
                    "assigned_department",
                    "assigned_role",
                    "assigned_appeal_department",
                    "assigned_escalation_department",
                    "confidentiality_level",
                    "redirection_protocol",
                    "administrative_level",
                ],
                limit: 0,
                order_by: "category_name asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step5-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No categories yet — click \"Add Category\" to create the first one.")}</p>`);
            return;
        }
        const dept_label = (n) => {
            const d = this.departments.find((x) => x.name === n);
            return d ? (d.department_name || d.name) : (n || "");
        };
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th>${__("Label")}</th>
                <th style="width:100px;">${__("Abbrev.")}</th>
                <th>${__("Routes To")}</th>
                <th style="width:140px;">${__("Confidentiality")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => {
            const tt = r.routing_target_type || "Department";
            const target_label = tt === "Role"
                ? this.role_label(r.assigned_role)
                : dept_label(r.assigned_department);
            const target_kind = tt === "Role" ? __("Role") : __("Dept");
            const badge_class = tt === "Role" ? "badge-info" : "badge-secondary";
            return `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.category_name || "")}</td>
              <td>${frappe.utils.escape_html(r.label || "")}</td>
              <td>${frappe.utils.escape_html(r.abbreviation || "")}</td>
              <td><span class="badge ${badge_class}">${target_kind}</span> ${frappe.utils.escape_html(target_label)}</td>
              <td>${frappe.utils.escape_html(r.confidentiality_level || "")}</td>
              <td>
                <button class="grm-row-action grm-edit-cat" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-cat" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
              </td>
            </tr>`;
        }).join("");
        $w.html(
            grm_render_bulk_toolbar("categories")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-cat").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-cat").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "categories",
            singular: __("category"),
            plural: __("categories"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected category?")
                : __("Delete {0} selected categories?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Issue Category", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    department_options(selected, include_blank) {
        const opts = [];
        if (include_blank) opts.push(`<option value="">${__("(none)")}</option>`);
        for (const d of this.departments) {
            const sel = d.name === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(d.name)}"${sel}>${frappe.utils.escape_html(d.department_name || d.name)}</option>`);
        }
        return opts.join("");
    }

    admin_level_options(selected) {
        const opts = [`<option value="">${__("(none)")}</option>`];
        for (const lvl of this.admin_levels) {
            const sel = lvl.name === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(lvl.name)}"${sel}>${frappe.utils.escape_html(lvl.level_name || lvl.name)}</option>`);
        }
        return opts.join("");
    }

    start_add() {
        if (!this.departments.length) {
            frappe.show_alert({ message: __("Add a department in Step 4 first."), indicator: "red" });
            return;
        }
        this.adding = true;
        this.editing = null;
        this.render_form(null);
    }

    start_edit(name) {
        const row = this.rows.find((x) => x.name === name);
        if (!row) return;
        this.editing = name;
        this.adding = false;
        this.render_form(row);
    }

    render_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const conf = r.confidentiality_level || "Public";
        const redir = r.redirection_protocol != null ? String(r.redirection_protocol) : "0";
        const $w = this.$body.find("#grm-step5-form-wrap").empty();
        $w.html(`
            <div class="grm-step5-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Category") : __("New Category")}</h5>
              <div class="row">
                <div class="col-md-4">
                  <label class="control-label reqd">${__("Category Name")}</label>
                  <input type="text" class="form-control" id="grm-cf-category_name" value="${frappe.utils.escape_html(r.category_name || "")}" ${is_edit ? "disabled" : ""}>
                  ${is_edit ? `<small class="text-muted">${__("Category name is the record id and can't be changed after creation.")}</small>` : ""}
                </div>
                <div class="col-md-5">
                  <label class="control-label reqd">${__("Display Label")}</label>
                  <input type="text" class="form-control" id="grm-cf-label" value="${frappe.utils.escape_html(r.label || "")}">
                </div>
                <div class="col-md-3">
                  <label class="control-label reqd">${__("Abbreviation")}</label>
                  <input type="text" class="form-control" id="grm-cf-abbreviation" value="${frappe.utils.escape_html(r.abbreviation || "")}">
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Route To")}</label>
                  <select class="form-control" id="grm-cf-routing_target_type">
                    <option value="Department" ${(r.routing_target_type || "Department") === "Department" ? "selected" : ""}>${__("Department")}</option>
                    <option value="Role"       ${r.routing_target_type === "Role" ? "selected" : ""}>${__("Role")}</option>
                  </select>
                  <small class="text-muted">${__("Choose Department for organisational routing or Role for cross-department workflows.")}</small>
                </div>
                <div class="col-md-6" id="grm-cf-target-dept-wrap" ${r.routing_target_type === "Role" ? `style="display:none"` : ""}>
                  <label class="control-label reqd">${__("Assigned Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_department">
                    <option value="">${__("(select)")}</option>
                    ${this.department_options(r.assigned_department, false)}
                  </select>
                </div>
                <div class="col-md-6" id="grm-cf-target-role-wrap" ${r.routing_target_type !== "Role" ? `style="display:none"` : ""}>
                  <label class="control-label reqd">${__("Assigned Role")}</label>
                  <select class="form-control" id="grm-cf-assigned_role">
                    ${this.role_options(r.assigned_role)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Appeal Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_appeal_department">
                    ${this.department_options(r.assigned_appeal_department, true)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Escalation Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_escalation_department">
                    ${this.department_options(r.assigned_escalation_department, true)}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="control-label">${__("Administrative Level")}</label>
                  <select class="form-control" id="grm-cf-administrative_level">
                    ${this.admin_level_options(r.administrative_level)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Confidentiality Level")}</label>
                  <select class="form-control" id="grm-cf-confidentiality_level">
                    <option value="Public" ${conf === "Public" ? "selected" : ""}>${__("Public")}</option>
                    <option value="Confidential" ${conf === "Confidential" ? "selected" : ""}>${__("Confidential")}</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Redirection Protocol")}</label>
                  <select class="form-control" id="grm-cf-redirection_protocol">
                    <option value="0" ${redir === "0" ? "selected" : ""}>${__("0 = direct routing")}</option>
                    <option value="1" ${redir === "1" ? "selected" : ""}>${__("1 = redirect via supervisor")}</option>
                  </select>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-cf-save">${__("Save Category")}</button>
                <button class="btn btn-default btn-sm" id="grm-cf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-cf-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-cf-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
        $w.find("#grm-cf-routing_target_type").on("change", (ev) => {
            const t = $(ev.target).val();
            $w.find("#grm-cf-target-dept-wrap").toggle(t === "Department");
            $w.find("#grm-cf-target-role-wrap").toggle(t === "Role");
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step5-form-wrap");
        const trim = (id) => ($w.find(`#${id}`).val() || "").trim();
        return {
            category_name: trim("grm-cf-category_name"),
            label: trim("grm-cf-label"),
            abbreviation: trim("grm-cf-abbreviation"),
            routing_target_type: trim("grm-cf-routing_target_type") || "Department",
            assigned_department: trim("grm-cf-assigned_department") || null,
            assigned_role: trim("grm-cf-assigned_role") || null,
            assigned_appeal_department: trim("grm-cf-assigned_appeal_department") || null,
            assigned_escalation_department: trim("grm-cf-assigned_escalation_department") || null,
            administrative_level: trim("grm-cf-administrative_level") || null,
            confidentiality_level: trim("grm-cf-confidentiality_level") || "Public",
            redirection_protocol: trim("grm-cf-redirection_protocol") || "0",
        };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!existing_name && !v.category_name) {
            frappe.show_alert({ message: __("Category Name is required."), indicator: "red" });
            return;
        }
        if (!v.label) {
            frappe.show_alert({ message: __("Display Label is required."), indicator: "red" });
            return;
        }
        if (!v.abbreviation) {
            frappe.show_alert({ message: __("Abbreviation is required."), indicator: "red" });
            return;
        }
        if (v.routing_target_type === "Role") {
            if (!v.assigned_role) {
                frappe.show_alert({ message: __("Assigned Role is required when Route To = Role."), indicator: "red" });
                return;
            }
        } else {
            if (!v.assigned_department) {
                frappe.show_alert({ message: __("Assigned Department is required when Route To = Department."), indicator: "red" });
                return;
            }
        }
        if (!existing_name) {
            const dup = this.rows.find(
                (x) => (x.category_name || "").toLowerCase() === v.category_name.toLowerCase(),
            );
            if (dup) {
                frappe.show_alert({ message: __("Category '{0}' already exists for this project.", [v.category_name]), indicator: "red" });
                return;
            }
        }
        try {
            if (existing_name) {
                const doc = await frappe.db.get_doc("GRM Issue Category", existing_name);
                doc.label = v.label;
                doc.abbreviation = v.abbreviation;
                doc.routing_target_type = v.routing_target_type;
                doc.assigned_department = v.routing_target_type === "Department" ? v.assigned_department : null;
                doc.assigned_role       = v.routing_target_type === "Role"       ? v.assigned_role       : null;
                doc.assigned_appeal_department = v.assigned_appeal_department;
                doc.assigned_escalation_department = v.assigned_escalation_department;
                doc.administrative_level = v.administrative_level;
                doc.confidentiality_level = v.confidentiality_level;
                doc.redirection_protocol = v.redirection_protocol;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Category updated."), indicator: "green" });
            } else {
                const payload = {
                    doctype: "GRM Issue Category",
                    category_name: v.category_name,
                    label: v.label,
                    abbreviation: v.abbreviation,
                    routing_target_type: v.routing_target_type,
                    confidentiality_level: v.confidentiality_level,
                    redirection_protocol: v.redirection_protocol,
                    grm_project_link: [{ project: this.project.name }],
                };
                if (v.routing_target_type === "Role") {
                    payload.assigned_role = v.assigned_role;
                } else {
                    payload.assigned_department = v.assigned_department;
                }
                if (v.assigned_appeal_department) payload.assigned_appeal_department = v.assigned_appeal_department;
                if (v.assigned_escalation_department) payload.assigned_escalation_department = v.assigned_escalation_department;
                if (v.administrative_level) payload.administrative_level = v.administrative_level;
                await frappe.db.insert(payload);
                frappe.show_alert({ message: __("Category created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step5-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete category {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Category", name);
                    frappe.show_alert({ message: __("Category deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete category — it may still be referenced by issues."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 6 — Issue Types
// ---------------------------------------------------------------------------
class GRMWizardStep4IssueTypes {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.editing = null;
        this.adding = false;
        this.selected = new Set();
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
        this.$body.html(`
            <div class="grm-step6" style="max-width: 720px;">
              <div class="grm-step6-intro" style="margin-bottom: 16px;">
                <p>${__("Issue Types complement categories — they describe the broader nature of a complaint (e.g. \"Service Quality\", \"Compensation\", \"Environmental\").")}</p>
                <p class="text-muted small">${__("Types are project-scoped. Pick a small, stable list — citizens see these on intake forms.")}</p>
              </div>
              <div id="grm-step6-table-wrap"></div>
              <div id="grm-step6-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step6-add">+ ${__("Add Type")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step6-add").on("click", () => this.start_add());
        await this.load_and_render_table();
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Issue Type", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: ["name", "type_name"],
                limit: 0,
                order_by: "type_name asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step6-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No issue types yet — click \"Add Type\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Type Name")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => {
            const editing = this.editing === r.name;
            if (editing) {
                return `
                  <tr data-name="${frappe.utils.escape_html(r.name)}">
                    <td class="grm-bulk-cell"></td>
                    <td><input type="text" class="form-control input-xs grm-e-type_name" value="${frappe.utils.escape_html(r.type_name || "")}"></td>
                    <td>
                      <button class="btn btn-xs btn-primary grm-save-edit-type" data-name="${frappe.utils.escape_html(r.name)}">${__("Save")}</button>
                      <button class="btn btn-xs btn-default grm-cancel-edit-type">${__("Cancel")}</button>
                    </td>
                  </tr>
                `;
            }
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
                <td>${frappe.utils.escape_html(r.type_name || "")}</td>
                <td>
                  <button class="grm-row-action grm-edit-type" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                  <button class="grm-row-action grm-row-action-danger grm-delete-type" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
                </td>
              </tr>
            `;
        }).join("");
        $w.html(
            grm_render_bulk_toolbar("types")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-type").on("click", (ev) => {
            this.editing = $(ev.currentTarget).data("name");
            this.render_table();
        });
        $w.find("button.grm-cancel-edit-type").on("click", () => {
            this.editing = null;
            this.render_table();
        });
        $w.find("button.grm-save-edit-type").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.save_edit(name);
        });
        $w.find("button.grm-delete-type").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "types",
            singular: __("type"),
            plural: __("types"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected issue type?")
                : __("Delete {0} selected issue types?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Issue Type", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        const $w = this.$body.find("#grm-step6-form-wrap").empty();
        $w.html(`
            <div class="grm-step6-add card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${__("New Issue Type")}</h5>
              <div class="form-group">
                <label class="control-label reqd">${__("Type Name")}</label>
                <input type="text" class="form-control" id="grm-n-type_name">
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-n-save-type">${__("Save Type")}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel-type">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-n-save-type").on("click", () => this.save_new());
        $w.find("#grm-n-cancel-type").on("click", () => {
            this.adding = false;
            $w.empty();
        });
    }

    async save_new() {
        const $w = this.$body.find("#grm-step6-form-wrap");
        const type_name = ($w.find("#grm-n-type_name").val() || "").trim();
        if (!type_name) {
            frappe.show_alert({ message: __("Type Name is required."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => (x.type_name || "").toLowerCase() === type_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Type '{0}' already exists for this project.", [type_name]), indicator: "red" });
            return;
        }
        try {
            await frappe.db.insert({
                doctype: "GRM Issue Type",
                type_name,
                grm_project_link: [{ project: this.project.name }],
            });
            frappe.show_alert({ message: __("Type created."), indicator: "green" });
            this.adding = false;
            $w.empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    async save_edit(name) {
        const $row = this.$body.find(`#grm-step6-table-wrap tr[data-name="${CSS.escape(name)}"]`);
        const type_name = ($row.find(".grm-e-type_name").val() || "").trim();
        const orig = this.rows.find((x) => x.name === name);
        if (!orig) return;
        if (!type_name) {
            frappe.show_alert({ message: __("Type Name is required."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => x.name !== name && (x.type_name || "").toLowerCase() === type_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Type '{0}' already exists for this project.", [type_name]), indicator: "red" });
            return;
        }
        try {
            const doc = await frappe.db.get_doc("GRM Issue Type", name);
            doc.type_name = type_name;
            await frappe.call({ method: "frappe.client.save", args: { doc } });
            frappe.show_alert({ message: __("Type updated."), indicator: "green" });
            this.editing = null;
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete issue type {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Type", name);
                    frappe.show_alert({ message: __("Type deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete type — it may still be referenced by issues."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 7 — Issue Statuses
// ---------------------------------------------------------------------------
class GRMWizardStep12IssueStatuses {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.editing = null;
        this.adding = false;
        this.selected = new Set();
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
        this.$body.html(`
            <div class="grm-step7" style="max-width: 960px;">
              <div class="grm-step7-intro" style="margin-bottom: 16px;">
                <p>${__("Issue Statuses define the lifecycle of a case — from intake to closure. Mark exactly one status as the Initial status (the entry point) and at least one as Final (resolution / closure).")}</p>
                <p class="text-muted small">${__("Common pattern: \"New\" (initial, open) → \"In Progress\" (open) → \"Resolved\" (final, open) → \"Closed\" (final). Use \"Rejected\" for cases dismissed during review.")}</p>
              </div>
              <div id="grm-step7-table-wrap"></div>
              <div id="grm-step7-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step7-add">+ ${__("Add Status")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step7-add").on("click", () => this.start_add());
        await this.load_and_render_table();
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Issue Status", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: ["name", "status_name", "initial_status", "open_status", "final_status", "rejected_status"],
                limit: 0,
                order_by: "status_name asc",
            });
        } catch (e) {
            this.rows = [];
        }

        // Auto-seed default statuses on first visit (idempotent on the server).
        // Frappe-native lifecycle pattern: New → In Progress → Resolved → Closed,
        // plus Rejected. The user can edit / delete / extend afterwards.
        if (!this.rows.length && !this._seeded) {
            this._seeded = true;
            try {
                const r = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.issue_status_seed_defaults",
                    args: { project: this.project.name },
                });
                if (r && r.message && r.message.count) {
                    frappe.show_alert({
                        message: __("Seeded {0} default statuses. Tweak as needed.", [r.message.count]),
                        indicator: "green",
                    });
                }
                this.rows = await frappe.db.get_list("GRM Issue Status", {
                    filters: [["GRM Project Link", "project", "=", this.project.name]],
                    fields: ["name", "status_name", "initial_status", "open_status", "final_status", "rejected_status"],
                    limit: 0,
                    order_by: "status_name asc",
                });
            } catch (e) {
                // surfaced by frappe; fall through to empty render
            }
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step7-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No statuses yet — click \"Add Status\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Status Name")}</th>
                <th style="width:80px;">${__("Initial?")}</th>
                <th style="width:80px;">${__("Open?")}</th>
                <th style="width:80px;">${__("Final?")}</th>
                <th style="width:90px;">${__("Rejected?")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.status_name || "")}</td>
              <td>${r.initial_status ? __("Yes") : __("No")}</td>
              <td>${r.open_status ? __("Yes") : __("No")}</td>
              <td>${r.final_status ? __("Yes") : __("No")}</td>
              <td>${r.rejected_status ? __("Yes") : __("No")}</td>
              <td>
                <button class="grm-row-action grm-edit-status" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-status" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(
            grm_render_bulk_toolbar("statuses")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-status").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-status").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "statuses",
            singular: __("status"),
            plural: __("statuses"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected status?")
                : __("Delete {0} selected statuses?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Issue Status", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        this.render_form(null);
    }

    start_edit(name) {
        const row = this.rows.find((x) => x.name === name);
        if (!row) return;
        this.editing = name;
        this.adding = false;
        this.render_form(row);
    }

    render_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const $w = this.$body.find("#grm-step7-form-wrap").empty();
        $w.html(`
            <div class="grm-step7-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Status") : __("New Status")}</h5>
              <div class="form-group">
                <label class="control-label reqd">${__("Status Name")}</label>
                <input type="text" class="form-control" id="grm-sf-status_name" value="${frappe.utils.escape_html(r.status_name || "")}">
              </div>
              <div class="row">
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-initial_status" ${r.initial_status ? "checked" : ""}> ${__("Initial Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-open_status" ${r.open_status ? "checked" : ""}> ${__("Open Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-final_status" ${r.final_status ? "checked" : ""}> ${__("Final Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-rejected_status" ${r.rejected_status ? "checked" : ""}> ${__("Rejected Status")}</label>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-sf-save">${__("Save Status")}</button>
                <button class="btn btn-default btn-sm" id="grm-sf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-sf-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-sf-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step7-form-wrap");
        const checked = (id) => $w.find(`#${id}`).is(":checked") ? 1 : 0;
        return {
            status_name: ($w.find("#grm-sf-status_name").val() || "").trim(),
            initial_status: checked("grm-sf-initial_status"),
            open_status: checked("grm-sf-open_status"),
            final_status: checked("grm-sf-final_status"),
            rejected_status: checked("grm-sf-rejected_status"),
        };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!v.status_name) {
            frappe.show_alert({ message: __("Status Name is required."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => x.name !== existing_name && (x.status_name || "").toLowerCase() === v.status_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Status '{0}' already exists for this project.", [v.status_name]), indicator: "red" });
            return;
        }
        // Soft warning: if marking initial and another row already is initial, advise the user.
        if (v.initial_status) {
            const other_initial = this.rows.find((x) => x.name !== existing_name && x.initial_status);
            if (other_initial) {
                frappe.show_alert({
                    message: __("Heads up: '{0}' is already marked Initial — only one should be the entry point.", [other_initial.status_name || other_initial.name]),
                    indicator: "blue",
                });
            }
        }
        try {
            if (existing_name) {
                const doc = await frappe.db.get_doc("GRM Issue Status", existing_name);
                doc.status_name = v.status_name;
                doc.initial_status = v.initial_status;
                doc.open_status = v.open_status;
                doc.final_status = v.final_status;
                doc.rejected_status = v.rejected_status;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Status updated."), indicator: "green" });
            } else {
                await frappe.db.insert({
                    doctype: "GRM Issue Status",
                    status_name: v.status_name,
                    initial_status: v.initial_status,
                    open_status: v.open_status,
                    final_status: v.final_status,
                    rejected_status: v.rejected_status,
                    grm_project_link: [{ project: this.project.name }],
                });
                frappe.show_alert({ message: __("Status created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step7-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete status {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Status", name);
                    frappe.show_alert({ message: __("Status deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete status — it may still be referenced by issues."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        if (this.rows && this.rows.length > 0) {
            const has_initial = this.rows.some(r => r.initial_status);
            const has_final = this.rows.some(r => r.final_status);
            if (!has_initial || !has_final) {
                const missing = [];
                if (!has_initial) missing.push(__("an Initial status"));
                if (!has_final) missing.push(__("a Final status"));
                frappe.show_alert({
                    message: __("Please define {0} before continuing.", [missing.join(__(" and "))]),
                    indicator: "red",
                });
                return false;
            }
        }
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 8 — Departments
// ---------------------------------------------------------------------------
class GRMWizardStep8Departments {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.users = [];
        this.editing = null;
        this.adding = false;
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
        this.$body.html(`
            <div class="grm-step8" style="max-width: 960px;">
              <div class="grm-step8-intro" style="margin-bottom: 16px;">
                <p>${__("Departments are the organizational units that handle issues — typical examples: Customer Service, Engineering, Compliance, Field Operations.")}</p>
                <p class="text-muted small">${__("Each department can have a head — a user who oversees issues routed there. Step 5 (Categories) assigns issues to one of these departments by default.")}</p>
              </div>
              <div id="grm-step8-table-wrap"></div>
              <div id="grm-step8-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step8-add">+ ${__("Add Department")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step8-add").on("click", () => this.start_add());
        await this.load_users();
        await this.load_and_render_table();
    }

    async load_users() {
        try {
            this.users = await frappe.db.get_list("User", {
                fields: ["name", "full_name"],
                filters: { enabled: 1 },
                limit: 100,
                order_by: "full_name asc",
            });
        } catch (e) {
            this.users = [];
        }
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Issue Department", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: ["name", "department_name", "head"],
                limit: 0,
                order_by: "department_name asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        // Mirrors the Frappe `Grid` markup + `.form-grid-container.column-limit-reached`
        // wrapper used on /app/doctype/<X>#fields_tab so we inherit:
        //   - outer chrome (border, radius, bg) from grid.scss:742-746
        //   - inner display:grid + border:unset from grid.scss:747-750
        //   - explicit per-col-xs-N widths from grid.scss:757-803
        //   - row-check / row-index 31/40px sticky cols from grid.scss:805-819
        // No trailing decorative cog — `_actions` is the last child; the
        // `:last-child → 30px sticky` rule is unset for `.grm-dept-table` in
        // grm_project_wizard.css so the col-xs-2 actions cell keeps its width.
        const $w = this.$body.find("#grm-step8-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No departments yet — click \"Add Department\" to create the first one.")}</p>`);
            this.selected = new Set();
            return;
        }
        if (!this.selected) this.selected = new Set();
        const existing = new Set(this.rows.map((r) => r.name));
        for (const n of [...this.selected]) if (!existing.has(n)) this.selected.delete(n);

        const esc = frappe.utils.escape_html;
        const user_label = (u) => {
            const found = (this.users || []).find((x) => x.name === u);
            return found ? (found.full_name ? `${found.full_name} (${found.name})` : found.name) : (u || "");
        };
        $w.html(`
            <div class="grm-bulk-actions" data-grm-bulk-for="dept" hidden>
              <span class="grm-bulk-count"></span>
              <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__("Delete")}</button>
              <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__("Clear selection")}</button>
            </div>
            <div class="form-grid-container column-limit-reached">
              <div class="form-grid grm-dept-table">
                <div class="grid-heading-row">
                  <div class="grid-row">
                    <div class="data-row row m-0">
                      <div class="row-check sortable-handle col">
                        <input type="checkbox" class="grid-row-check grm-row-check-all" tabindex="-1">
                      </div>
                      <div class="row-index sortable-handle grid-static-col col"><span>${__("No.")}</span></div>
                      <div class="col grid-static-col col-xs-5" data-fieldname="department_name" data-fieldtype="Data">
                        <div class="static-area ellipsis reqd">${__("Department")}</div>
                      </div>
                      <div class="col grid-static-col col-xs-5" data-fieldname="head" data-fieldtype="Link">
                        <div class="static-area ellipsis">${__("Head")}</div>
                      </div>
                      <div class="col grid-static-col col-xs-2 text-right" data-fieldname="_actions">
                        <div class="static-area ellipsis">${__("Actions")}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="grid-body">
                  <div class="rows"></div>
                </div>
              </div>
            </div>
        `);
        const $rows = $w.find(".grid-body > .rows");
        this.rows.forEach((r, idx) => {
            const $row = $(`<div class="grid-row" data-name="${esc(r.name)}"><div class="data-row row m-0"></div></div>`).appendTo($rows);
            const $dr = $row.find(".data-row");

            // Structural cols (row-check is functional; row-index decorative)
            const checked = this.selected.has(r.name) ? "checked" : "";
            $(`<div class="row-check sortable-handle col"><input type="checkbox" class="grid-row-check" tabindex="-1" ${checked}></div>`).appendTo($dr);
            $(`<div class="row-index sortable-handle grid-static-col col"><span>${idx + 1}</span></div>`).appendTo($dr);

            // Department (read-only static)
            $(`<div class="col grid-static-col col-xs-5" data-fieldname="department_name"><div class="static-area ellipsis"></div></div>`)
                .appendTo($dr).find(".static-area").text(r.department_name || "");

            // Head — click-to-edit cell (User Link dialog)
            const $head = $(`<div class="col grid-static-col col-xs-5 grm-edit-cell" data-fieldname="head"><div class="static-area ellipsis"></div></div>`).appendTo($dr);
            const $hsa = $head.find(".static-area");
            const label = user_label(r.head);
            if (label) $hsa.text(label);
            else $hsa.html(`<span class="grm-edit-placeholder">${__("Click to set")}</span>`);
            $head.on("click", () => this.show_head_dialog(r));

            // Actions — discrete pencil + x icons (col-xs-2 → ~100px flex)
            const $act = $(`<div class="col grid-static-col col-xs-2 text-right" data-fieldname="_actions"></div>`).appendTo($dr);
            $(`<button class="grm-row-action grm-edit-dept" title="${__("Edit")}">${frappe.utils.icon("edit", "sm")}</button>`)
                .appendTo($act).attr("data-name", r.name)
                .on("click", (e) => { e.stopPropagation(); this.start_edit(r.name); });
            $(`<button class="grm-row-action grm-row-action-danger grm-delete-dept" title="${__("Delete")}">${frappe.utils.icon("close", "sm")}</button>`)
                .appendTo($act).attr("data-name", r.name)
                .on("click", (e) => { e.stopPropagation(); this.confirm_delete(r.name); });
        });
        this.bind_bulk_select();
        this.refresh_bulk_actions();
    }

    bind_bulk_select() {
        const $w = this.$body.find("#grm-step8-table-wrap");
        $w.off("change.grm-bulk").on("change.grm-bulk", ".grid-row-check", (e) => {
            const $chk = $(e.currentTarget);
            const isHeader = $chk.closest(".grid-heading-row").length > 0;
            const checked = $chk.prop("checked");
            if (isHeader) {
                this.selected = checked ? new Set(this.rows.map((r) => r.name)) : new Set();
                $w.find(".grid-body .grid-row-check").prop("checked", checked);
            } else {
                const name = $chk.closest(".grid-row").attr("data-name");
                if (!name) return;
                if (checked) this.selected.add(name);
                else this.selected.delete(name);
            }
            this.refresh_bulk_actions();
        });
        $w.off("click.grm-bulk").on("click.grm-bulk", ".grm-bulk-delete", () => this.confirm_bulk_delete());
        $w.on("click.grm-bulk", ".grm-bulk-clear", () => {
            this.selected = new Set();
            $w.find(".grid-row-check").prop("checked", false);
            this.refresh_bulk_actions();
        });
    }

    refresh_bulk_actions() {
        const n = this.selected.size;
        const $bar = this.$body.find(".grm-bulk-actions[data-grm-bulk-for='dept']");
        $bar.attr("hidden", n === 0 ? "hidden" : null);
        $bar.find(".grm-bulk-count").text(
            n === 0 ? "" : (n === 1 ? __("1 row selected") : __("{0} rows selected", [n])),
        );
        $bar.find(".grm-bulk-delete").text(n === 1 ? __("Delete row") : __("Delete {0} rows", [n]));
        const total = this.rows.length;
        const $all = this.$body.find(".grm-row-check-all");
        if (total > 0) {
            $all.prop("checked", n === total);
            $all.prop("indeterminate", n > 0 && n < total);
        }
    }

    async confirm_bulk_delete() {
        const names = [...this.selected];
        if (!names.length) return;
        const msg = names.length === 1
            ? __("Delete department {0}?", [names[0]])
            : __("Delete {0} selected departments?", [names.length]);
        const proceed = await new Promise((res) => frappe.confirm(msg, () => res(true), () => res(false)));
        if (!proceed) return;
        const errs = [];
        frappe.dom.freeze(__("Deleting…"));
        for (const name of names) {
            try {
                await frappe.db.delete_doc("GRM Issue Department", name);
            } catch (e) {
                errs.push(name);
            }
        }
        frappe.dom.unfreeze();
        this.selected = new Set();
        if (this.editing && names.includes(this.editing)) this.editing = null;
        if (errs.length) {
            frappe.show_alert({
                message: __("Could not delete {0} department(s) — they may still be referenced by categories or issues.", [errs.length]),
                indicator: "red",
            });
        } else {
            frappe.show_alert({ message: __("{0} department(s) deleted.", [names.length]), indicator: "green" });
        }
        await this.load_and_render_table();
    }

    show_head_dialog(row) {
        const d = new frappe.ui.Dialog({
            title: __("Edit Head — {0}", [row.department_name || row.name]),
            fields: [
                {
                    fieldtype: "Link",
                    label: __("Head (User)"),
                    fieldname: "head",
                    options: "User",
                    default: row.head || "",
                    description: __("Optional. The user who oversees issues routed to this department."),
                },
            ],
        });
        d.set_primary_action(__("Save"), async () => {
            const v = d.get_value("head") || null;
            try {
                await frappe.db.set_value("GRM Issue Department", row.name, "head", v);
                row.head = v;
                d.hide();
                this.render_table();
            } catch (e) {
                frappe.msgprint({ title: __("Error"), message: e.message || e, indicator: "red" });
            }
        });
        d.show();
    }

    user_options(selected) {
        const opts = [`<option value="">${__("(none)")}</option>`];
        // Always include the currently-selected user even if they're not in the limit-100 list
        let saw_selected = false;
        for (const u of this.users) {
            const sel = u.name === selected ? " selected" : "";
            if (u.name === selected) saw_selected = true;
            const display = u.full_name ? `${u.full_name} (${u.name})` : u.name;
            opts.push(`<option value="${frappe.utils.escape_html(u.name)}"${sel}>${frappe.utils.escape_html(display)}</option>`);
        }
        if (selected && !saw_selected) {
            opts.push(`<option value="${frappe.utils.escape_html(selected)}" selected>${frappe.utils.escape_html(selected)}</option>`);
        }
        return opts.join("");
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        this.render_form(null);
    }

    start_edit(name) {
        const row = this.rows.find((x) => x.name === name);
        if (!row) return;
        this.editing = name;
        this.adding = false;
        this.render_form(row);
    }

    render_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const $w = this.$body.find("#grm-step8-form-wrap").empty();
        $w.html(`
            <div class="grm-step8-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Department") : __("New Department")}</h5>
              <div class="row">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Department Name")}</label>
                  <input type="text" class="form-control" id="grm-df-department_name" value="${frappe.utils.escape_html(r.department_name || "")}">
                </div>
                <div class="col-md-6">
                  <label class="control-label">${__("Head")}</label>
                  <select class="form-control" id="grm-df-head">
                    ${this.user_options(r.head)}
                  </select>
                  <small class="text-muted">${__("Showing up to 100 enabled users.")}</small>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-df-save">${__("Save Department")}</button>
                <button class="btn btn-default btn-sm" id="grm-df-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-df-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-df-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step8-form-wrap");
        return {
            department_name: ($w.find("#grm-df-department_name").val() || "").trim(),
            head: ($w.find("#grm-df-head").val() || "").trim() || null,
        };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!v.department_name) {
            frappe.show_alert({ message: __("Department Name is required."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => x.name !== existing_name && (x.department_name || "").toLowerCase() === v.department_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Department '{0}' already exists for this project.", [v.department_name]), indicator: "red" });
            return;
        }
        try {
            if (existing_name) {
                const doc = await frappe.db.get_doc("GRM Issue Department", existing_name);
                doc.department_name = v.department_name;
                doc.head = v.head;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Department updated."), indicator: "green" });
            } else {
                const payload = {
                    doctype: "GRM Issue Department",
                    department_name: v.department_name,
                    grm_project_link: [{ project: this.project.name }],
                };
                if (v.head) payload.head = v.head;
                await frappe.db.insert(payload);
                frappe.show_alert({ message: __("Department created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step8-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete department {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Department", name);
                    frappe.show_alert({ message: __("Department deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete department — it may still be referenced by categories or issues."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 10 — Citizen Lookups (Age Groups + Citizen Groups)
// ---------------------------------------------------------------------------
class GRMWizardStep5CitizenLookups {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.age_rows = [];
        this.group_rows = [];
        this.editing_age = null;
        this.editing_group = null;
        this.adding_age = false;
        this.adding_group = false;
        this.selected_age = new Set();
        this.selected_group = new Set();
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
        this.$body.html(`
            <div class="grm-step10" style="max-width: 960px;">
              <div class="grm-step10-intro" style="margin-bottom: 16px;">
                <p>${__("Citizen Lookups are the demographic dropdowns shown on intake forms. They help disaggregate complaint data for reporting.")}</p>
                <p class="text-muted small">${__("Age Groups: e.g. \"0-17\", \"18-24\", \"25-44\", \"45-64\", \"65+\". Citizen Groups: tags like \"Indigenous\", \"Smallholder Farmer\", \"Female-headed Household\". Group Type 1 vs 2 lets you split groups into two parallel lists if your form needs it.")}</p>
              </div>

              <div class="grm-step10-section" style="margin-bottom: 24px;">
                <h4>${__("Age Groups")}</h4>
                <div id="grm-step10-age-table-wrap"></div>
                <div id="grm-step10-age-form-wrap" style="margin-top: 12px;"></div>
                <div style="margin-top: 12px;">
                  <button class="btn btn-default btn-sm" id="grm-step10-age-add">+ ${__("Add Age Group")}</button>
                </div>
              </div>

              <div class="grm-step10-section">
                <h4>${__("Citizen Groups")}</h4>
                <div id="grm-step10-group-table-wrap"></div>
                <div id="grm-step10-group-form-wrap" style="margin-top: 12px;"></div>
                <div style="margin-top: 12px;">
                  <button class="btn btn-default btn-sm" id="grm-step10-group-add">+ ${__("Add Citizen Group")}</button>
                </div>
              </div>
            </div>
        `);
        this.$body.find("#grm-step10-age-add").on("click", () => this.start_add_age());
        this.$body.find("#grm-step10-group-add").on("click", () => this.start_add_group());
        await this.load_age_groups();
        await this.load_citizen_groups();
    }

    // ---- Age Groups ----
    async load_age_groups() {
        try {
            this.age_rows = await frappe.db.get_list("GRM Issue Age Group", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: ["name", "age_group"],
                limit: 0,
                order_by: "age_group asc",
            });
        } catch (e) {
            this.age_rows = [];
        }
        this.render_age_table();
    }

    render_age_table() {
        const $w = this.$body.find("#grm-step10-age-table-wrap").empty();
        if (!this.age_rows.length) {
            $w.html(`<p class="text-muted">${__("No age groups yet — click \"Add Age Group\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Age Group")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.age_rows.map((r) => {
            const editing = this.editing_age === r.name;
            if (editing) {
                return `
                  <tr data-name="${frappe.utils.escape_html(r.name)}">
                    <td class="grm-bulk-cell"></td>
                    <td><input type="text" class="form-control input-xs grm-e-age_group" value="${frappe.utils.escape_html(r.age_group || "")}"></td>
                    <td>
                      <button class="btn btn-xs btn-primary grm-save-edit-age" data-name="${frappe.utils.escape_html(r.name)}">${__("Save")}</button>
                      <button class="btn btn-xs btn-default grm-cancel-edit-age">${__("Cancel")}</button>
                    </td>
                  </tr>
                `;
            }
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
                <td>${frappe.utils.escape_html(r.age_group || "")}</td>
                <td>
                  <button class="grm-row-action grm-edit-age" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                  <button class="grm-row-action grm-row-action-danger grm-delete-age" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
                </td>
              </tr>
            `;
        }).join("");
        $w.html(
            grm_render_bulk_toolbar("age")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-age").on("click", (ev) => {
            this.editing_age = $(ev.currentTarget).data("name");
            this.render_age_table();
        });
        $w.find("button.grm-cancel-edit-age").on("click", () => {
            this.editing_age = null;
            this.render_age_table();
        });
        $w.find("button.grm-save-edit-age").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.save_edit_age(name);
        });
        $w.find("button.grm-delete-age").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete_age(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected_age,
            row_names: this.age_rows.map((r) => r.name),
            key: "age",
            singular: __("age group"),
            plural: __("age groups"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected age group?")
                : __("Delete {0} selected age groups?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Issue Age Group", name),
            on_done: () => this.load_age_groups(),
        });
    }

    start_add_age() {
        this.adding_age = true;
        this.editing_age = null;
        const $w = this.$body.find("#grm-step10-age-form-wrap").empty();
        $w.html(`
            <div class="grm-step10-age-add card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${__("New Age Group")}</h5>
              <div class="form-group">
                <label class="control-label reqd">${__("Age Group")}</label>
                <input type="text" class="form-control" id="grm-n-age_group" placeholder="${__("e.g. 18-24")}">
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-n-save-age">${__("Save")}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel-age">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-n-save-age").on("click", () => this.save_new_age());
        $w.find("#grm-n-cancel-age").on("click", () => {
            this.adding_age = false;
            $w.empty();
        });
    }

    async save_new_age() {
        const $w = this.$body.find("#grm-step10-age-form-wrap");
        const age_group = ($w.find("#grm-n-age_group").val() || "").trim();
        if (!age_group) {
            frappe.show_alert({ message: __("Age Group is required."), indicator: "red" });
            return;
        }
        const dup = this.age_rows.find(
            (x) => (x.age_group || "").toLowerCase() === age_group.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Age Group '{0}' already exists for this project.", [age_group]), indicator: "red" });
            return;
        }
        try {
            await frappe.db.insert({
                doctype: "GRM Issue Age Group",
                age_group,
                grm_project_link: [{ project: this.project.name }],
            });
            frappe.show_alert({ message: __("Age Group created."), indicator: "green" });
            this.adding_age = false;
            $w.empty();
            await this.load_age_groups();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    async save_edit_age(name) {
        const $row = this.$body.find(`#grm-step10-age-table-wrap tr[data-name="${CSS.escape(name)}"]`);
        const age_group = ($row.find(".grm-e-age_group").val() || "").trim();
        if (!age_group) {
            frappe.show_alert({ message: __("Age Group is required."), indicator: "red" });
            return;
        }
        const dup = this.age_rows.find(
            (x) => x.name !== name && (x.age_group || "").toLowerCase() === age_group.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Age Group '{0}' already exists for this project.", [age_group]), indicator: "red" });
            return;
        }
        try {
            const doc = await frappe.db.get_doc("GRM Issue Age Group", name);
            doc.age_group = age_group;
            await frappe.call({ method: "frappe.client.save", args: { doc } });
            frappe.show_alert({ message: __("Age Group updated."), indicator: "green" });
            this.editing_age = null;
            await this.load_age_groups();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete_age(name) {
        frappe.confirm(
            __("Delete age group {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Age Group", name);
                    frappe.show_alert({ message: __("Age Group deleted."), indicator: "green" });
                    if (this.editing_age === name) this.editing_age = null;
                    await this.load_age_groups();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete age group — it may still be referenced by issues."), indicator: "red" });
                }
            },
        );
    }

    // ---- Citizen Groups ----
    async load_citizen_groups() {
        try {
            this.group_rows = await frappe.db.get_list("GRM Issue Citizen Group", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: ["name", "group_name", "group_type"],
                limit: 0,
                order_by: "group_name asc",
            });
        } catch (e) {
            this.group_rows = [];
        }
        this.render_group_table();
    }

    render_group_table() {
        const $w = this.$body.find("#grm-step10-group-table-wrap").empty();
        if (!this.group_rows.length) {
            $w.html(`<p class="text-muted">${__("No citizen groups yet — click \"Add Citizen Group\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th style="width:120px;">${__("Type")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.group_rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.group_name || "")}</td>
              <td>${frappe.utils.escape_html(r.group_type || "")}</td>
              <td>
                <button class="grm-row-action grm-edit-group" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-group" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(
            grm_render_bulk_toolbar("groups")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-group").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit_group(name);
        });
        $w.find("button.grm-delete-group").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete_group(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected_group,
            row_names: this.group_rows.map((r) => r.name),
            key: "groups",
            singular: __("citizen group"),
            plural: __("citizen groups"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected citizen group?")
                : __("Delete {0} selected citizen groups?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Issue Citizen Group", name),
            on_done: () => this.load_citizen_groups(),
        });
    }

    start_add_group() {
        this.adding_group = true;
        this.editing_group = null;
        this.render_group_form(null);
    }

    start_edit_group(name) {
        const row = this.group_rows.find((x) => x.name === name);
        if (!row) return;
        this.editing_group = name;
        this.adding_group = false;
        this.render_group_form(row);
    }

    render_group_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const gt = r.group_type != null ? String(r.group_type) : "1";
        const $w = this.$body.find("#grm-step10-group-form-wrap").empty();
        $w.html(`
            <div class="grm-step10-group-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Citizen Group") : __("New Citizen Group")}</h5>
              <div class="row">
                <div class="col-md-7">
                  <label class="control-label reqd">${__("Group Name")}</label>
                  <input type="text" class="form-control" id="grm-gf-group_name" value="${frappe.utils.escape_html(r.group_name || "")}">
                </div>
                <div class="col-md-5">
                  <label class="control-label reqd">${__("Group Type")}</label>
                  <select class="form-control" id="grm-gf-group_type">
                    <option value="1" ${gt === "1" ? "selected" : ""}>${__("1")}</option>
                    <option value="2" ${gt === "2" ? "selected" : ""}>${__("2")}</option>
                  </select>
                  <small class="text-muted">${__("Group Type 1 / 2 separates two parallel demographic dimensions on the intake form.")}</small>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-gf-save">${__("Save Group")}</button>
                <button class="btn btn-default btn-sm" id="grm-gf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-gf-save").on("click", () => this.save_group_form(is_edit ? row.name : null));
        $w.find("#grm-gf-cancel").on("click", () => {
            this.adding_group = false;
            this.editing_group = null;
            $w.empty();
        });
    }

    async save_group_form(existing_name) {
        const $w = this.$body.find("#grm-step10-group-form-wrap");
        const group_name = ($w.find("#grm-gf-group_name").val() || "").trim();
        const group_type = ($w.find("#grm-gf-group_type").val() || "").trim() || "1";
        if (!group_name) {
            frappe.show_alert({ message: __("Group Name is required."), indicator: "red" });
            return;
        }
        const dup = this.group_rows.find(
            (x) => x.name !== existing_name && (x.group_name || "").toLowerCase() === group_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Citizen Group '{0}' already exists for this project.", [group_name]), indicator: "red" });
            return;
        }
        try {
            if (existing_name) {
                const doc = await frappe.db.get_doc("GRM Issue Citizen Group", existing_name);
                doc.group_name = group_name;
                doc.group_type = group_type;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Citizen Group updated."), indicator: "green" });
            } else {
                await frappe.db.insert({
                    doctype: "GRM Issue Citizen Group",
                    group_name,
                    group_type,
                    grm_project_link: [{ project: this.project.name }],
                });
                frappe.show_alert({ message: __("Citizen Group created."), indicator: "green" });
            }
            this.editing_group = null;
            this.adding_group = false;
            $w.empty();
            await this.load_citizen_groups();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete_group(name) {
        frappe.confirm(
            __("Delete citizen group {0}? This will remove it from this project's setup.", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Issue Citizen Group", name);
                    frappe.show_alert({ message: __("Citizen Group deleted."), indicator: "green" });
                    if (this.editing_group === name) this.editing_group = null;
                    await this.load_citizen_groups();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete citizen group — it may still be referenced by issues."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 11 — Notification Templates
// ---------------------------------------------------------------------------
class GRMWizardStep6NotificationTemplates {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.email_templates = [];
        this.editing = null;
        this.adding = false;
        this.selected = new Set();
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
        this.$body.html(`
            <div class="grm-step11" style="max-width: 1100px;">
              <div class="grm-step11-intro" style="margin-bottom: 16px;">
                <p>${__("Notification Templates control the messages sent to citizens at each stage of an issue's lifecycle (receipt, acknowledgment, status updates, escalation, SLA reminders).")}</p>
                <p class="text-muted small">${__("Each template can drive an email (linked Email Template) and / or an SMS (Jinja2 message body). Use {{ tracking_code }}, {{ status }}, {{ subject }}, etc. as placeholders.")}</p>
              </div>
              <div id="grm-step11-table-wrap"></div>
              <div id="grm-step11-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step11-add">+ ${__("Add Template")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step11-add").on("click", () => this.start_add());
        await this.load_email_templates();
        await this.load_and_render_table();
    }

    async load_email_templates() {
        try {
            this.email_templates = await frappe.db.get_list("Email Template", {
                fields: ["name"],
                limit: 50,
                order_by: "name asc",
            });
        } catch (e) {
            this.email_templates = [];
        }
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Notification Template", {
                filters: { project: this.project.name },
                fields: ["name", "template_name", "template_type", "active"],
                limit: 0,
                order_by: "template_type asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step11-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No notification templates yet — click \"Add Template\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th style="width:170px;">${__("Type")}</th>
                <th style="width:90px;">${__("Active")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.template_name || r.name)}</td>
              <td>${frappe.utils.escape_html(r.template_type || "")}</td>
              <td>${r.active ? __("Yes") : __("No")}</td>
              <td>
                <button class="grm-row-action grm-edit-tpl" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-tpl" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(
            grm_render_bulk_toolbar("templates")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "templates",
            singular: __("template"),
            plural: __("templates"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected notification template?")
                : __("Delete {0} selected notification templates?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Notification Template", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    type_options(selected) {
        const types = [
            "Receipt",
            "Acknowledgment",
            "In Progress",
            "Resolved",
            "Closed",
            "Escalated",
            "SLA Reminder",
        ];
        const opts = [`<option value="">${__("(select)")}</option>`];
        for (const t of types) {
            const sel = t === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(t)}"${sel}>${frappe.utils.escape_html(t)}</option>`);
        }
        return opts.join("");
    }

    email_template_options(selected) {
        const opts = [`<option value="">${__("(none)")}</option>`];
        let saw_selected = false;
        for (const t of this.email_templates) {
            const sel = t.name === selected ? " selected" : "";
            if (t.name === selected) saw_selected = true;
            opts.push(`<option value="${frappe.utils.escape_html(t.name)}"${sel}>${frappe.utils.escape_html(t.name)}</option>`);
        }
        if (selected && !saw_selected) {
            opts.push(`<option value="${frappe.utils.escape_html(selected)}" selected>${frappe.utils.escape_html(selected)}</option>`);
        }
        return opts.join("");
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        this.render_form(null);
    }

    async start_edit(name) {
        try {
            const doc = await frappe.db.get_doc("GRM Notification Template", name);
            this.editing = name;
            this.adding = false;
            this.render_form(doc);
        } catch (e) {
            frappe.show_alert({ message: __("Could not load template."), indicator: "red" });
        }
    }

    render_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const active = is_edit ? !!r.active : true;
        const enable_sms = !!r.enable_sms;
        const $w = this.$body.find("#grm-step11-form-wrap").empty();
        $w.html(`
            <div class="grm-step11-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Template") : __("New Template")}</h5>
              <div class="row">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Template Name")}</label>
                  <input type="text" class="form-control" id="grm-tf-template_name" value="${frappe.utils.escape_html(r.template_name || "")}" ${is_edit ? "disabled" : ""}>
                  ${is_edit ? `<small class="text-muted">${__("Template name is the record id and can't be changed.")}</small>` : ""}
                </div>
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Template Type")}</label>
                  <select class="form-control" id="grm-tf-template_type">
                    ${this.type_options(r.template_type)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Email Template")}</label>
                  <select class="form-control" id="grm-tf-email_template">
                    ${this.email_template_options(r.email_template)}
                  </select>
                  <small class="text-muted">${__("Showing up to 50 Email Templates.")}</small>
                </div>
                <div class="col-md-6">
                  <label class="control-label">${__("Active")}</label>
                  <div><label class="checkbox"><input type="checkbox" id="grm-tf-active" ${active ? "checked" : ""}> ${__("Template Active")}</label></div>
                </div>
              </div>
              <div class="form-group" style="margin-top:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-tf-enable_sms" ${enable_sms ? "checked" : ""}>
                  ${__("Enable SMS")}
                </label>
              </div>
              <div class="form-group">
                <label class="control-label">${__("SMS Message")}</label>
                <textarea class="form-control" id="grm-tf-sms_message" rows="4" placeholder="${__("e.g. Issue {{ tracking_code }} is now {{ status }}.")}">${frappe.utils.escape_html(r.sms_message || "")}</textarea>
                <small class="text-muted">${__("Supports Jinja2: {{ tracking_code }}, {{ status }}, {{ subject }}, {{ complainant_name }}, {{ created_date }}, etc.")}</small>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-tf-save">${__("Save Template")}</button>
                <button class="btn btn-default btn-sm" id="grm-tf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-tf-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-tf-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step11-form-wrap");
        const trim = (id) => ($w.find(`#${id}`).val() || "").trim();
        const checked = (id) => $w.find(`#${id}`).is(":checked") ? 1 : 0;
        return {
            template_name: trim("grm-tf-template_name"),
            template_type: trim("grm-tf-template_type"),
            email_template: trim("grm-tf-email_template") || null,
            enable_sms: checked("grm-tf-enable_sms"),
            sms_message: trim("grm-tf-sms_message"),
            active: checked("grm-tf-active"),
        };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!existing_name && !v.template_name) {
            frappe.show_alert({ message: __("Template Name is required."), indicator: "red" });
            return;
        }
        if (!v.template_type) {
            frappe.show_alert({ message: __("Template Type is required."), indicator: "red" });
            return;
        }
        if (!existing_name) {
            const dup = this.rows.find(
                (x) => (x.template_name || "").toLowerCase() === v.template_name.toLowerCase(),
            );
            if (dup) {
                frappe.show_alert({ message: __("Template '{0}' already exists for this project.", [v.template_name]), indicator: "red" });
                return;
            }
        }
        const dup_type = this.rows.find(
            (r) => r.template_type === v.template_type && r.name !== existing_name,
        );
        if (dup_type) {
            frappe.show_alert({
                message: __("A template of type \"{0}\" already exists for this project.", [v.template_type]),
                indicator: "red",
            });
            return;
        }
        try {
            if (existing_name) {
                // Use the doc round-trip so the project field doesn't get unset by partial saves.
                const doc = await frappe.db.get_doc("GRM Notification Template", existing_name);
                doc.project = this.project.name;
                doc.template_type = v.template_type;
                doc.email_template = v.email_template;
                doc.enable_sms = v.enable_sms;
                doc.sms_message = v.sms_message;
                doc.active = v.active;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Template updated."), indicator: "green" });
            } else {
                const payload = {
                    doctype: "GRM Notification Template",
                    template_name: v.template_name,
                    template_type: v.template_type,
                    enable_sms: v.enable_sms,
                    sms_message: v.sms_message,
                    active: v.active,
                    project: this.project.name,
                };
                if (v.email_template) payload.email_template = v.email_template;
                await frappe.db.insert(payload);
                frappe.show_alert({ message: __("Template created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step11-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete notification template {0}?", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Notification Template", name);
                    frappe.show_alert({ message: __("Template deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete template."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}
