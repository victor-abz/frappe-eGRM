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
				try {
					this.on_first_load(this.total);
				} catch (e) {
					/* non-fatal */
				}
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
		if (
			this.total === 0 &&
			!this.search &&
			!this.filter_level &&
			!this.filter_role &&
			!this.filter_status
		) {
			// Empty state: drop search/filter row entirely; the Add panel
			// below this one (Phase D) is where the user starts.
			$ctl.empty();
			$tbl.html(`
              <div class="grm-step9-empty">
                <p class="text-muted">${__(
					"No users assigned to this project yet. Add users below."
				)}</p>
              </div>
            `);
			return;
		}
		this._render_controls($ctl);
		this._render_table($tbl);
	}

	_render_header($hdr) {
		const total_label = this.total === 1 ? __("1 assigned") : __("{0} assigned", [this.total]);
		const summary_bits = [];
		if (this.summary.active) summary_bits.push(__("{0} active", [this.summary.active]));
		if (this.summary.pending) summary_bits.push(__("{0} pending", [this.summary.pending]));
		if (this.summary.draft) summary_bits.push(__("{0} draft", [this.summary.draft]));
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
			.concat(
				(this.project_levels || []).map(
					(l) =>
						`<option value="${frappe.utils.escape_html(l.name)}"${
							l.name === this.filter_level ? " selected" : ""
						}>${frappe.utils.escape_html(l.level_name || l.name)}</option>`
				)
			)
			.join("");
		const role_options = [`<option value="">${__("All roles")}</option>`]
			.concat(
				(this.project_roles || []).map(
					(r) =>
						`<option value="${frappe.utils.escape_html(r.name)}"${
							r.name === this.filter_role ? " selected" : ""
						}>${frappe.utils.escape_html(r.role_name || r.name)}</option>`
				)
			)
			.join("");
		const status_values = ["Draft", "Pending Activation", "Activated", "Suspended", "Expired"];
		const status_options = [`<option value="">${__("All statuses")}</option>`]
			.concat(
				status_values.map(
					(s) =>
						`<option value="${s}"${s === this.filter_status ? " selected" : ""}>${__(
							s
						)}</option>`
				)
			)
			.join("");
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
              <button class="btn btn-default btn-xs grm-step9-prev" ${
					this.start === 0 ? "disabled" : ""
				}>${__("Prev")}</button>
              <span class="grm-step9-pager-label">${__("{0}-{1} of {2}", [
					range_from,
					range_to,
					this.total,
				])}</span>
              <button class="btn btn-default btn-xs grm-step9-next" ${
					page_idx >= page_total ? "disabled" : ""
				}>${__("Next")}</button>
            </div>
          </div>
          ${grm_render_bulk_toolbar("step9_users")}
          <div class="grm-step9-bulk-extras" hidden>
            <button class="btn btn-xs btn-default grm-step9-bulk-role">${__(
				"Change role"
			)}</button>
            <button class="btn btn-xs btn-default grm-step9-bulk-status">${__(
				"Change status"
			)}</button>
            <button class="btn btn-xs btn-default grm-step9-bulk-deactivate">${__(
				"Deactivate"
			)}</button>
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
		$ctl.find(".grm-step9-bulk-status").on("click", () =>
			this._bulk_change("activation_status")
		);
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
			confirm_msg: (n) =>
				n === 1
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
		this.$body.on("change.grm-step9-extras", ".grm-bulk-row-check, .grm-bulk-all", () =>
			setTimeout(sync_extras, 0)
		);
		this.$body.on("click.grm-step9-extras", ".grm-bulk-clear", () =>
			setTimeout(sync_extras, 0)
		);
		sync_extras();
	}

	_render_row(r) {
		const name_email = `
          <div class="grm-step9-name">${frappe.utils.escape_html(
				r.user_full_name || r.user || ""
			)}</div>
          <div class="grm-step9-email text-muted">${frappe.utils.escape_html(
				r.user_email || ""
			)}</div>
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
			try {
				this._popover.remove();
			} catch (e) {
				/* ignore */
			}
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
                ${opts
					.map(
						(o) =>
							`<option value="${o}"${o === current_value ? " selected" : ""}>${__(
								o
							)}</option>`
					)
					.join("")}
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
		$pop.html(
			`<label class="grm-pill-pop-label">${ctl_meta.label}</label><div class="grm-step9-pop-ctrl"></div>`
		);
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
			$(parent).html(
				`<input type="text" class="form-control form-control-sm" value="${frappe.utils.escape_html(
					current_value
				)}">`
			);
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
			const value = await this._prompt_select(__("Change status"), [
				"Draft",
				"Pending Activation",
				"Activated",
				"Suspended",
			]);
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
				fields: [
					{
						fieldname: "value",
						fieldtype: "Select",
						label: __("Value"),
						options: options.join("\n"),
						reqd: 1,
					},
				],
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
				fields: [
					{
						fieldname: "value",
						fieldtype: "Link",
						label: meta.label,
						options: meta.doctype,
						get_query: meta.get_query,
						reqd: 1,
					},
				],
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
