frappe.pages["grm-project-wizard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Setup Wizard"),
        single_column: true,
    });
    new GRMProjectWizard(page);
};

const STEP_TITLES = [
    "",
    "Project Information",
    "Uptake Notes",
    "Administrative Levels",
    "Project Roles",
    "Issue Categories & Routing",
    "Issue Types",
    "Issue Statuses",
    "Departments",
    "SLAs",
    "Citizen Lookups",
    "Notification Templates",
    "Activate",
];

const TOTAL_STEPS = 12;

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
        this.render_step();
    }

    render_step() {
        $("#grm-step-title").text(`${this.current_step}. ${STEP_TITLES[this.current_step]}`);
        this.render_stepper();
        this.render_step_body();
        this.update_footer();
    }

    render_stepper() {
        const $s = $("#grm-stepper").empty();
        for (let i = 1; i <= TOTAL_STEPS; i++) {
            const cls = i < this.current_step ? "done" : i === this.current_step ? "active" : "pending";
            $s.append(`<div class="grm-step ${cls}">${i}</div>`);
        }
    }

    step_class(n) {
        const map = {
            1: GRMWizardStep1ProjectInfo,
            2: GRMWizardStep2UptakeNotes,
            3: GRMWizardStep3AdminLevels,
            4: GRMWizardStep4ProjectRoles,
            5: GRMWizardStep5IssueCategories,
            6: GRMWizardStep6IssueTypes,
            7: GRMWizardStep7IssueStatuses,
            8: GRMWizardStep8Departments,
            9: GRMWizardStep9SLAs,
            10: GRMWizardStep10CitizenLookups,
            11: GRMWizardStep11NotificationTemplates,
            12: GRMWizardStep12Activate,
        };
        return map[n] || null;
    }

    render_step_body() {
        const $body = $("#grm-step-body").empty();
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
                method: "egrm.page.grm_project_wizard.grm_project_wizard.activate_project",
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
            <div class="grm-step1-form" style="max-width: 720px;">
              <div class="form-group">
                <label class="control-label reqd">${__("Project Code")}</label>
                <input type="text" class="form-control" id="grm-f-project_code"
                       value="${frappe.utils.escape_html(p.project_code || "")}" ${code_disabled}>
                ${code_warning}
              </div>
              <div class="form-group">
                <label class="control-label reqd">${__("Title")}</label>
                <input type="text" class="form-control" id="grm-f-title"
                       value="${frappe.utils.escape_html(p.title || "")}">
              </div>
              <div class="form-group">
                <label class="control-label">${__("Description")}</label>
                <textarea class="form-control" id="grm-f-description" rows="3">${frappe.utils.escape_html(p.description || "")}</textarea>
              </div>
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
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Default Language")}</label>
                    <input type="text" class="form-control" id="grm-f-default_language"
                           value="${frappe.utils.escape_html(p.default_language || "en")}">
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Auto Escalation Days")}</label>
                    <input type="number" min="0" class="form-control" id="grm-f-auto_escalation_days"
                           value="${p.auto_escalation_days != null ? p.auto_escalation_days : 7}">
                  </div>
                </div>
              </div>
              <div class="form-group">
                <label class="checkbox">
                  <input type="checkbox" id="grm-f-is_active" ${(p.is_active == null ? 1 : p.is_active) ? "checked" : ""}>
                  ${__("Is Active")}
                </label>
              </div>
            </div>
        `);
    }

    read_form() {
        const get = (id) => this.$body.find(`#${id}`).val();
        const checked = (id) => this.$body.find(`#${id}`).is(":checked") ? 1 : 0;
        const trim = (v) => (v == null ? "" : String(v).trim());
        const auto_esc = parseInt(get("grm-f-auto_escalation_days"), 10);
        return {
            project_code: trim(get("grm-f-project_code")),
            title: trim(get("grm-f-title")),
            description: trim(get("grm-f-description")),
            start_date: trim(get("grm-f-start_date")) || null,
            end_date: trim(get("grm-f-end_date")) || null,
            default_language: trim(get("grm-f-default_language")) || "en",
            is_active: checked("grm-f-is_active"),
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
// Step 2 — Uptake Notes
// ---------------------------------------------------------------------------
class GRMWizardStep2UptakeNotes {
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
        const desc = this.project.description || "";
        this.$body.html(`
            <div class="grm-step2-form" style="max-width: 820px;">
              <div class="grm-step2-intro" style="margin-bottom: 16px;">
                <p>${__("The World Bank GRM uptake-channel framework recommends defining how citizens can submit grievances. Capture your project's decisions below.")}</p>
                <ul class="text-muted small">
                  <li>${__("Direct: in-person at field offices, project sites, or community meetings")}</li>
                  <li>${__("Mediated: community focal points, local leaders, paralegals, NGO partners")}</li>
                  <li>${__("Remote: phone hotline, SMS short-code, mobile app, web form, email")}</li>
                  <li>${__("Anonymous: drop-boxes, suggestion boxes at village level")}</li>
                </ul>
                <p class="text-muted small">${__("Example: \"Citizens via mobile + paper letterboxes at village level + community focal points (1 per ADM4).\"")}</p>
              </div>
              <div class="form-group">
                <label class="control-label">${__("Project Description / Uptake Channels")}</label>
                <textarea class="form-control" id="grm-f-description" rows="10">${frappe.utils.escape_html(desc)}</textarea>
                <small class="text-muted">${__("This is saved to the project description and is visible on the GRM Project record.")}</small>
              </div>
            </div>
        `);
    }

    async save() {
        if (!this.project) {
            frappe.show_alert({ message: __("Save Step 1 first."), indicator: "red" });
            return false;
        }
        const value = (this.$body.find("#grm-f-description").val() || "").trim();
        try {
            if ((this.project.description || "") !== value) {
                await frappe.db.set_value("GRM Project", this.project.name, "description", value);
                this.project.description = value;
            }
            return true;
        } catch (e) {
            return false;
        }
    }
}

// ---------------------------------------------------------------------------
// Step 12 — Activate
// ---------------------------------------------------------------------------
class GRMWizardStep12Activate {
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
            // Count distinct GRM Issue Categories linked to this project via GRM Project Link child table
            const r = await frappe.call({
                method: "frappe.client.get_count",
                args: {
                    doctype: "GRM Project Link",
                    filters: { project, parenttype: "GRM Issue Category" },
                    debug: 0,
                },
            });
            // get_count returns a total of links (one per category in normal use)
            counts.categories = (r && r.message) ? r.message : 0;
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
            <table class="table table-bordered" style="margin-bottom:0;">
              <tbody>
                <tr><th style="width:40%;">${__("Project Code")}</th><td>${frappe.utils.escape_html(p.project_code || "")}</td></tr>
                <tr><th>${__("Title")}</th><td>${frappe.utils.escape_html(p.title || "")}</td></tr>
                <tr><th>${__("Administrative Levels")}</th><td>${counts.adm_levels}</td></tr>
                <tr><th>${__("Project Roles")}</th><td>${counts.roles}</td></tr>
                <tr><th>${__("Issue Categories (linked)")}</th><td>${counts.categories}</td></tr>
              </tbody>
            </table>
        `);
    }

    render_action() {
        const p = this.project;
        const $a = this.$body.find("#grm-step12-action").empty();
        if (p.is_setup_complete) {
            $a.html(`
                <div class="alert alert-success" style="margin-bottom:0;">
                  <strong>${__("Project is already active.")}</strong>
                  <a href="/app/grm-project/${encodeURIComponent(p.name)}" class="ml-2">${__("Open project record")}</a>
                </div>
            `);
            // Also tell the wizard footer not to suggest activation
            $("#grm-next").prop("disabled", true).text(__("Already Active"));
        } else {
            $a.html(`
                <p>${__("Pre-flight: review the summary above. Click \"Activate Project\" to mark setup complete and switch to the Platform workspace.")}</p>
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
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 3 — Administrative Levels
// ---------------------------------------------------------------------------
class GRMWizardStep3AdminLevels {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
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
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

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
    }

    render_row_html(r) {
        const editing = this.editing === r.name;
        if (editing) {
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
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
            <td>${frappe.utils.escape_html(r.level_name || "")}</td>
            <td>${r.level_order != null ? r.level_order : ""}</td>
            <td>${r.acknowledgment_days != null ? r.acknowledgment_days : ""}</td>
            <td>${r.resolution_days != null ? r.resolution_days : ""}</td>
            <td>${r.reminder_before_days != null ? r.reminder_before_days : ""}</td>
            <td>${r.auto_escalate ? __("Yes") : __("No")}</td>
            <td>
              <button class="btn btn-xs btn-default grm-edit" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
              <button class="btn btn-xs btn-danger grm-delete" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
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

class GRMWizardStep4ProjectRoles {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];           // [{name, role_name, admin_level, is_active, description, duties: [name,...]}]
        this.admin_levels = [];   // [{name, level_name}]
        this.duties = [];         // [{name, label}]
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
            <div class="grm-step4" style="max-width: 1040px;">
              <div class="grm-step4-intro" style="margin-bottom: 16px;">
                <p>${__("Project Roles bind a project-specific role label (e.g. \"District GRM Officer\") to one or more duties from the universal duty catalog.")}</p>
                <p class="text-muted small">${__("Each role can be optionally bound to an administrative level — for example, a District GRM Officer is normally bound to the \"District\" level. Duties drive what the role can do in the case lifecycle.")}</p>
              </div>
              <div id="grm-step4-table-wrap"></div>
              <div id="grm-step4-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step4-add">+ ${__("Add Role")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step4-add").on("click", () => this.start_add());

        await this.load_lookups();
        await this.load_and_render_table();
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
            if (duty_rows && duty_rows.length) {
                this.duties = duty_rows.map((d) => ({
                    name: d.name,
                    label: d.label || d.duty_name || d.name,
                }));
            } else {
                this.duties = GRM_DEFAULT_DUTIES.slice();
            }
        } catch (e) {
            this.duties = GRM_DEFAULT_DUTIES.slice();
        }
    }

    async load_and_render_table() {
        try {
            const list_rows = await frappe.db.get_list("GRM Project Role", {
                filters: { project: this.project.name },
                fields: ["name", "role_name", "admin_level", "is_active", "description"],
                limit: 0,
                order_by: "role_name asc",
            });
            // Pull full docs in parallel to get child rows (duties)
            const docs = await Promise.all(
                list_rows.map((r) => frappe.db.get_doc("GRM Project Role", r.name).catch(() => null)),
            );
            this.rows = list_rows.map((r, i) => {
                const doc = docs[i];
                const duties = doc && Array.isArray(doc.duties)
                    ? doc.duties.map((d) => d.duty).filter(Boolean)
                    : [];
                return Object.assign({}, r, { duties });
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step4-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No project roles yet — click \"Add Role\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th>${__("Role Name")}</th>
                <th style="width:180px;">${__("Admin Level")}</th>
                <th>${__("Duties")}</th>
                <th style="width:80px;">${__("Active")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => {
            const duty_labels = (r.duties || [])
                .map((d) => {
                    const found = this.duties.find((x) => x.name === d);
                    return found ? found.label : d;
                })
                .map((s) => frappe.utils.escape_html(s))
                .join(", ");
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td>${frappe.utils.escape_html(r.role_name || "")}</td>
                <td>${frappe.utils.escape_html(r.admin_level || "")}</td>
                <td>${duty_labels}</td>
                <td>${r.is_active ? __("Yes") : __("No")}</td>
                <td>
                  <button class="btn btn-xs btn-default grm-edit-role" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                  <button class="btn btn-xs btn-danger grm-delete-role" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
                </td>
              </tr>
            `;
        }).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-role").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-role").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });
    }

    admin_level_options(selected) {
        const opts = [`<option value="">${__("(none)")}</option>`];
        for (const lvl of this.admin_levels) {
            const sel = lvl.name === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(lvl.name)}"${sel}>${frappe.utils.escape_html(lvl.level_name || lvl.name)}</option>`);
        }
        return opts.join("");
    }

    duty_checkboxes_html(selected_set, prefix) {
        return this.duties
            .map((d) => {
                const checked = selected_set.has(d.name) ? "checked" : "";
                const id = `${prefix}-${d.name.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
                return `
                  <label class="checkbox" style="display:inline-block; margin-right:14px;">
                    <input type="checkbox" class="grm-duty-cb" data-duty="${frappe.utils.escape_html(d.name)}" id="${id}" ${checked}>
                    ${frappe.utils.escape_html(d.label)}
                  </label>
                `;
            })
            .join("");
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
        const role_name = row ? (row.role_name || "") : "";
        const admin_level = row ? (row.admin_level || "") : "";
        const description = row ? (row.description || "") : "";
        const is_active = row ? !!row.is_active : true;
        const selected_duties = new Set((row && row.duties) ? row.duties : []);

        const $w = this.$body.find("#grm-step4-form-wrap").empty();
        $w.html(`
            <div class="grm-step4-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Role") : __("New Role")}</h5>
              <div class="row">
                <div class="col-md-5">
                  <label class="control-label reqd">${__("Role Name")}</label>
                  <input type="text" class="form-control" id="grm-rf-role_name" value="${frappe.utils.escape_html(role_name)}">
                </div>
                <div class="col-md-5">
                  <label class="control-label">${__("Admin Level")}</label>
                  <select class="form-control" id="grm-rf-admin_level">
                    ${this.admin_level_options(admin_level)}
                  </select>
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Active")}</label>
                  <div><label class="checkbox"><input type="checkbox" id="grm-rf-is_active" ${is_active ? "checked" : ""}> ${__("Is Active")}</label></div>
                </div>
              </div>
              <div class="form-group" style="margin-top:8px;">
                <label class="control-label reqd">${__("Duties")}</label>
                <div id="grm-rf-duties">${this.duty_checkboxes_html(selected_duties, "grm-rf-duty")}</div>
                <small class="text-muted">${__("Select at least one duty.")}</small>
              </div>
              <div class="form-group">
                <label class="control-label">${__("Description")}</label>
                <textarea class="form-control" id="grm-rf-description" rows="2">${frappe.utils.escape_html(description)}</textarea>
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-rf-save">${__("Save Role")}</button>
                <button class="btn btn-default btn-sm" id="grm-rf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-rf-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-rf-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step4-form-wrap");
        const role_name = ($w.find("#grm-rf-role_name").val() || "").trim();
        const admin_level = ($w.find("#grm-rf-admin_level").val() || "").trim() || null;
        const description = ($w.find("#grm-rf-description").val() || "").trim();
        const is_active = $w.find("#grm-rf-is_active").is(":checked") ? 1 : 0;
        const duties = [];
        $w.find(".grm-duty-cb:checked").each(function () {
            duties.push($(this).data("duty"));
        });
        return { role_name, admin_level, description, is_active, duties };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!v.role_name) {
            frappe.show_alert({ message: __("Role Name is required."), indicator: "red" });
            return;
        }
        if (!v.duties.length) {
            frappe.show_alert({ message: __("Select at least one duty."), indicator: "red" });
            return;
        }
        // Local uniqueness on role_name within project
        const dup = this.rows.find(
            (x) => x.name !== existing_name && (x.role_name || "").toLowerCase() === v.role_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Role '{0}' already exists for this project.", [v.role_name]), indicator: "red" });
            return;
        }

        try {
            if (existing_name) {
                const doc = await frappe.db.get_doc("GRM Project Role", existing_name);
                doc.role_name = v.role_name;
                doc.admin_level = v.admin_level;
                doc.description = v.description;
                doc.is_active = v.is_active;
                doc.duties = v.duties.map((d) => ({ duty: d }));
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Role updated."), indicator: "green" });
            } else {
                const payload = {
                    doctype: "GRM Project Role",
                    project: this.project.name,
                    role_name: v.role_name,
                    admin_level: v.admin_level,
                    description: v.description,
                    is_active: v.is_active,
                    duties: v.duties.map((d) => ({ duty: d })),
                };
                if (payload.admin_level == null) delete payload.admin_level;
                await frappe.db.insert(payload);
                frappe.show_alert({ message: __("Role created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step4-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(__("Delete role {0}?", [name]), async () => {
            try {
                await frappe.db.delete_doc("GRM Project Role", name);
                frappe.show_alert({ message: __("Role deleted."), indicator: "green" });
                if (this.editing === name) this.editing = null;
                await this.load_and_render_table();
            } catch (e) {
                // frappe surfaces the error
            }
        });
    }

    async save() {
        return true;
    }
}

// ---------------------------------------------------------------------------
// Step 9 — SLAs
// ---------------------------------------------------------------------------
class GRMWizardStep9SLAs {
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
            $w.html(`<p class="text-muted">${__("No administrative levels defined yet — go back to Step 3 to add them.")}</p>`);
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
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);
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
class GRMWizardStep5IssueCategories {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.departments = [];
        this.admin_levels = [];
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
            <div class="grm-step5" style="max-width: 1100px;">
              <div class="grm-step5-intro" style="margin-bottom: 16px;">
                <p>${__("Issue Categories define the kinds of grievances this project handles, plus the default routing (which department picks them up, escalation paths, and confidentiality).")}</p>
                <p class="text-muted small">${__("Each category must be assigned to one of this project's departments. If you haven't created departments yet, set them up in Step 8 first.")}</p>
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
                  ${__("No departments defined yet — go to Step 8 first to add departments, then return to this step.")}
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

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Issue Category", {
                filters: [["GRM Project Link", "project", "=", this.project.name]],
                fields: [
                    "name",
                    "category_name",
                    "label",
                    "abbreviation",
                    "assigned_department",
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
                <th>${__("Name")}</th>
                <th>${__("Label")}</th>
                <th style="width:100px;">${__("Abbrev.")}</th>
                <th>${__("Department")}</th>
                <th style="width:140px;">${__("Confidentiality")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.category_name || "")}</td>
              <td>${frappe.utils.escape_html(r.label || "")}</td>
              <td>${frappe.utils.escape_html(r.abbreviation || "")}</td>
              <td>${frappe.utils.escape_html(dept_label(r.assigned_department))}</td>
              <td>${frappe.utils.escape_html(r.confidentiality_level || "")}</td>
              <td>
                <button class="btn btn-xs btn-default grm-edit-cat" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                <button class="btn btn-xs btn-danger grm-delete-cat" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-cat").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-cat").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
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
            frappe.show_alert({ message: __("Add a department in Step 8 first."), indicator: "red" });
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
                  <label class="control-label reqd">${__("Assigned Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_department">
                    <option value="">${__("(select)")}</option>
                    ${this.department_options(r.assigned_department, false)}
                  </select>
                </div>
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
    }

    read_form() {
        const $w = this.$body.find("#grm-step5-form-wrap");
        const trim = (id) => ($w.find(`#${id}`).val() || "").trim();
        return {
            category_name: trim("grm-cf-category_name"),
            label: trim("grm-cf-label"),
            abbreviation: trim("grm-cf-abbreviation"),
            assigned_department: trim("grm-cf-assigned_department") || null,
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
        if (!v.assigned_department) {
            frappe.show_alert({ message: __("Assigned Department is required."), indicator: "red" });
            return;
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
                doc.assigned_department = v.assigned_department;
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
                    assigned_department: v.assigned_department,
                    confidentiality_level: v.confidentiality_level,
                    redirection_protocol: v.redirection_protocol,
                    grm_project_link: [{ project: this.project.name }],
                };
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
class GRMWizardStep6IssueTypes {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
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
                <td>${frappe.utils.escape_html(r.type_name || "")}</td>
                <td>
                  <button class="btn btn-xs btn-default grm-edit-type" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                  <button class="btn btn-xs btn-danger grm-delete-type" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
                </td>
              </tr>
            `;
        }).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

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
class GRMWizardStep7IssueStatuses {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
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
              <td>${frappe.utils.escape_html(r.status_name || "")}</td>
              <td>${r.initial_status ? __("Yes") : __("No")}</td>
              <td>${r.open_status ? __("Yes") : __("No")}</td>
              <td>${r.final_status ? __("Yes") : __("No")}</td>
              <td>${r.rejected_status ? __("Yes") : __("No")}</td>
              <td>
                <button class="btn btn-xs btn-default grm-edit-status" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                <button class="btn btn-xs btn-danger grm-delete-status" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-status").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-status").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
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
        const $w = this.$body.find("#grm-step8-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No departments yet — click \"Add Department\" to create the first one.")}</p>`);
            return;
        }
        const user_label = (u) => {
            const found = this.users.find((x) => x.name === u);
            return found ? (found.full_name ? `${found.full_name} (${found.name})` : found.name) : (u || "");
        };
        const head = `
            <thead>
              <tr>
                <th>${__("Department")}</th>
                <th>${__("Head")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.department_name || "")}</td>
              <td>${frappe.utils.escape_html(user_label(r.head))}</td>
              <td>
                <button class="btn btn-xs btn-default grm-edit-dept" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                <button class="btn btn-xs btn-danger grm-delete-dept" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-dept").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-dept").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });
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
class GRMWizardStep10CitizenLookups {
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
                <td>${frappe.utils.escape_html(r.age_group || "")}</td>
                <td>
                  <button class="btn btn-xs btn-default grm-edit-age" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                  <button class="btn btn-xs btn-danger grm-delete-age" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
                </td>
              </tr>
            `;
        }).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

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
                <th>${__("Name")}</th>
                <th style="width:120px;">${__("Type")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.group_rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.group_name || "")}</td>
              <td>${frappe.utils.escape_html(r.group_type || "")}</td>
              <td>
                <button class="btn btn-xs btn-default grm-edit-group" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                <button class="btn btn-xs btn-danger grm-delete-group" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-group").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit_group(name);
        });
        $w.find("button.grm-delete-group").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete_group(name);
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
class GRMWizardStep11NotificationTemplates {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.email_templates = [];
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
                <th>${__("Name")}</th>
                <th style="width:170px;">${__("Type")}</th>
                <th style="width:90px;">${__("Active")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.template_name || r.name)}</td>
              <td>${frappe.utils.escape_html(r.template_type || "")}</td>
              <td>${r.active ? __("Yes") : __("No")}</td>
              <td>
                <button class="btn btn-xs btn-default grm-edit-tpl" data-name="${frappe.utils.escape_html(r.name)}">${__("Edit")}</button>
                <button class="btn btn-xs btn-danger grm-delete-tpl" data-name="${frappe.utils.escape_html(r.name)}">${__("Delete")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(`<table class="table table-bordered table-sm">${head}<tbody>${body_rows}</tbody></table>`);

        $w.find("button.grm-edit-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
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
