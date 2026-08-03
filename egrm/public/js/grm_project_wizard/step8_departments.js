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
                <p>${__(
					"Departments are the organizational units that handle issues — typical examples: Customer Service, Engineering, Compliance, Field Operations."
				)}</p>
                <p class="text-muted small">${__(
					"Each department can have a head — a user who oversees issues routed there. Step 5 (Categories) assigns issues to one of these departments by default."
				)}</p>
              </div>
              <div id="grm-step8-table-wrap"></div>
              <div id="grm-step8-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step8-add">+ ${__(
					"Add Department"
				)}</button>
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
			$w.html(
				`<p class="text-muted">${__(
					'No departments yet — click "Add Department" to create the first one.'
				)}</p>`
			);
			this.selected = new Set();
			return;
		}
		if (!this.selected) this.selected = new Set();
		const existing = new Set(this.rows.map((r) => r.name));
		for (const n of [...this.selected]) if (!existing.has(n)) this.selected.delete(n);

		const esc = frappe.utils.escape_html;
		const user_label = (u) => {
			const found = (this.users || []).find((x) => x.name === u);
			return found
				? found.full_name
					? `${found.full_name} (${found.name})`
					: found.name
				: u || "";
		};
		$w.html(`
            <div class="grm-bulk-actions" data-grm-bulk-for="dept" hidden>
              <span class="grm-bulk-count"></span>
              <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__(
					"Delete"
				)}</button>
              <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__(
					"Clear selection"
				)}</button>
            </div>
            <div class="form-grid-container column-limit-reached">
              <div class="form-grid grm-dept-table">
                <div class="grid-heading-row">
                  <div class="grid-row">
                    <div class="data-row row m-0">
                      <div class="row-check sortable-handle col">
                        <input type="checkbox" class="grid-row-check grm-row-check-all" tabindex="-1">
                      </div>
                      <div class="row-index sortable-handle grid-static-col col"><span>${__(
							"No."
						)}</span></div>
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
			const $row = $(
				`<div class="grid-row" data-name="${esc(
					r.name
				)}"><div class="data-row row m-0"></div></div>`
			).appendTo($rows);
			const $dr = $row.find(".data-row");

			// Structural cols (row-check is functional; row-index decorative)
			const checked = this.selected.has(r.name) ? "checked" : "";
			$(
				`<div class="row-check sortable-handle col"><input type="checkbox" class="grid-row-check" tabindex="-1" ${checked}></div>`
			).appendTo($dr);
			$(
				`<div class="row-index sortable-handle grid-static-col col"><span>${
					idx + 1
				}</span></div>`
			).appendTo($dr);

			// Department (read-only static)
			$(
				`<div class="col grid-static-col col-xs-5" data-fieldname="department_name"><div class="static-area ellipsis"></div></div>`
			)
				.appendTo($dr)
				.find(".static-area")
				.text(r.department_name || "");

			// Head — click-to-edit cell (User Link dialog)
			const $head = $(
				`<div class="col grid-static-col col-xs-5 grm-edit-cell" data-fieldname="head"><div class="static-area ellipsis"></div></div>`
			).appendTo($dr);
			const $hsa = $head.find(".static-area");
			const label = user_label(r.head);
			if (label) $hsa.text(label);
			else $hsa.html(`<span class="grm-edit-placeholder">${__("Click to set")}</span>`);
			$head.on("click", () => this.show_head_dialog(r));

			// Actions — discrete pencil + x icons (col-xs-2 → ~100px flex)
			const $act = $(
				`<div class="col grid-static-col col-xs-2 text-right" data-fieldname="_actions"></div>`
			).appendTo($dr);
			$(
				`<button class="grm-row-action grm-edit-dept" title="${__(
					"Edit"
				)}">${frappe.utils.icon("edit", "sm")}</button>`
			)
				.appendTo($act)
				.attr("data-name", r.name)
				.on("click", (e) => {
					e.stopPropagation();
					this.start_edit(r.name);
				});
			$(
				`<button class="grm-row-action grm-row-action-danger grm-delete-dept" title="${__(
					"Delete"
				)}">${frappe.utils.icon("close", "sm")}</button>`
			)
				.appendTo($act)
				.attr("data-name", r.name)
				.on("click", (e) => {
					e.stopPropagation();
					this.confirm_delete(r.name);
				});
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
		$w.off("click.grm-bulk").on("click.grm-bulk", ".grm-bulk-delete", () =>
			this.confirm_bulk_delete()
		);
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
			n === 0 ? "" : n === 1 ? __("1 row selected") : __("{0} rows selected", [n])
		);
		$bar.find(".grm-bulk-delete").text(
			n === 1 ? __("Delete row") : __("Delete {0} rows", [n])
		);
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
		const msg =
			names.length === 1
				? __("Delete department {0}?", [names[0]])
				: __("Delete {0} selected departments?", [names.length]);
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
				message: __(
					"Could not delete {0} department(s) — they may still be referenced by categories or issues.",
					[errs.length]
				),
				indicator: "red",
			});
		} else {
			frappe.show_alert({
				message: __("{0} department(s) deleted.", [names.length]),
				indicator: "green",
			});
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
					description: __(
						"Optional. The user who oversees issues routed to this department."
					),
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
			opts.push(
				`<option value="${frappe.utils.escape_html(
					u.name
				)}"${sel}>${frappe.utils.escape_html(display)}</option>`
			);
		}
		if (selected && !saw_selected) {
			opts.push(
				`<option value="${frappe.utils.escape_html(
					selected
				)}" selected>${frappe.utils.escape_html(selected)}</option>`
			);
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
              <h5 style="margin-top:0;">${
					is_edit ? __("Edit Department") : __("New Department")
				}</h5>
              <div class="row">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Department Name")}</label>
                  <input type="text" class="form-control" id="grm-df-department_name" value="${frappe.utils.escape_html(
						r.department_name || ""
					)}">
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
                <button class="btn btn-primary btn-sm" id="grm-df-save">${__(
					"Save Department"
				)}</button>
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
			(x) =>
				x.name !== existing_name &&
				(x.department_name || "").toLowerCase() === v.department_name.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Department '{0}' already exists for this project.", [
					v.department_name,
				]),
				indicator: "red",
			});
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
					frappe.show_alert({
						message: __(
							"Could not delete department — it may still be referenced by categories or issues."
						),
						indicator: "red",
					});
				}
			}
		);
	}

	async save() {
		return true;
	}
}
