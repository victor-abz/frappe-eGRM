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
		this.rows = []; // [{name, role_name, admin_level, is_active, duties: Set<string>}]
		this.admin_levels = []; // [{name, level_name}]
		this.duties = []; // [{name, label, lifecycle_phase}]
		this.render();
	}

	async render() {
		if (!this.project) {
			this.$body.html(
				`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`
			);
			return;
		}
		this.$body.html(`
            <div class="grm-step7-roles">
              <div class="grm-step7-intro" style="margin-bottom: 12px;">
                <p>${__(
					'Define the project\'s user types (e.g. "District GRM Officer") and tick the duties each role performs in the case lifecycle.'
				)}</p>
                <p class="text-muted small">${__(
					"Tick a checkbox to grant the role that duty — saves immediately."
				)}</p>
              </div>
              <div class="grm-perm-engine table-responsive" style="min-height: 120px;"></div>
              <div class="grm-step7-footer" style="margin-top: 12px; display: flex; gap: 8px; align-items: center;">
                <button type="button" id="grm-step7-add-role" class="btn btn-default btn-sm">+ ${__(
					"Add Role"
				)}</button>
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
			try {
				this.wizard.page.clear_primary_action && this.wizard.page.clear_primary_action();
			} catch (e) {
				/* ignore */
			}
			try {
				this.wizard.page.clear_secondary_action &&
					this.wizard.page.clear_secondary_action();
			} catch (e) {
				/* ignore */
			}
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
			this.duties =
				duty_rows && duty_rows.length
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
				list_rows.map((r) =>
					frappe.db.get_doc("GRM Project Role", r.name).catch(() => null)
				)
			);
			this.rows = list_rows.map((r, i) => {
				const doc = docs[i];
				const duties = new Set(
					doc && Array.isArray(doc.duties)
						? doc.duties.map((d) => d.duty).filter(Boolean)
						: []
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
                <p class="text-muted">${__(
					'No roles yet — click "+ Add Role" below to create the first one.'
				)}</p>
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
		const duty_heads = (this.duties || [])
			.map((d) => {
				const tip = d.lifecycle_phase ? `title="${esc(d.lifecycle_phase)}"` : "";
				return `
                <div class="col grid-static-col text-center grm-duty-col" ${tip} data-fieldname="duty:${esc(
					d.name
				)}" data-fieldtype="Check">
                  <div class="static-area ellipsis">${esc(d.label)}</div>
                </div>`;
			})
			.join("");

		this.body.html(`
            <div class="grm-bulk-actions" data-grm-bulk-for="perm" hidden>
              <span class="grm-bulk-count"></span>
              <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__(
					"Delete"
				)}</button>
              <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__(
					"Clear selection"
				)}</button>
            </div>
            <div class="form-grid-container column-limit-reached">
              <div class="form-grid grm-perm-table">
                <div class="grid-heading-row">
                  <div class="grid-row">
                    <div class="data-row row m-0">
                      <div class="row-check sortable-handle col">
                        <input type="checkbox" class="grid-row-check grm-row-check-all" tabindex="-1">
                      </div>
                      <div class="row-index sortable-handle grid-static-col col"><span>${__(
							"No."
						)}</span></div>
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
			$(
				`<div class="row-check sortable-handle col"><input type="checkbox" class="grid-row-check" tabindex="-1" ${checked}></div>`
			).appendTo($dr);
			$(
				`<div class="row-index sortable-handle grid-static-col col"><span>${
					idx + 1
				}</span></div>`
			).appendTo($dr);
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
		this.body
			.off("click.grm-bulk")
			.on("click.grm-bulk", ".grm-bulk-delete", () => this.confirm_bulk_delete());
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
			n === 0 ? "" : n === 1 ? __("1 row selected") : __("{0} rows selected", [n])
		);
		$bar.find(".grm-bulk-delete").text(
			n === 1 ? __("Delete row") : __("Delete {0} rows", [n])
		);
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
		const msg =
			names.length === 1
				? __("Delete role {0}?", [names[0]])
				: __("Delete {0} selected roles?", [names.length]);
		const proceed = await new Promise((res) =>
			frappe.confirm(
				msg,
				() => res(true),
				() => res(false)
			)
		);
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
				message: __("Could not delete {0} role(s) — they may still be referenced.", [
					errs.length,
				]),
				indicator: "red",
			});
		} else {
			frappe.show_alert({
				message: __("{0} role(s) deleted.", [names.length]),
				indicator: "green",
			});
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
		return found ? found.level_name || value : value;
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
            <div class="col grid-static-col text-center grm-duty-cell" data-fieldname="duty:${frappe.utils.escape_html(
				duty.name
			)}" data-fieldtype="Check">
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
		const $col = $(
			`<div class="col grid-static-col text-right" data-fieldname="_actions"></div>`
		).appendTo($dr);
		$(
			`<button class="grm-row-action grm-row-action-danger btn-remove-perm" title="${__(
				"Delete role"
			)}">${frappe.utils.icon("close", "sm")}</button>`
		)
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
		// Build duty checkbox markup so the operator MUST pick at least one
		// duty at create-time. Previously the dialog created the role with no
		// duties and the server defaulted to ``["Supervise"]`` to satisfy the
		// doctype validator — that polluted every role with an unintended
		// duty. The right design is to require explicit duty selection here.
		const duties = this.duties || [];
		const fields = [
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
				description: __(
					"Bind this role to an admin level (e.g. District). Leave blank for project-wide roles."
				),
			},
			{
				fieldtype: "Section Break",
				label: __("Duties"),
				description: __(
					"Tick the duties this role performs in the case lifecycle. At least one is required."
				),
			},
		];
		for (const duty of duties) {
			fields.push({
				fieldtype: "Check",
				label: duty.label || duty.name,
				fieldname: `duty__${duty.name}`,
				default: 0,
			});
		}
		const d = new frappe.ui.Dialog({
			title: __("Add User Type"),
			fields,
		});
		d.set_primary_action(__("Add"), () => {
			const args = d.get_values() || {};
			if (!args.role_name) return;
			const selected = duties
				.map((duty) => (args[`duty__${duty.name}`] ? duty.name : null))
				.filter(Boolean);
			if (!selected.length) {
				frappe.msgprint({
					title: __("Pick at least one duty"),
					message: __("A role must have at least one duty assigned."),
					indicator: "orange",
				});
				return;
			}
			frappe.call({
				method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_add",
				args: {
					project: this.project.name,
					role_name: args.role_name,
					admin_level: args.admin_level || null,
					duties: JSON.stringify(selected),
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
			}
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
