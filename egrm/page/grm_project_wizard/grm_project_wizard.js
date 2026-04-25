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
            12: GRMWizardStep12Activate,
            // Steps 3-11 will be assigned in subsequent tasks
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
