// ---------------------------------------------------------------------------
// Step 10 — Issue Routing finalization (review per-category routing)
// ---------------------------------------------------------------------------
class GRMWizardStep10Routing {
	constructor($body, project, wizard) {
		this.$body = $body;
		this.project = project;
		this.wizard = wizard;
		this.categories = [];
		this.departments = [];
		this.roles = [];
		this.render();
	}

	async render() {
		if (!this.project) {
			this.$body.html(
				`<p class="text-muted">${__("Save Step 1 first to create the project.")}</p>`
			);
			return;
		}
		this.$body.html(`<p class="text-muted">${__("Loading…")}</p>`);
		await this._load();
		this._render_table();
	}

	async _load() {
		try {
			const [cats, depts, roles] = await Promise.all([
				frappe.db.get_list("GRM Issue Category", {
					filters: [["GRM Project Link", "project", "=", this.project.name]],
					fields: [
						"name",
						"category_name",
						"label",
						"routing_target_type",
						"assigned_department",
						"assigned_role",
					],
					limit: 0,
				}),
				frappe.db.get_list("GRM Issue Department", {
					filters: { project: this.project.name },
					fields: ["name", "department_name"],
					limit: 0,
				}),
				frappe.db.get_list("GRM Project Role", {
					filters: { project: this.project.name, is_active: 1 },
					fields: ["name", "role_name"],
					limit: 0,
				}),
			]);
			this.categories = cats || [];
			this.departments = depts || [];
			this.roles = roles || [];
		} catch (e) {
			this.categories = [];
			this.departments = [];
			this.roles = [];
		}
	}

	_opt(value, label, selected) {
		const sel = selected != null && String(selected) === String(value) ? "selected" : "";
		return `<option value="${frappe.utils.escape_html(
			value || ""
		)}" ${sel}>${frappe.utils.escape_html(label || "")}</option>`;
	}

	_render_table() {
		if (!this.categories.length) {
			this.$body.html(
				`<p class="text-muted">${__(
					"No issue categories defined yet — go back to Step 5 to add some."
				)}</p>`
			);
			return;
		}
		const dept_opts = this.departments
			.map(
				(d) =>
					`<option value="${frappe.utils.escape_html(
						d.name
					)}">${frappe.utils.escape_html(d.department_name || d.name)}</option>`
			)
			.join("");
		const role_opts = this.roles
			.map(
				(r) =>
					`<option value="${frappe.utils.escape_html(
						r.name
					)}">${frappe.utils.escape_html(r.role_name || r.name)}</option>`
			)
			.join("");
		const rows = this.categories
			.map((c) => {
				const tt = c.routing_target_type || "Department";
				const dept_options =
					`<option value="">— ${__("None")} —</option>` +
					dept_opts.replace(
						`value="${frappe.utils.escape_html(c.assigned_department)}"`,
						`value="${frappe.utils.escape_html(c.assigned_department)}" selected`
					);
				const role_options =
					`<option value="">— ${__("None")} —</option>` +
					role_opts.replace(
						`value="${frappe.utils.escape_html(c.assigned_role)}"`,
						`value="${frappe.utils.escape_html(c.assigned_role)}" selected`
					);
				return `
              <tr data-cat="${frappe.utils.escape_html(c.name)}">
                <td>${frappe.utils.escape_html(c.label || c.category_name || c.name)}</td>
                <td>
                  <select class="form-control form-control-sm grm-r-type">
                    <option value="Department" ${tt === "Department" ? "selected" : ""}>${__(
					"Department"
				)}</option>
                    <option value="Role"       ${tt === "Role" ? "selected" : ""}>${__(
					"Role"
				)}</option>
                  </select>
                </td>
                <td>
                  <select class="form-control form-control-sm grm-r-target-dept" ${
						tt === "Role" ? "style='display:none'" : ""
					}>
                    ${dept_options}
                  </select>
                  <select class="form-control form-control-sm grm-r-target-role" ${
						tt === "Department" ? "style='display:none'" : ""
					}>
                    ${role_options}
                  </select>
                </td>
              </tr>`;
			})
			.join("");
		this.$body.html(`
            <p class="text-muted">${__(
				"Finalise where each category's complaints are routed. Choose a Department for organisational routing, or a Role for cross-department workflows."
			)}</p>
            <div class="form-grid">
              <table class="table table-borderless">
                <thead><tr><th>${__("Category")}</th><th style="width:160px;">${__(
			"Route To"
		)}</th><th>${__("Target")}</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
        `);
		this.$body.on("change", ".grm-r-type", (e) => {
			const $tr = $(e.target).closest("tr");
			const t = $(e.target).val();
			$tr.find(".grm-r-target-dept").toggle(t === "Department");
			$tr.find(".grm-r-target-role").toggle(t === "Role");
		});
	}

	async save() {
		const tasks = [];
		const me = this;
		this.$body.find("tbody tr").each(function () {
			const $tr = $(this);
			const cat = $tr.data("cat");
			const t = $tr.find(".grm-r-type").val();
			const target =
				t === "Department"
					? $tr.find(".grm-r-target-dept").val()
					: $tr.find(".grm-r-target-role").val();
			if (!target) return;
			tasks.push(
				frappe.call({
					method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.update_category_routing",
					args: { project: me.project.name, category: cat, target_type: t, target },
				})
			);
		});
		try {
			await Promise.all(tasks);
			return true;
		} catch (e) {
			return false;
		}
	}
}
