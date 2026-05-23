// ---------------------------------------------------------------------------
// Step 2 — Regions tab (bulk CSV upload of administrative regions)
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminRegionsInner {
    constructor($container, project, wizard) {
        this.$container = $container;
        this.project = project;
        this.wizard = wizard;
        this.parsed = null;
        this.render();
    }

    render() {
        this.$container.html(`
            <p class="text-muted">${__("Upload a CSV with one column per administrative level (e.g. Province, District, Sector). The highest level is auto-created from the project's country.")}</p>
            <div class="form-group">
              <label>${__("Highest level (single value, applied to all rows)")}</label>
              <input type="text" class="form-control" id="grm-rg-highest" placeholder="Country" value="Country">
            </div>
            <div class="form-group">
              <label>${__("CSV file")}</label>
              <input type="file" accept=".csv" id="grm-rg-file" class="form-control-file">
            </div>
            <button class="btn btn-default btn-sm" id="grm-rg-preview">${__("Preview")}</button>
            <button class="btn btn-primary btn-sm" id="grm-rg-import" disabled>${__("Import Regions")}</button>
            <div id="grm-rg-result" class="mt-3"></div>
        `);
        this.$container.find("#grm-rg-preview").on("click", () => this.preview());
        this.$container.find("#grm-rg-import").on("click",  () => this.do_import());
    }

    async _read_file() {
        const file = this.$container.find("#grm-rg-file")[0].files[0];
        if (!file) {
            frappe.show_alert({ message: __("Pick a CSV first."), indicator: "orange" });
            return null;
        }
        return await file.text();
    }

    async preview() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.parse_admin_regions_csv",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        this.parsed = r.message;
        this._render_preview();
    }

    _render_preview() {
        const p = this.parsed || {};
        const $r = this.$container.find("#grm-rg-result").empty();
        if (p.errors && p.errors.length) {
            $r.append(`<div class="alert alert-danger"><strong>${__("Errors")}:</strong><ul>${p.errors.map(e => `<li>${frappe.utils.escape_html(e)}</li>`).join("")}</ul></div>`);
            this.$container.find("#grm-rg-import").prop("disabled", true);
            return;
        }
        const cols = p.level_columns || [];
        $r.append(`<div class="alert alert-info">${__("Detected {0} rows across levels: {1}", [p.total_rows || 0, cols.join(" → ")])}</div>`);
        const $tbl = $(`<div class="form-grid"><table class="table table-borderless"><thead><tr>${cols.map(c => `<th>${frappe.utils.escape_html(c)}</th>`).join("")}</tr></thead><tbody></tbody></table></div>`);
        (p.preview || []).forEach(row => {
            $tbl.find("tbody").append(`<tr>${cols.map(c => `<td>${frappe.utils.escape_html(row[c] || "")}</td>`).join("")}</tr>`);
        });
        $r.append($tbl);
        this.$container.find("#grm-rg-import").prop("disabled", false);
    }

    async do_import() {
        const csv_text = await this._read_file();
        if (!csv_text) return;
        const highest = this.$container.find("#grm-rg-highest").val().trim() || "Country";
        const r = await frappe.call({
            method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.bulk_insert_admin_regions",
            args: { project: this.project.name, highest_level: highest, csv_text },
        });
        const m = r.message || {};
        const $r = this.$container.find("#grm-rg-result").empty();
        $r.append(`<div class="alert alert-success">${__("Imported {0} regions ({1} updated). {2} errors.", [m.created || 0, m.updated || 0, (m.errors || []).length])}</div>`);
        if (m.errors && m.errors.length) {
            $r.append(`<ul>${m.errors.map(e => `<li class="text-danger">${frappe.utils.escape_html(e)}</li>`).join("")}</ul>`);
        }
    }

    async save() {
        // The Regions tab does not gate step navigation — bulk upload is optional.
        return true;
    }
}

