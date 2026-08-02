// ---------------------------------------------------------------------------
// Step 5 — Issue Categories & Routing
// ---------------------------------------------------------------------------
class GRMWizardStep3IssueCategories {
	constructor($body, project, wizard) {
		this.$body = $body;
		this.project = project;
		this.wizard = wizard;
		this.rows = [];
		this.departments = [];
		this.project_roles = [];
		this.admin_levels = [];
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
            <div class="grm-step5" style="max-width: 1100px;">
              <div class="grm-step5-intro" style="margin-bottom: 16px;">
                <p>${__(
					"Issue Categories define the kinds of grievances this project handles, plus the default routing (which department or role picks them up, escalation paths, and confidentiality)."
				)}</p>
                <p class="text-muted small">${__(
					"Each category routes to either a Department (organisational) or a Role (cross-department workflow). Step 10 lets you review and re-assign at the end."
				)}</p>
              </div>
              <div id="grm-step5-notice"></div>
              <div id="grm-step5-table-wrap"></div>
              <div id="grm-step5-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step5-add" disabled>+ ${__(
					"Add Category"
				)}</button>
              </div>
            </div>
        `);
		this.$body.find("#grm-step5-add").on("click", () => this.start_add());
		await this.load_lookups();
		await this.load_and_render_table();
		this.render_notice();
	}

	render_notice() {
		const $n = this.$body.find("#grm-step5-notice").empty();
		if (!this.departments.length) {
			$n.html(`
                <div class="alert alert-warning" style="margin-bottom:12px;">
                  ${__(
						"No departments defined yet — go back to Step 4 first to add departments, then return to this step."
					)}
                </div>
            `);
			this.$body.find("#grm-step5-add").prop("disabled", true);
		} else {
			this.$body.find("#grm-step5-add").prop("disabled", false);
		}
	}

	async load_lookups() {
		const project = this.project.name;
		try {
			this.departments = await frappe.db.get_list("GRM Issue Department", {
				filters: [["GRM Project Link", "project", "=", project]],
				fields: ["name", "department_name"],
				limit: 0,
				order_by: "department_name asc",
			});
		} catch (e) {
			this.departments = [];
		}
		try {
			this.project_roles = await frappe.db.get_list("GRM Project Role", {
				filters: { project, is_active: 1 },
				fields: ["name", "role_name"],
				limit: 0,
				order_by: "role_name asc",
			});
		} catch (e) {
			this.project_roles = [];
		}
		try {
			this.admin_levels = await frappe.db.get_list("GRM Administrative Level Type", {
				filters: { project },
				fields: ["name", "level_name"],
				limit: 0,
				order_by: "level_order asc",
			});
		} catch (e) {
			this.admin_levels = [];
		}
	}

	role_options(selected) {
		const opts = [`<option value="">${__("(select)")}</option>`];
		for (const r of this.project_roles || []) {
			const sel = r.name === selected ? " selected" : "";
			opts.push(
				`<option value="${frappe.utils.escape_html(
					r.name
				)}"${sel}>${frappe.utils.escape_html(r.role_name || r.name)}</option>`
			);
		}
		return opts.join("");
	}

	role_label(name) {
		const r = (this.project_roles || []).find((x) => x.name === name);
		return r ? r.role_name || r.name : name || "";
	}

	async load_and_render_table() {
		try {
			this.rows = await frappe.db.get_list("GRM Issue Category", {
				filters: [["GRM Project Link", "project", "=", this.project.name]],
				fields: [
					"name",
					"category_name",
					"label",
					"abbreviation",
					"routing_target_type",
					"assigned_department",
					"assigned_role",
					"assigned_appeal_department",
					"assigned_escalation_department",
					"confidentiality_level",
					"redirection_protocol",
					"administrative_level",
				],
				limit: 0,
				order_by: "category_name asc",
			});
		} catch (e) {
			this.rows = [];
		}
		this.render_table();
	}

	render_table() {
		const $w = this.$body.find("#grm-step5-table-wrap").empty();
		if (!this.rows.length) {
			$w.html(
				`<p class="text-muted">${__(
					'No categories yet — click "Add Category" to create the first one.'
				)}</p>`
			);
			return;
		}
		const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th>${__("Label")}</th>
                <th style="width:100px;">${__("Abbrev.")}</th>
                <th>${__("Routes To")}</th>
                <th style="width:140px;">${__("Confidentiality")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
		const body_rows = this.rows
			.map((r) => {
				const is_role = r.routing_target_type === "Role" && r.assigned_role;
				const target_label = is_role
					? this.role_label(r.assigned_role)
					: `<span class="text-danger">${__("Needs role — edit to fix")}</span>`;
				const badge_class = is_role ? "badge-info" : "badge-warning";
				const target_kind = is_role ? __("Role") : __("Unrouted");
				return `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.category_name || "")}</td>
              <td>${frappe.utils.escape_html(r.label || "")}</td>
              <td>${frappe.utils.escape_html(r.abbreviation || "")}</td>
              <td><span class="badge ${badge_class}">${target_kind}</span> ${frappe.utils.escape_html(
					target_label
				)}</td>
              <td>${frappe.utils.escape_html(r.confidentiality_level || "")}</td>
              <td>
                <button class="grm-row-action grm-edit-cat" title="${__(
					"Edit"
				)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"edit",
					"sm"
				)}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-cat" title="${__(
					"Delete"
				)}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon(
					"close",
					"sm"
				)}</button>
              </td>
            </tr>`;
			})
			.join("");
		$w.html(
			grm_render_bulk_toolbar("categories") +
				`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
		);

		$w.find("button.grm-edit-cat").on("click", (ev) => {
			const name = $(ev.currentTarget).data("name");
			this.start_edit(name);
		});
		$w.find("button.grm-delete-cat").on("click", (ev) => {
			const name = $(ev.currentTarget).data("name");
			this.confirm_delete(name);
		});

		grm_wire_bulk_table($w, {
			selected: this.selected,
			row_names: this.rows.map((r) => r.name),
			key: "categories",
			singular: __("category"),
			plural: __("categories"),
			confirm_msg: (n) =>
				n === 1
					? __("Delete the selected category?")
					: __("Delete {0} selected categories?", [n]),
			delete_one: (name) => frappe.db.delete_doc("GRM Issue Category", name),
			on_done: () => this.load_and_render_table(),
		});
	}

	department_options(selected, include_blank) {
		const opts = [];
		if (include_blank) opts.push(`<option value="">${__("(none)")}</option>`);
		for (const d of this.departments) {
			const sel = d.name === selected ? " selected" : "";
			opts.push(
				`<option value="${frappe.utils.escape_html(
					d.name
				)}"${sel}>${frappe.utils.escape_html(d.department_name || d.name)}</option>`
			);
		}
		return opts.join("");
	}

	admin_level_options(selected) {
		const opts = [`<option value="">${__("(none)")}</option>`];
		for (const lvl of this.admin_levels) {
			const sel = lvl.name === selected ? " selected" : "";
			opts.push(
				`<option value="${frappe.utils.escape_html(
					lvl.name
				)}"${sel}>${frappe.utils.escape_html(lvl.level_name || lvl.name)}</option>`
			);
		}
		return opts.join("");
	}

	start_add() {
		if (!this.departments.length) {
			frappe.show_alert({
				message: __("Add a department in Step 4 first."),
				indicator: "red",
			});
			return;
		}
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
		const conf = r.confidentiality_level || "Public";
		const redir = r.redirection_protocol != null ? String(r.redirection_protocol) : "0";
		const $w = this.$body.find("#grm-step5-form-wrap").empty();
		$w.html(`
            <div class="grm-step5-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Category") : __("New Category")}</h5>
              <div class="row">
                <div class="col-md-4">
                  <label class="control-label reqd">${__("Category Name")}</label>
                  <input type="text" class="form-control" id="grm-cf-category_name" value="${frappe.utils.escape_html(
						r.category_name || ""
					)}" ${is_edit ? "disabled" : ""}>
                  ${
						is_edit
							? `<small class="text-muted">${__(
									"Category name is the record id and can't be changed after creation."
							  )}</small>`
							: ""
					}
                </div>
                <div class="col-md-5">
                  <label class="control-label reqd">${__("Display Label")}</label>
                  <input type="text" class="form-control" id="grm-cf-label" value="${frappe.utils.escape_html(
						r.label || ""
					)}">
                </div>
                <div class="col-md-3">
                  <label class="control-label reqd">${__("Abbreviation")}</label>
                  <input type="text" class="form-control" id="grm-cf-abbreviation" value="${frappe.utils.escape_html(
						r.abbreviation || ""
					)}">
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Assigned Role")}</label>
                  <select class="form-control" id="grm-cf-assigned_role">
                    ${this.role_options(r.assigned_role)}
                  </select>
                  <small class="text-muted">${__(
						"Issues in this category are routed to the user holding this role in the issue's region (or nearest ancestor) with the Investigate & Resolve duty."
					)}</small>
                  <input type="hidden" id="grm-cf-routing_target_type" value="Role">
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Appeal Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_appeal_department">
                    ${this.department_options(r.assigned_appeal_department, true)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Escalation Department")}</label>
                  <select class="form-control" id="grm-cf-assigned_escalation_department">
                    ${this.department_options(r.assigned_escalation_department, true)}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="control-label">${__("Administrative Level")}</label>
                  <select class="form-control" id="grm-cf-administrative_level">
                    ${this.admin_level_options(r.administrative_level)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Confidentiality Level")}</label>
                  <select class="form-control" id="grm-cf-confidentiality_level">
                    <option value="Public" ${conf === "Public" ? "selected" : ""}>${__(
			"Public"
		)}</option>
                    <option value="Confidential" ${conf === "Confidential" ? "selected" : ""}>${__(
			"Confidential"
		)}</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Redirection Protocol")}</label>
                  <select class="form-control" id="grm-cf-redirection_protocol">
                    <option value="0" ${redir === "0" ? "selected" : ""}>${__(
			"0 = direct routing"
		)}</option>
                    <option value="1" ${redir === "1" ? "selected" : ""}>${__(
			"1 = redirect via supervisor"
		)}</option>
                  </select>
                </div>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-cf-save">${__(
					"Save Category"
				)}</button>
                <button class="btn btn-default btn-sm" id="grm-cf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
		$w.find("#grm-cf-save").on("click", () => this.save_form(is_edit ? row.name : null));
		$w.find("#grm-cf-cancel").on("click", () => {
			this.adding = false;
			this.editing = null;
			$w.empty();
		});
	}

	read_form() {
		const $w = this.$body.find("#grm-step5-form-wrap");
		const trim = (id) => ($w.find(`#${id}`).val() || "").trim();
		return {
			category_name: trim("grm-cf-category_name"),
			label: trim("grm-cf-label"),
			abbreviation: trim("grm-cf-abbreviation"),
			routing_target_type: "Role",
			assigned_role: trim("grm-cf-assigned_role") || null,
			assigned_appeal_department: trim("grm-cf-assigned_appeal_department") || null,
			assigned_escalation_department: trim("grm-cf-assigned_escalation_department") || null,
			administrative_level: trim("grm-cf-administrative_level") || null,
			confidentiality_level: trim("grm-cf-confidentiality_level") || "Public",
			redirection_protocol: trim("grm-cf-redirection_protocol") || "0",
		};
	}

	async save_form(existing_name) {
		const v = this.read_form();
		if (!existing_name && !v.category_name) {
			frappe.show_alert({ message: __("Category Name is required."), indicator: "red" });
			return;
		}
		if (!v.label) {
			frappe.show_alert({ message: __("Display Label is required."), indicator: "red" });
			return;
		}
		if (!v.abbreviation) {
			frappe.show_alert({ message: __("Abbreviation is required."), indicator: "red" });
			return;
		}
		if (!v.assigned_role) {
			frappe.show_alert({ message: __("Assigned Role is required."), indicator: "red" });
			return;
		}
		if (!existing_name) {
			const dup = this.rows.find(
				(x) => (x.category_name || "").toLowerCase() === v.category_name.toLowerCase()
			);
			if (dup) {
				frappe.show_alert({
					message: __("Category '{0}' already exists for this project.", [
						v.category_name,
					]),
					indicator: "red",
				});
				return;
			}
		}
		try {
			if (existing_name) {
				const doc = await frappe.db.get_doc("GRM Issue Category", existing_name);
				doc.label = v.label;
				doc.abbreviation = v.abbreviation;
				doc.routing_target_type = "Role";
				doc.assigned_department = null;
				doc.assigned_role = v.assigned_role;
				doc.assigned_appeal_department = v.assigned_appeal_department;
				doc.assigned_escalation_department = v.assigned_escalation_department;
				doc.administrative_level = v.administrative_level;
				doc.confidentiality_level = v.confidentiality_level;
				doc.redirection_protocol = v.redirection_protocol;
				await frappe.call({ method: "frappe.client.save", args: { doc } });
				frappe.show_alert({ message: __("Category updated."), indicator: "green" });
			} else {
				const payload = {
					doctype: "GRM Issue Category",
					category_name: v.category_name,
					label: v.label,
					abbreviation: v.abbreviation,
					routing_target_type: "Role",
					assigned_role: v.assigned_role,
					confidentiality_level: v.confidentiality_level,
					redirection_protocol: v.redirection_protocol,
					grm_project_link: [{ project: this.project.name }],
				};
				if (v.assigned_appeal_department)
					payload.assigned_appeal_department = v.assigned_appeal_department;
				if (v.assigned_escalation_department)
					payload.assigned_escalation_department = v.assigned_escalation_department;
				if (v.administrative_level) payload.administrative_level = v.administrative_level;
				await frappe.db.insert(payload);
				frappe.show_alert({ message: __("Category created."), indicator: "green" });
			}
			this.editing = null;
			this.adding = false;
			this.$body.find("#grm-step5-form-wrap").empty();
			await this.load_and_render_table();
		} catch (e) {
			// frappe surfaces the error
		}
	}

	confirm_delete(name) {
		frappe.confirm(
			__("Delete category {0}? This will remove it from this project's setup.", [name]),
			async () => {
				try {
					await frappe.db.delete_doc("GRM Issue Category", name);
					frappe.show_alert({ message: __("Category deleted."), indicator: "green" });
					if (this.editing === name) this.editing = null;
					await this.load_and_render_table();
				} catch (e) {
					frappe.show_alert({
						message: __(
							"Could not delete category — it may still be referenced by issues."
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
