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
                <p>${__(
					'Issue Types complement categories — they describe the broader nature of a complaint (e.g. "Service Quality", "Compensation", "Environmental").'
				)}</p>
                <p class="text-muted small">${__(
					"Types are project-scoped. Pick a small, stable list — citizens see these on intake forms."
				)}</p>
              </div>
              <div id="grm-step6-table-wrap"></div>
              <div id="grm-step6-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step6-add">+ ${__(
					"Add Type"
				)}</button>
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
			$w.html(
				`<p class="text-muted">${__(
					'No issue types yet — click "Add Type" to create the first one.'
				)}</p>`
			);
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
		const body_rows = this.rows
			.map((r) => {
				const editing = this.editing === r.name;
				if (editing) {
					return `
                  <tr data-name="${frappe.utils.escape_html(r.name)}">
                    <td class="grm-bulk-cell"></td>
                    <td><input type="text" class="form-control input-xs grm-e-type_name" value="${frappe.utils.escape_html(
						r.type_name || ""
					)}"></td>
                    <td>
                      <button class="btn btn-xs btn-primary grm-save-edit-type" data-name="${frappe.utils.escape_html(
							r.name
						)}">${__("Save")}</button>
                      <button class="btn btn-xs btn-default grm-cancel-edit-type">${__(
							"Cancel"
						)}</button>
                    </td>
                  </tr>
                `;
				}
				return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
                <td>${frappe.utils.escape_html(r.type_name || "")}</td>
                <td>
                  <button class="grm-row-action grm-edit-type" title="${__(
						"Edit"
					)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"edit",
					"sm"
				)}</button>
                  <button class="grm-row-action grm-row-action-danger grm-delete-type" title="${__(
						"Delete"
					)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"close",
					"sm"
				)}</button>
                </td>
              </tr>
            `;
			})
			.join("");
		$w.html(
			grm_render_bulk_toolbar("types") +
				`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
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
			confirm_msg: (n) =>
				n === 1
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
                <button class="btn btn-primary btn-sm" id="grm-n-save-type">${__(
					"Save Type"
				)}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel-type">${__(
					"Cancel"
				)}</button>
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
			(x) => (x.type_name || "").toLowerCase() === type_name.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Type '{0}' already exists for this project.", [type_name]),
				indicator: "red",
			});
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
			(x) => x.name !== name && (x.type_name || "").toLowerCase() === type_name.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Type '{0}' already exists for this project.", [type_name]),
				indicator: "red",
			});
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
					frappe.show_alert({
						message: __(
							"Could not delete type — it may still be referenced by issues."
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
