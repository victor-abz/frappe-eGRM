// ---------------------------------------------------------------------------
// Step 10 — Citizen Lookups (Age Groups + Citizen Groups)
// ---------------------------------------------------------------------------
class GRMWizardStep5CitizenLookups {
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
		this.selected_age = new Set();
		this.selected_group = new Set();
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
                <p>${__(
					"Citizen Lookups are the demographic dropdowns shown on intake forms. They help disaggregate complaint data for reporting."
				)}</p>
                <p class="text-muted small">${__(
					'Age Groups: e.g. "0-17", "18-24", "25-44", "45-64", "65+". Citizen Groups: tags like "Indigenous", "Smallholder Farmer", "Female-headed Household". Group Type 1 vs 2 lets you split groups into two parallel lists if your form needs it.'
				)}</p>
              </div>

              <div class="grm-step10-section" style="margin-bottom: 24px;">
                <h4>${__("Age Groups")}</h4>
                <div id="grm-step10-age-table-wrap"></div>
                <div id="grm-step10-age-form-wrap" style="margin-top: 12px;"></div>
                <div style="margin-top: 12px;">
                  <button class="btn btn-default btn-sm" id="grm-step10-age-add">+ ${__(
						"Add Age Group"
					)}</button>
                </div>
              </div>

              <div class="grm-step10-section">
                <h4>${__("Citizen Groups")}</h4>
                <div id="grm-step10-group-table-wrap"></div>
                <div id="grm-step10-group-form-wrap" style="margin-top: 12px;"></div>
                <div style="margin-top: 12px;">
                  <button class="btn btn-default btn-sm" id="grm-step10-group-add">+ ${__(
						"Add Citizen Group"
					)}</button>
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
			$w.html(
				`<p class="text-muted">${__(
					'No age groups yet — click "Add Age Group" to create the first one.'
				)}</p>`
			);
			return;
		}
		const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Age Group")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
		const body_rows = this.age_rows
			.map((r) => {
				const editing = this.editing_age === r.name;
				if (editing) {
					return `
                  <tr data-name="${frappe.utils.escape_html(r.name)}">
                    <td class="grm-bulk-cell"></td>
                    <td><input type="text" class="form-control input-xs grm-e-age_group" value="${frappe.utils.escape_html(
						r.age_group || ""
					)}"></td>
                    <td>
                      <button class="btn btn-xs btn-primary grm-save-edit-age" data-name="${frappe.utils.escape_html(
							r.name
						)}">${__("Save")}</button>
                      <button class="btn btn-xs btn-default grm-cancel-edit-age">${__(
							"Cancel"
						)}</button>
                    </td>
                  </tr>
                `;
				}
				return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
                <td>${frappe.utils.escape_html(r.age_group || "")}</td>
                <td>
                  <button class="grm-row-action grm-edit-age" title="${__(
						"Edit"
					)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"edit",
					"sm"
				)}</button>
                  <button class="grm-row-action grm-row-action-danger grm-delete-age" title="${__(
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
			grm_render_bulk_toolbar("age") +
				`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
		);

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

		grm_wire_bulk_table($w, {
			selected: this.selected_age,
			row_names: this.age_rows.map((r) => r.name),
			key: "age",
			singular: __("age group"),
			plural: __("age groups"),
			confirm_msg: (n) =>
				n === 1
					? __("Delete the selected age group?")
					: __("Delete {0} selected age groups?", [n]),
			delete_one: (name) => frappe.db.delete_doc("GRM Issue Age Group", name),
			on_done: () => this.load_age_groups(),
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
                <input type="text" class="form-control" id="grm-n-age_group" placeholder="${__(
					"e.g. 18-24"
				)}">
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-n-save-age">${__("Save")}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel-age">${__(
					"Cancel"
				)}</button>
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
			(x) => (x.age_group || "").toLowerCase() === age_group.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Age Group '{0}' already exists for this project.", [age_group]),
				indicator: "red",
			});
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
		const $row = this.$body.find(
			`#grm-step10-age-table-wrap tr[data-name="${CSS.escape(name)}"]`
		);
		const age_group = ($row.find(".grm-e-age_group").val() || "").trim();
		if (!age_group) {
			frappe.show_alert({ message: __("Age Group is required."), indicator: "red" });
			return;
		}
		const dup = this.age_rows.find(
			(x) => x.name !== name && (x.age_group || "").toLowerCase() === age_group.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Age Group '{0}' already exists for this project.", [age_group]),
				indicator: "red",
			});
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
					frappe.show_alert({
						message: __(
							"Could not delete age group — it may still be referenced by issues."
						),
						indicator: "red",
					});
				}
			}
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
			$w.html(
				`<p class="text-muted">${__(
					'No citizen groups yet — click "Add Citizen Group" to create the first one.'
				)}</p>`
			);
			return;
		}
		const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th style="width:120px;">${__("Type")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
		const body_rows = this.group_rows
			.map(
				(r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.group_name || "")}</td>
              <td>${frappe.utils.escape_html(r.group_type || "")}</td>
              <td>
                <button class="grm-row-action grm-edit-group" title="${__(
					"Edit"
				)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"edit",
					"sm"
				)}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-group" title="${__(
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
			grm_render_bulk_toolbar("groups") +
				`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
		);

		$w.find("button.grm-edit-group").on("click", (ev) => {
			const name = $(ev.currentTarget).data("name");
			this.start_edit_group(name);
		});
		$w.find("button.grm-delete-group").on("click", (ev) => {
			const name = $(ev.currentTarget).data("name");
			this.confirm_delete_group(name);
		});

		grm_wire_bulk_table($w, {
			selected: this.selected_group,
			row_names: this.group_rows.map((r) => r.name),
			key: "groups",
			singular: __("citizen group"),
			plural: __("citizen groups"),
			confirm_msg: (n) =>
				n === 1
					? __("Delete the selected citizen group?")
					: __("Delete {0} selected citizen groups?", [n]),
			delete_one: (name) => frappe.db.delete_doc("GRM Issue Citizen Group", name),
			on_done: () => this.load_citizen_groups(),
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
              <h5 style="margin-top:0;">${
					is_edit ? __("Edit Citizen Group") : __("New Citizen Group")
				}</h5>
              <div class="row">
                <div class="col-md-7">
                  <label class="control-label reqd">${__("Group Name")}</label>
                  <input type="text" class="form-control" id="grm-gf-group_name" value="${frappe.utils.escape_html(
						r.group_name || ""
					)}">
                </div>
                <div class="col-md-5">
                  <label class="control-label reqd">${__("Group Type")}</label>
                  <select class="form-control" id="grm-gf-group_type">
                    <option value="1" ${gt === "1" ? "selected" : ""}>${__("1")}</option>
                    <option value="2" ${gt === "2" ? "selected" : ""}>${__("2")}</option>
                  </select>
                  <small class="text-muted">${__(
						"Group Type 1 / 2 separates two parallel demographic dimensions on the intake form."
					)}</small>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-gf-save">${__(
					"Save Group"
				)}</button>
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
			(x) =>
				x.name !== existing_name &&
				(x.group_name || "").toLowerCase() === group_name.toLowerCase()
		);
		if (dup) {
			frappe.show_alert({
				message: __("Citizen Group '{0}' already exists for this project.", [group_name]),
				indicator: "red",
			});
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
					frappe.show_alert({
						message: __("Citizen Group deleted."),
						indicator: "green",
					});
					if (this.editing_group === name) this.editing_group = null;
					await this.load_citizen_groups();
				} catch (e) {
					frappe.show_alert({
						message: __(
							"Could not delete citizen group — it may still be referenced by issues."
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
