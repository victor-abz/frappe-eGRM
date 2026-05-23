// ---------------------------------------------------------------------------
// Step 11 — Notification Templates
// ---------------------------------------------------------------------------
class GRMWizardStep6NotificationTemplates {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.rows = [];
        this.email_templates = [];
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
            <div class="grm-step11" style="max-width: 1100px;">
              <div class="grm-step11-intro" style="margin-bottom: 16px;">
                <p>${__("Notification Templates control the messages sent to citizens at each stage of an issue's lifecycle (receipt, acknowledgment, status updates, escalation, SLA reminders).")}</p>
                <p class="text-muted small">${__("Each template can drive an email (linked Email Template) and / or an SMS (Jinja2 message body). Use {{ tracking_code }}, {{ status }}, {{ subject }}, etc. as placeholders.")}</p>
              </div>
              <div id="grm-step11-table-wrap"></div>
              <div id="grm-step11-form-wrap" style="margin-top: 12px;"></div>
              <div style="margin-top: 12px;">
                <button class="btn btn-default btn-sm" id="grm-step11-add">+ ${__("Add Template")}</button>
              </div>
            </div>
        `);
        this.$body.find("#grm-step11-add").on("click", () => this.start_add());
        await this.load_email_templates();
        await this.load_and_render_table();
    }

    async load_email_templates() {
        try {
            this.email_templates = await frappe.db.get_list("Email Template", {
                fields: ["name"],
                limit: 50,
                order_by: "name asc",
            });
        } catch (e) {
            this.email_templates = [];
        }
    }

    async load_and_render_table() {
        try {
            this.rows = await frappe.db.get_list("GRM Notification Template", {
                filters: { project: this.project.name },
                fields: ["name", "template_name", "template_type", "active"],
                limit: 0,
                order_by: "template_type asc",
            });
        } catch (e) {
            this.rows = [];
        }
        this.render_table();
    }

    render_table() {
        const $w = this.$body.find("#grm-step11-table-wrap").empty();
        if (!this.rows.length) {
            $w.html(`<p class="text-muted">${__("No notification templates yet — click \"Add Template\" to create the first one.")}</p>`);
            return;
        }
        const head = `
            <thead>
              <tr>
                <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all" tabindex="-1"></th>
                <th>${__("Name")}</th>
                <th style="width:170px;">${__("Type")}</th>
                <th style="width:90px;">${__("Active")}</th>
                <th style="width:140px;">${__("Actions")}</th>
              </tr>
            </thead>
        `;
        const body_rows = this.rows.map((r) => `
            <tr data-name="${frappe.utils.escape_html(r.name)}">
              <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check" tabindex="-1"></td>
              <td>${frappe.utils.escape_html(r.template_name || r.name)}</td>
              <td>${frappe.utils.escape_html(r.template_type || "")}</td>
              <td>${r.active ? __("Yes") : __("No")}</td>
              <td>
                <button class="grm-row-action grm-edit-tpl" title="${__("Edit")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("edit", "sm")}</button>
                <button class="grm-row-action grm-row-action-danger grm-delete-tpl" title="${__("Delete")}" data-name="${frappe.utils.escape_html(r.name)}">${frappe.utils.icon("close", "sm")}</button>
              </td>
            </tr>
        `).join("");
        $w.html(
            grm_render_bulk_toolbar("templates")
            + `<div class="form-grid"><table class="table table-borderless">${head}<tbody>${body_rows}</tbody></table></div>`,
        );

        $w.find("button.grm-edit-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.start_edit(name);
        });
        $w.find("button.grm-delete-tpl").on("click", (ev) => {
            const name = $(ev.currentTarget).data("name");
            this.confirm_delete(name);
        });

        grm_wire_bulk_table($w, {
            selected: this.selected,
            row_names: this.rows.map((r) => r.name),
            key: "templates",
            singular: __("template"),
            plural: __("templates"),
            confirm_msg: (n) => n === 1
                ? __("Delete the selected notification template?")
                : __("Delete {0} selected notification templates?", [n]),
            delete_one: (name) => frappe.db.delete_doc("GRM Notification Template", name),
            on_done: () => this.load_and_render_table(),
        });
    }

    type_options(selected) {
        const types = [
            "Receipt",
            "Acknowledgment",
            "In Progress",
            "Resolved",
            "Closed",
            "Escalated",
            "SLA Reminder",
        ];
        const opts = [`<option value="">${__("(select)")}</option>`];
        for (const t of types) {
            const sel = t === selected ? " selected" : "";
            opts.push(`<option value="${frappe.utils.escape_html(t)}"${sel}>${frappe.utils.escape_html(t)}</option>`);
        }
        return opts.join("");
    }

    email_template_options(selected) {
        const opts = [`<option value="">${__("(none)")}</option>`];
        let saw_selected = false;
        for (const t of this.email_templates) {
            const sel = t.name === selected ? " selected" : "";
            if (t.name === selected) saw_selected = true;
            opts.push(`<option value="${frappe.utils.escape_html(t.name)}"${sel}>${frappe.utils.escape_html(t.name)}</option>`);
        }
        if (selected && !saw_selected) {
            opts.push(`<option value="${frappe.utils.escape_html(selected)}" selected>${frappe.utils.escape_html(selected)}</option>`);
        }
        return opts.join("");
    }

    start_add() {
        this.adding = true;
        this.editing = null;
        this.render_form(null);
    }

    async start_edit(name) {
        try {
            const doc = await frappe.db.get_doc("GRM Notification Template", name);
            this.editing = name;
            this.adding = false;
            this.render_form(doc);
        } catch (e) {
            frappe.show_alert({ message: __("Could not load template."), indicator: "red" });
        }
    }

    render_form(row) {
        const is_edit = !!row;
        const r = row || {};
        const active = is_edit ? !!r.active : true;
        const enable_sms = !!r.enable_sms;
        const $w = this.$body.find("#grm-step11-form-wrap").empty();
        $w.html(`
            <div class="grm-step11-form card" style="border:1px solid var(--border-color, #d1d8dd); padding:12px; border-radius:6px;">
              <h5 style="margin-top:0;">${is_edit ? __("Edit Template") : __("New Template")}</h5>
              <div class="row">
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Template Name")}</label>
                  <input type="text" class="form-control" id="grm-tf-template_name" value="${frappe.utils.escape_html(r.template_name || "")}" ${is_edit ? "disabled" : ""}>
                  ${is_edit ? `<small class="text-muted">${__("Template name is the record id and can't be changed.")}</small>` : ""}
                </div>
                <div class="col-md-6">
                  <label class="control-label reqd">${__("Template Type")}</label>
                  <select class="form-control" id="grm-tf-template_type">
                    ${this.type_options(r.template_type)}
                  </select>
                </div>
              </div>
              <div class="row" style="margin-top:8px;">
                <div class="col-md-6">
                  <label class="control-label">${__("Email Template")}</label>
                  <select class="form-control" id="grm-tf-email_template">
                    ${this.email_template_options(r.email_template)}
                  </select>
                  <small class="text-muted">${__("Showing up to 50 Email Templates.")}</small>
                </div>
                <div class="col-md-6">
                  <label class="control-label">${__("Active")}</label>
                  <div><label class="checkbox"><input type="checkbox" id="grm-tf-active" ${active ? "checked" : ""}> ${__("Template Active")}</label></div>
                </div>
              </div>
              <div class="form-group" style="margin-top:8px;">
                <label class="checkbox">
                  <input type="checkbox" id="grm-tf-enable_sms" ${enable_sms ? "checked" : ""}>
                  ${__("Enable SMS")}
                </label>
              </div>
              <div class="form-group">
                <label class="control-label">${__("SMS Message")}</label>
                <textarea class="form-control" id="grm-tf-sms_message" rows="4" placeholder="${__("e.g. Issue {{ tracking_code }} is now {{ status }}.")}">${frappe.utils.escape_html(r.sms_message || "")}</textarea>
                <small class="text-muted">${__("Supports Jinja2: {{ tracking_code }}, {{ status }}, {{ subject }}, {{ complainant_name }}, {{ created_date }}, etc.")}</small>
              </div>
              <div style="margin-top:12px;">
                <button class="btn btn-primary btn-sm" id="grm-tf-save">${__("Save Template")}</button>
                <button class="btn btn-default btn-sm" id="grm-tf-cancel">${__("Cancel")}</button>
              </div>
            </div>
        `);
        $w.find("#grm-tf-save").on("click", () => this.save_form(is_edit ? row.name : null));
        $w.find("#grm-tf-cancel").on("click", () => {
            this.adding = false;
            this.editing = null;
            $w.empty();
        });
    }

    read_form() {
        const $w = this.$body.find("#grm-step11-form-wrap");
        const trim = (id) => ($w.find(`#${id}`).val() || "").trim();
        const checked = (id) => $w.find(`#${id}`).is(":checked") ? 1 : 0;
        return {
            template_name: trim("grm-tf-template_name"),
            template_type: trim("grm-tf-template_type"),
            email_template: trim("grm-tf-email_template") || null,
            enable_sms: checked("grm-tf-enable_sms"),
            sms_message: trim("grm-tf-sms_message"),
            active: checked("grm-tf-active"),
        };
    }

    async save_form(existing_name) {
        const v = this.read_form();
        if (!existing_name && !v.template_name) {
            frappe.show_alert({ message: __("Template Name is required."), indicator: "red" });
            return;
        }
        if (!v.template_type) {
            frappe.show_alert({ message: __("Template Type is required."), indicator: "red" });
            return;
        }
        if (!existing_name) {
            const dup = this.rows.find(
                (x) => (x.template_name || "").toLowerCase() === v.template_name.toLowerCase(),
            );
            if (dup) {
                frappe.show_alert({ message: __("Template '{0}' already exists for this project.", [v.template_name]), indicator: "red" });
                return;
            }
        }
        const dup_type = this.rows.find(
            (r) => r.template_type === v.template_type && r.name !== existing_name,
        );
        if (dup_type) {
            frappe.show_alert({
                message: __("A template of type \"{0}\" already exists for this project.", [v.template_type]),
                indicator: "red",
            });
            return;
        }
        try {
            if (existing_name) {
                // Use the doc round-trip so the project field doesn't get unset by partial saves.
                const doc = await frappe.db.get_doc("GRM Notification Template", existing_name);
                doc.project = this.project.name;
                doc.template_type = v.template_type;
                doc.email_template = v.email_template;
                doc.enable_sms = v.enable_sms;
                doc.sms_message = v.sms_message;
                doc.active = v.active;
                await frappe.call({ method: "frappe.client.save", args: { doc } });
                frappe.show_alert({ message: __("Template updated."), indicator: "green" });
            } else {
                const payload = {
                    doctype: "GRM Notification Template",
                    template_name: v.template_name,
                    template_type: v.template_type,
                    enable_sms: v.enable_sms,
                    sms_message: v.sms_message,
                    active: v.active,
                    project: this.project.name,
                };
                if (v.email_template) payload.email_template = v.email_template;
                await frappe.db.insert(payload);
                frappe.show_alert({ message: __("Template created."), indicator: "green" });
            }
            this.editing = null;
            this.adding = false;
            this.$body.find("#grm-step11-form-wrap").empty();
            await this.load_and_render_table();
        } catch (e) {
            // frappe surfaces the error
        }
    }

    confirm_delete(name) {
        frappe.confirm(
            __("Delete notification template {0}?", [name]),
            async () => {
                try {
                    await frappe.db.delete_doc("GRM Notification Template", name);
                    frappe.show_alert({ message: __("Template deleted."), indicator: "green" });
                    if (this.editing === name) this.editing = null;
                    await this.load_and_render_table();
                } catch (e) {
                    frappe.show_alert({ message: __("Could not delete template."), indicator: "red" });
                }
            },
        );
    }

    async save() {
        return true;
    }
}
