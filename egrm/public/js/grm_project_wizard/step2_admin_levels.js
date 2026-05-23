// ---------------------------------------------------------------------------
// Step 3 — Administrative Levels
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminLevelsInner {
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
            <div class="grm-step3" style="max-width: 960px;">
              <div class="grm-step3-intro" style="margin-bottom: 16px;">
                <p>${__("Administrative Levels are the geographic / organizational hierarchy used to route GRM cases (e.g. National &rarr; Region &rarr; District &rarr; Sector &rarr; Cell).")}</p>
                <p class="text-muted small">${__("Lower level_order = higher in the tree (1 = root). Each level defines its own SLA defaults: acknowledgment, resolution, reminder lead time, and auto-escalation.")}</p>
              </div>
              <div id="grm-step3-table-wrap"></div>
              <div id="grm-step3-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step3-add">+ ${__("Add Level")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step3-add").on("click", () => this.start_add());
        await this.load_and_render_table();
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Administrative Level Type", {
                filters: { project: this.project.name },
                fields: [
                    "name",
                    "level_name",
                    "level_order",
                    "acknowledgment_days",
                    "resolution_days",
                    "reminder_before_days",
                    "auto_escalate",
                ],
                limit: 0,
                order_by: "level_order asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step3-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No administrative levels yet — click \"Add Level\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Level Name")}</th>
                <th style="width:80px;">${__("Order")}</th>
                <th style="width:90px;">${__("Ack Days")}</th>
                <th style="width:90px;">${__("Res Days")}</th>
                <th style="width:120px;">${__("Reminder Before")}</th>
                <th style="width:110px;">${__("Auto Escalate")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => this.render_row_html(r)).join("");
        $w.html(
            grm_render_bulk_toolbar("levels")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        // Wire up actions via delegation
        $w.find("button.grm-edit").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });
        $w.find("button.grm-save-edit").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.save_edit(name);
        });
        $w.find("button.grm-cancel-edit").on("click", () => {
            this.editing = null;
            this.render_table();
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "levels",
            singular: __("level"),
            plural: __("levels"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected administrative level?")
                : __("Delete {0} selected administrative levels?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Administrative Level Type", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    render_row_html(r) {
        const editing = this.editing === r.name;
        if (editing) {
            return `
              <tr data-name="${frappe.utils.escape_html(r.name)}">
                <td class="grm-bulk-cell"></td>
                <td><input type="text" class="form-control input-xs" id="grm-e-level_name" value="${frappe.utils.escape_html(r.level_name || "")}"></td>
                <td><input type="number" min="1" class="form-control input-xs" id="grm-e-level_order" value="${r.level_order != null ? r.level_order : ""}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-acknowledgment_days" value="${r.acknowledgment_days != null ? r.acknowledgment_days : 7}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-resolution_days" value="${r.resolution_days != null ? r.resolution_days : 30}"></td>
                <td><input type="number" min="0" class="form-control input-xs" id="grm-e-reminder_before_days" value="${r.reminder_before_days != null ? r.reminder_before_days : 2}"></td>
                <td><input type="checkbox" id="grm-e-auto_escalate" ${r.auto_escalate ? "checked" : ""}></td>
                <td>
                  <button class="btn btn-xs btn-primary grm-save-edit" data-name="${frappe.utils.escape_html(r.name)}">${__("Save")}</button>
                  <button class="btn btn-xs btn-default grm-cancel-edit">${__("Cancel")}</button>
                </td>
              </tr>
            `;
        }
        return `
          <tr data-name="${frappe.utils.escape_html(r.name)}">
            <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
            <td>${frappe.utils.escape_html(r.level_name || "")}</td>
            <td>${r.level_order != null ? r.level_order : ""}</td>
            <td>${r.acknowledgment_days != null ? r.acknowledgment_days : ""}</td>
            <td>${r.resolution_days != null ? r.resolution_days : ""}</td>
            <td>${r.reminder_before_days != null ? r.reminder_before_days : ""}</td>
            <td>${r.auto_escalate ? __("Yes") : __("No")}</td>
            <td>
              <button class="grm-row-action grm-edit" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
              <button class="grm-row-action grm-row-action-danger grm-delete" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
            </td>
          </tr>
        `;
    }

    start_edit(name) {
        this.editing = name;
        this.adding = false;
        this.$body.find("#grm-step3-form-wrap").empty();
        this.render_table();
    }

    async save_edit(name) {
        const $row = this.$body.find(`#grm-step3-table-wrap tr[data-name="${CSS.escape(name)}"]`);
        const orig = this.rows.find((x) => x.name === name);
        if (!orig) return;
        const level_name = ($row.find("#grm-e-level_name").val() || "").trim();
        const level_order = parseInt($row.find("#grm-e-level_order").val(), 10);
        const ack = parseInt($row.find("#grm-e-acknowledgment_days").val(), 10);
        const res = parseInt($row.find("#grm-e-resolution_days").val(), 10);
        const rem = parseInt($row.find("#grm-e-reminder_before_days").val(), 10);
        const auto = $row.find("#grm-e-auto_escalate").is(":checked") ? 1 : 0;

        if (!level_name) {
            frappe.show_alert({ message: __("Level Name is required."), indicator: "red" });
            return;
        }
        if (isNaN(level_order) || level_order < 1) {
            frappe.show_alert({ message: __("Level Order must be an integer >= 1."), indicator: "red" });
            return;
        }
        // Local uniqueness check (excluding self)
        const dup = this.rows.find(
            (x) => x.name !== name && (x.level_name || "").toLowerCase() === level_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Level Name '{0}' already exists for this project.", [level_name]), indicator: "red" });
            return;
        }

        const updates = {
            level_name,
            level_order,
            acknowledgment_days: isNaN(ack) ? 7 : ack,
            resolution_days: isNaN(res) ? 30 : res,
            reminder_before_days: isNaN(rem) ? 2 : rem,
            auto_escalate: auto,
        };
        try {
            // Use a single get_doc + frappe.client.save to update level_name (which is the autoname)
            // safely. Per-field set_value can't change the document name itself.
            const doc = await frappe.db.get_doc("GRM Administrative Level Type", name);
            Object.assign(doc, updates);
            await frappe.call({ method: "frappe.client.save", args: { doc } });
            frappe.show_alert({ message: __("Level updated."), indicator: "green" });
            this.editing = null;
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(__("Delete level {0}?", [name]), async () => {
            try {
                await frappe.db.delete_doc("GRM Administrative Level Type", name);
                frappe.show_alert({ message: __("Level deleted."), indicator: "green" });
                if (this.editing === name) this.editing = null;
                await this.load_and_render_table();
            } catch (e) {
                // frappe surfaces the error
            }
        });
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        const $w = this.$body.find("#grm-step3-form-wrap").empty();
        $w.html(`
            <div class="grm-step3-add card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${__("New Administrative Level")}</h5>
              <div class="row">
                <div class="col-md-4">
                  <label class="control-label reqd">${__("Level Name")}</label>
                  <input type="text" class="form-control" id="grm-n-level_name">
                </div>
                <div class="col-md-2">
                  <label class="control-label reqd">${__("Order")}</label>
                  <input type="number" min="1" class="form-control" id="grm-n-level_order">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Ack Days")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-acknowledgment_days" value="7">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Res Days")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-resolution_days" value="30">
                </div>
                <div class="col-md-2">
                  <label class="control-label">${__("Reminder Before")}</label>
                  <input type="number" min="0" class="form-control" id="grm-n-reminder_before_days" value="2">
                </div>
              </div>
              <div class="form-group" style="margin-top:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-n-auto_escalate" checked>
                  ${__("Auto Escalate")}
                </label>
              </div>
              <div style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" id="grm-n-save">${__("Save Level")}</button>
                <button class="btn btn-default btn-sm" id="grm-n-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-n-save").on("click", () => this.save_new());
        $w.find("#grm-n-cancel").on("click", () => {
            this.adding = false;
            $w.empty();
        });
    }

    async save_new() {
        const $w = this.$body.find("#grm-step3-form-wrap");
        const level_name = ($w.find("#grm-n-level_name").val() || "").trim();
        const level_order = parseInt($w.find("#grm-n-level_order").val(), 10);
        const ack = parseInt($w.find("#grm-n-acknowledgment_days").val(), 10);
        const res = parseInt($w.find("#grm-n-resolution_days").val(), 10);
        const rem = parseInt($w.find("#grm-n-reminder_before_days").val(), 10);
        const auto = $w.find("#grm-n-auto_escalate").is(":checked") ? 1 : 0;

        if (!level_name) {
            frappe.show_alert({ message: __("Level Name is required."), indicator: "red" });
            return;
        }
        if (isNaN(level_order) || level_order < 1) {
            frappe.show_alert({ message: __("Level Order must be an integer >= 1."), indicator: "red" });
            return;
        }
        const dup = this.rows.find(
            (x) => (x.level_name || "").toLowerCase() === level_name.toLowerCase(),
        );
        if (dup) {
            frappe.show_alert({ message: __("Level Name '{0}' already exists for this project.", [level_name]), indicator: "red" });
            return;
        }

        try {
            await frappe.db.insert({
                doctype: "GRM Administrative Level Type",
                project: this.project.name,
                level_name,
                level_order,
                acknowledgment_days: isNaN(ack) ? 7 : ack,
                resolution_days: isNaN(res) ? 30 : res,
                reminder_before_days: isNaN(rem) ? 2 : rem,
                auto_escalate: auto,
            });
            frappe.show_alert({ message: __("Level created."), indicator: "green" });
            this.adding = false;
            $w.empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    async save() {
        // Rows are persisted inline as the user edits — Continue just advances.
        return true;
    }
}

