// ---------------------------------------------------------------------------
// Step 9 — SLAs
// ---------------------------------------------------------------------------
class GRMWizardStep11SLAs {
	constructor($body, project, wizard) {
		this.$body = $body;
		this.project = project;
		this.wizard = wizard;
		this.rows = []; // current values shown in inputs (from server)
		this.snapshot = {}; // {name: {acknowledgment_days, resolution_days, auto_escalate}}
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
            <div class="grm-step9" style="max-width: 960px;">
              <div class="grm-step9-intro" style="margin-bottom: 16px;">
                <p>${__(
					"SLAs are tuned per administrative level. Adjust the acknowledgment and resolution targets and toggle auto-escalation for each level."
				)}</p>
                <p class="text-muted small">${__(
					"Acknowledgment Days: how long before the case must be acknowledged. Resolution Days: how long before it must be resolved. Resolution must be >= Acknowledgment."
				)}</p>
              </div>
              <div id="grm-step9-table-wrap"></div>
              <div id="grm-step9-error" class="text-danger small" style="margin-top:8px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-primary btn-sm" id="grm-step9-save-all">${__(
					"Save All"
				)}</button>
              </div>
            </div>
        `);
		this.$body.find("#grm-step9-save-all").on("click", () => this.save_all());
		await this.load_and_render_table();
	}

	async load_and_render_table() {
		try {
			const rows = await frappe.db.get_list("GRM Administrative Level Type", {
				filters: { project: this.project.name },
				fields: [
					"name",
					"level_name",
					"level_order",
					"acknowledgment_days",
					"resolution_days",
					"auto_escalate",
				],
				limit: 0,
				order_by: "level_order asc",
			});
			this.rows = rows;
			this.snapshot = {};
			for (const r of rows) {
				this.snapshot[r.name] = {
					acknowledgment_days: r.acknowledgment_days,
					resolution_days: r.resolution_days,
					auto_escalate: r.auto_escalate,
				};
			}
		} catch (e) {
			this.rows = [];
			this.snapshot = {};
		}
		this.render_table();
	}

	render_table() {
		const $w = this.$body.find("#grm-step9-table-wrap").empty();
		if (!this.rows.length) {
			$w.html(
				`<p class="text-muted">${__(
					"No administrative levels defined yet — go back to Step 2 to add them."
				)}</p>`
			);
			return;
		}
		const head = `
            <thead>
              <tr>
                <th>${__("Level Name")}</th>
                <th style="width:80px;">${__("Order")}</th>
                <th style="width:160px;">${__("Acknowledgment Days")}</th>
                <th style="width:160px;">${__("Resolution Days")}</th>
                <th style="width:120px;">${__("Auto Escalate")}</th>
              </tr>
            </thead>
        `;
		const body_rows = this.rows
			.map(
				(r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td>${frappe.utils.escape_html(r.level_name || "")}</td>
              <td>${r.level_order != null ? r.level_order : ""}</td>
              <td><input type="number" min="0" class="form-control input-xs grm-s9-ack" value="${
					r.acknowledgment_days != null ? r.acknowledgment_days : 7
				}"></td>
              <td><input type="number" min="1" class="form-control input-xs grm-s9-res" value="${
					r.resolution_days != null ? r.resolution_days : 30
				}"></td>
              <td><input type="checkbox" class="grm-s9-auto" ${
					r.auto_escalate ? "checked" : ""
				}></td>
            </tr>
        `
			)
			.join("");
		$w.html(
			`<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`
		);
	}

	read_table() {
		const out = [];
		const $w = this.$body.find("#grm-step9-table-wrap");
		$w.find("tbody tr").each(function () {
			const $tr = $(this);
			const name = $tr.data("name");
			const ack = parseInt($tr.find(".grm-s9-ack").val(), 10);
			const res = parseInt($tr.find(".grm-s9-res").val(), 10);
			const auto = $tr.find(".grm-s9-auto").is(":checked") ? 1 : 0;
			out.push({
				name,
				acknowledgment_days: ack,
				resolution_days: res,
				auto_escalate: auto,
			});
		});
		return out;
	}

	validate(values) {
		const errors = [];
		for (const v of values) {
			if (isNaN(v.acknowledgment_days) || v.acknowledgment_days < 0) {
				errors.push(__("Row {0}: Acknowledgment Days must be >= 0.", [v.name]));
			}
			if (isNaN(v.resolution_days) || v.resolution_days < 1) {
				errors.push(__("Row {0}: Resolution Days must be >= 1.", [v.name]));
			}
			if (
				!isNaN(v.acknowledgment_days) &&
				!isNaN(v.resolution_days) &&
				v.resolution_days < v.acknowledgment_days
			) {
				errors.push(
					__("Row {0}: Resolution Days must be >= Acknowledgment Days.", [v.name])
				);
			}
		}
		return errors;
	}

	async save_all() {
		const ok = await this._do_save();
		if (ok) {
			frappe.show_alert({ message: __("SLAs saved."), indicator: "green" });
		}
		return ok;
	}

	async _do_save() {
		const $err = this.$body.find("#grm-step9-error").empty();
		if (!this.rows.length) {
			// Nothing to save; treat as success (Step 9 isn't blocking when no levels exist)
			return true;
		}
		const values = this.read_table();
		const errors = this.validate(values);
		if (errors.length) {
			$err.html(errors.map((e) => `<div>${frappe.utils.escape_html(e)}</div>`).join(""));
			frappe.show_alert({
				message: __("SLA validation failed — see errors above."),
				indicator: "red",
			});
			return false;
		}
		try {
			for (const v of values) {
				const orig = this.snapshot[v.name] || {};
				const diffs = {};
				if (orig.acknowledgment_days !== v.acknowledgment_days)
					diffs.acknowledgment_days = v.acknowledgment_days;
				if (orig.resolution_days !== v.resolution_days)
					diffs.resolution_days = v.resolution_days;
				if ((orig.auto_escalate ? 1 : 0) !== (v.auto_escalate ? 1 : 0))
					diffs.auto_escalate = v.auto_escalate;
				for (const [field, val] of Object.entries(diffs)) {
					await frappe.db.set_value("GRM Administrative Level Type", v.name, field, val);
				}
			}
			// Refresh snapshot
			for (const v of values) {
				this.snapshot[v.name] = {
					acknowledgment_days: v.acknowledgment_days,
					resolution_days: v.resolution_days,
					auto_escalate: v.auto_escalate,
				};
			}
			return true;
		} catch (e) {
			return false;
		}
	}

	async save() {
		return await this._do_save();
	}
}
