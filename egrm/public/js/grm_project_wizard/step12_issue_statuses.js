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
                <p>${__(
					"Issue Statuses define the lifecycle of a case — from intake to closure. Mark exactly one status as the Initial status (the entry point) and at least one as Final (resolution / closure)."
				)}</p>
                <p class="text-muted small">${__(
					'Common pattern: "New" (initial, open) → "In Progress" (open) → "Resolved" (final, open) → "Closed" (final). Use "Rejected" for cases dismissed during review.'
				)}</p>
              </div>
              <div id="grm-step7-table-wrap"></div>
              <div id="grm-step7-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step7-add">+ ${__(
					"Add Status"
				)}</button>
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
				fields: [
					"name",
					"status_name",
					"initial_status",
					"open_status",
					"final_status",
					"rejected_status",
				],
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
						message: __("Seeded {0} default statuses. Tweak as needed.", [
							r.message.count,
						]),
						indicator: "green",
					});
				}
				this.rows = await frappe.db.get_list("GRM Issue Status", {
					filters: [["GRM Project Link", "project", "=", this.project.name]],
					fields: [
						"name",
						"status_name",
						"initial_status",
						"open_status",
						"final_status",
						"rejected_status",
					],
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
			$w.html(
				`<p class="text-muted">${__(
					'No statuses yet — click "Add Status" to create the first one.'
				)}</p>`
			);
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
		const body_rows = this.rows
			.map(
				(r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.status_name || "")}</td>
              <td>${r.initial_status ? __("Yes") : __("No")}</td>
              <td>${r.open_status ? __("Yes") : __("No")}</td>
              <td>${r.final_status ? __("Yes") : __("No")}</td>
              <td>${r.rejected_status ? __("Yes") : __("No")}</td>
              <td>
                <button class="grm-row-action grm-edit-status" title="${__(
					"Edit"
				)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"edit",
					"sm"
				)}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-status" title="${__(
					"Delete"
				)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"close",
					"sm"
				)}</button>
              </td>
            </tr>
        `
			)
			.join("");
		$w.html(
			grm_render_bulk_toolbar("statuses") +
				`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
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
			confirm_msg: (n) =>
				n === 1
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
                <input type="text" class="form-control" id="grm-sf-status_name" value="${frappe.utils.escape_html(
					r.status_name || ""
				)}">
              </div>
              <div class="row">
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-initial_status" ${
						r.initial_status ? "checked" : ""
					}> ${__("Initial Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-open_status" ${
						r.open_status ? "checked" : ""
					}> ${__("Open Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-final_status" ${
						r.final_status ? "checked" : ""
					}> ${__("Final Status")}</label>
                </div>
                <div class="col-md-3">
                  <label class="checkbox"><input type="checkbox" id="grm-sf-rejected_status" ${
						r.rejected_status ? "checked" : ""
					}> ${__("Rejected Status")}</label>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-sf-save">${__(
					"Save Status"
				)}</button>
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
		const checked = (id) => ($w.find(`#${id}`).is(":checked") ? 1 : 0);
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
			(x) =>
				x.name !== existing_name &&
				(x.status_name || "").toLowerCase() === v.status_name.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Status '{0}' already exists for this project.", [v.status_name]),
				indicator: "red",
			});
			return;
		}
		// Soft warning: if marking initial and another row already is initial, advise the user.
		if (v.initial_status) {
			const other_initial = this.rows.find(
				(x) => x.name !== existing_name && x.initial_status
			);
			if (other_initial) {
				frappe.show_alert({
					message: __(
						"Heads up: '{0}' is already marked Initial — only one should be the entry point.",
						[other_initial.status_name || other_initial.name]
					),
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
					frappe.show_alert({
						message: __(
							"Could not delete status — it may still be referenced by issues."
						),
						indicator: "red",
					});
				}
			}
		);
	}

	async save() {
		if (this.rows && this.rows.length > 0) {
			const has_initial = this.rows.some((r) => r.initial_status);
			const has_final = this.rows.some((r) => r.final_status);
			if (!has_initial || !has_final) {
				const missing = [];
				if (!has_initial) missing.push(__("an Initial status"));
				if (!has_final) missing.push(__("a Final status"));
				frappe.show_alert({
					message: __("Please define {0} before continuing.", [
						missing.join(__(" and ")),
					]),
					indicator: "red",
				});
				return false;
			}
		}
		return true;
	}
}
