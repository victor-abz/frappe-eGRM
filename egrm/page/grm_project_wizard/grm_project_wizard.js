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

    render_step_body() {
        // Step components are registered in Task 3.2; for now, show a placeholder
        // so the scaffold is testable.
        const $body = $("#grm-step-body").empty();
        $body.html(`
            <div class="grm-wizard-placeholder">
              <p class="text-muted">${__("Step component pending — see Task 3.2")}</p>
              ${this.project
                  ? `<p>${__("Project")}: <strong>${frappe.utils.escape_html(this.project.name)}</strong></p>`
                  : `<p>${__("(no project loaded)")}</p>`}
            </div>
        `);
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
        // The actual save logic lives in step components (Task 3.2). For the
        // scaffold, we just step forward — no persistence yet.
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
