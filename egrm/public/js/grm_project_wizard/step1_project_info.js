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
			? `<small class="text-muted">${__(
					"Project code cannot be changed after creation."
			  )}</small>`
			: `<small class="text-warning">${__(
					"Heads up: project code becomes the record name and cannot be changed after save."
			  )}</small>`;

		this.$body.html(`
            <div class="grm-step1-form" style="max-width: 760px;">

              <p class="text-muted">${__(
					"Tell us about your project. The information below will appear across the platform — citizen-facing portals, mobile apps, and notification templates."
				)}</p>

              <h4 class="mt-4">${__("Identity")}</h4>
              <p class="text-muted small">${__(
					"These fields identify your project to staff and citizens."
				)}</p>
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
                <textarea class="form-control" id="grm-f-description" rows="3">${frappe.utils.escape_html(
					p.description || ""
				)}</textarea>
              </div>

              <h4 class="mt-4">${__("Schedule")}</h4>
              <p class="text-muted small">${__(
					"Optional. Used in dashboards and to gate intake outside the project window."
				)}</p>
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
              <p class="text-muted small">${__(
					"How dates, numbers, and currency are formatted across the platform. Default Language drives label translations for citizens and staff."
				)}</p>
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
                      <option value="#,###.##" ${
							(p.number_format || "#,###.##") === "#,###.##" ? "selected" : ""
						}>1,234.56 (en-US)</option>
                      <option value="#.###,##" ${
							p.number_format === "#.###,##" ? "selected" : ""
						}>1.234,56 (de-DE)</option>
                      <option value="# ###.##"  ${
							p.number_format === "# ###.##" ? "selected" : ""
						}>1 234.56 (fr-FR)</option>
                      <option value="#,##,###.##" ${
							p.number_format === "#,##,###.##" ? "selected" : ""
						}>1,23,456.78 (Indic)</option>
                    </select>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Date Format")}</label>
                    <select class="form-control" id="grm-f-date_format">
                      ${["yyyy-mm-dd", "dd-mm-yyyy", "mm-dd-yyyy", "dd/mm/yyyy", "mm/dd/yyyy"]
							.map(
								(fmt) =>
									`<option value="${fmt}" ${
										(p.date_format || "yyyy-mm-dd") === fmt ? "selected" : ""
									}>${fmt}</option>`
							)
							.join("")}
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
              <p class="text-muted small">${__(
					"Project-wide behavioural defaults. You can adjust these later from project settings."
				)}</p>
              <div class="row">
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="control-label">${__("Auto Escalation Days")}</label>
                    <input type="number" min="0" class="form-control" id="grm-f-auto_escalation_days"
                           value="${p.auto_escalation_days != null ? p.auto_escalation_days : 7}">
                    <small class="text-muted">${__(
						"Days before an unresolved issue auto-escalates to the next tier."
					)}</small>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-group">
                    <label class="checkbox">
                      <input type="checkbox" id="grm-f-enable_citizen_feedback" ${
							p.enable_citizen_feedback ? "checked" : ""
						}>
                      ${__("Enable Citizen Feedback")}
                    </label>
                    <small class="text-muted d-block">${__(
						"Allow citizens to rate the resolution of their complaints."
					)}</small>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <label class="checkbox">
                  <input type="checkbox" id="grm-f-is_active" ${
						(p.is_active == null ? 1 : p.is_active) ? "checked" : ""
					}>
                  ${__("Is Active")}
                </label>
                <small class="text-muted d-block">${__(
					"Inactive projects are hidden from intake screens but stay queryable in reports."
				)}</small>
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
				$(parent).html(
					`<input type="text" class="form-control" data-fb="${fieldname}" value="${frappe.utils.escape_html(
						value || ""
					)}">`
				);
			}
		};
		make("grm-f-country-wrap", "country", "Country", p.country);
		make(
			"grm-f-default_language-wrap",
			"default_language",
			"Language",
			p.default_language || "en"
		);
		make("grm-f-currency-wrap", "currency", "Currency", p.currency);
	}

	read_form() {
		const get = (id) => this.$body.find(`#${id}`).val();
		const checked = (id) => (this.$body.find(`#${id}`).is(":checked") ? 1 : 0);
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
		// Review fix B4: defense-in-depth on the permission_query_conditions
		// SQL builder — reject project codes that contain characters that
		// would require escaping ({ ' ; \ [ ]). The server-side builder
		// also escapes backslashes and quotes, but rejecting them at the
		// input layer keeps the entire downstream surface clean.
		if (values.project_code && /[\[\]\\;'"`]/.test(values.project_code)) {
			errors.push(
				__("Project Code may not contain quotes, semicolons, backslashes, or brackets.")
			);
		}
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
				frappe.show_alert({
					message: __("Project created: {0}", [doc.name]),
					indicator: "green",
				});
			} else {
				// Review fix B10: single batched set_value call instead
				// of one round-trip per changed field. Avoids the
				// 1-RPC-per-form-field cost on Step 1 saves where the
				// operator typically tweaks 3-5 fields.
				const changed = {};
				for (const [k, v] of Object.entries(values)) {
					if (k === "project_code") continue; // immutable after creation
					if (this.project[k] !== v) changed[k] = v;
				}
				if (Object.keys(changed).length) {
					await frappe.db.set_value("GRM Project", this.project.name, changed);
					Object.assign(this.project, changed);
				}
			}
			return true;
		} catch (e) {
			// frappe surfaces the error already; nothing more to do
			return false;
		}
	}
}
