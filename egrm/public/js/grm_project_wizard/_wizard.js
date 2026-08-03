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
			const cls =
				i < this.current_step ? "done" : i === this.current_step ? "active" : "pending";
			const title = `${i}. ${STEP_TITLES[i] || ""}`;
			const aria_label = `${__("Go to step")} ${title}`;
			const aria_current = i === this.current_step ? 'aria-current="step"' : "";
			const disabled =
				!has_project && i !== this.current_step ? 'disabled aria-disabled="true"' : "";
			$s.append(
				`<button type="button" class="grm-step ${cls}" data-step="${i}" ` +
					`title="${frappe.utils.escape_html(title)}" ` +
					`aria-label="${frappe.utils.escape_html(aria_label)}" ` +
					`${aria_current} ${disabled}></button>`
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
			1: GRMWizardStep1ProjectInfo, // 1 → Project Information
			2: GRMWizardStep2AdminUnits, // 2 → Admin Levels & Regions
			3: GRMWizardStep7ProjectRoles, // 3 → User Types  (was 7)
			4: GRMWizardStep8Departments, // 4 → Departments (was 8)
			5: GRMWizardStep3IssueCategories, // 5 → Categories  (was 3, needs roles+depts)
			6: GRMWizardStep4IssueTypes, // 6 → Issue Types (was 4)
			7: GRMWizardStep5CitizenLookups, // 7 → Citizen Groups (was 5)
			8: GRMWizardStep6NotificationTemplates, // 8 → Notif Templates (was 6)
			9: GRMWizardStep9Users, // 9 → Users
			10: GRMWizardStep10Routing, // 10 → Issue Routing
			11: GRMWizardStep11SLAs, // 11 → SLAs
			12: GRMWizardStep12IssueStatuses, // 12 → Issue Statuses
			13: GRMWizardStep13Activate, // 13 → Activate
		};
		return map[n] || null;
	}

	render_step_body() {
		const $body = $("#grm-step-body").empty();
		// Wipe any page-header primary/secondary actions from the previous step
		// so they never leak across steps. Steps that need actions render them
		// inside the form body (see grm-step7-footer in Step 3 for the pattern).
		if (this.page) {
			try {
				this.page.clear_primary_action && this.page.clear_primary_action();
			} catch (e) {
				/* ignore */
			}
			try {
				this.page.clear_secondary_action && this.page.clear_secondary_action();
			} catch (e) {
				/* ignore */
			}
		}
		const StepClass = this.step_class(this.current_step);
		if (!StepClass) {
			$body.html(`
                <div class="grm-wizard-placeholder">
                  <p class="text-muted">${__(
						"Step component pending — see plan tasks 3.2-B / 3.2-C"
					)}</p>
                  ${
						this.project
							? `<p>${__("Project")}: <strong>${frappe.utils.escape_html(
									this.project.name
							  )}</strong></p>`
							: `<p>${__("(no project loaded)")}</p>`
					}
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
			this.project ? `${this.current_step} / ${TOTAL_STEPS}` : __("Save Step 1 to begin")
		);
	}

	async advance() {
		// Review fix B9: double-submit guard on the wizard's primary
		// forward action (Save & Next). Without this, a fast double
		// click can fire two save() coroutines in parallel and corrupt
		// state on the per-step save path.
		if (this._advancing) return;
		this._advancing = true;
		try {
			if (this.step_instance && typeof this.step_instance.save === "function") {
				const ok = await this.step_instance.save();
				if (!ok) return;
			}
			if (this.current_step < TOTAL_STEPS) {
				this.goto_step(this.current_step + 1);
			} else {
				await this.complete_wizard();
			}
		} finally {
			this._advancing = false;
		}
	}

	goto_step(n) {
		if (n < 1 || n > TOTAL_STEPS) return;
		// Review fix B11: if the current step reports unsaved changes,
		// confirm before discarding them. Steps that don't implement
		// ``is_dirty()`` are treated as clean (no prompt) — that
		// preserves backward compatibility for the steps that haven't
		// been migrated yet.
		const step = this.step_instance;
		const isDirty = step && typeof step.is_dirty === "function" && step.is_dirty();
		if (isDirty) {
			frappe.confirm(
				__("Discard unsaved changes?"),
				() => {
					this._do_goto_step(n);
				},
				() => {
					/* cancel: stay on the current step */
				}
			);
			return;
		}
		this._do_goto_step(n);
	}

	_do_goto_step(n) {
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
			frappe.set_route("Workspaces", "eGRM");
		} catch (e) {
			// frappe.call already shows the error; nothing to do
		}
	}
}
