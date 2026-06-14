// Phase E — `GRMWizardStep9UserImport` 4-stage bulk-import flow
// ---------------------------------------------------------------------------
// Wraps the Phase B Data Import endpoints (`download_user_template`,
// `auto_detect_user_import_mapping`, `prepare_user_import`,
// `start_user_import`, `poll_user_import`) with a stage-driven UI:
//   1. template — pick CSV or XLSX template download
//   2. upload   — drag-drop / browse a filled-in file
//   3. mapping  — confirm/edit the column → target mapping
//   4. preview  — review resolved rows + start import + poll progress
// On import completion the `on_completed` callback refreshes the list.
// ---------------------------------------------------------------------------

const GRM_STEP9_BULK_POLL_MS = 1500;
const GRM_STEP9_BULK_PREVIEW_LIMIT = 50;
const GRM_STEP9_BULK_MAX_FILE_MB = 10;

class GRMWizardStep9UserImport {
    constructor(opts) {
        this.project = opts.project;
        this.$mount = opts.$mount;
        this.on_completed = opts.on_completed || (() => {});
        this.stage = "template"; // template | upload | mapping | preview
        this.uploaded_file_url = null;
        this.uploaded_file_name = "";
        this.headers = [];
        this.mapping = {}; // {header: {target, level_type, ...}}
        this.project_meta = null;
        this.validation = null;
        this.preview_rows = [];
        this.total_rows = 0;
        this.preview = null;        // result of `prepare_user_import`
        this.regions_to_create = [];
        this.data_import_name = null;
        this.poll_handle = null;
    }

    render() {
        // Fresh skeleton — re-rendered if user navigates away from this
        // panel and back. Per-stage state is preserved on `this`.
        this.$mount.html(`
            <div class="grm-step9-add-form grm-step9-bulk">
              <h5>${__("Bulk import users")}</h5>
              <div class="grm-step9-bulk-stages">
                <div class="grm-stage" data-stage="template">${__("1. Template")}</div>
                <div class="grm-stage" data-stage="upload">${__("2. Upload")}</div>
                <div class="grm-stage" data-stage="mapping">${__("3. Map columns")}</div>
                <div class="grm-stage" data-stage="preview">${__("4. Preview & Import")}</div>
              </div>
              <div class="grm-step9-bulk-content"></div>
            </div>
        `);
        this._refresh_stage_pills();
        this._render_stage();
    }

    _refresh_stage_pills() {
        const $stages = this.$mount.find(".grm-stage");
        $stages.removeClass("active done");
        const order = ["template", "upload", "mapping", "preview"];
        const cur_idx = order.indexOf(this.stage);
        $stages.each((i, el) => {
            const $el = $(el);
            const stage = $el.data("stage");
            const idx = order.indexOf(stage);
            if (idx === cur_idx) $el.addClass("active");
            else if (idx < cur_idx) $el.addClass("done");
        });
    }

    set_stage(stage) {
        // Cancel any pending poll when leaving the preview stage.
        if (this.stage === "preview" && stage !== "preview" && this.poll_handle) {
            clearTimeout(this.poll_handle);
            this.poll_handle = null;
        }
        this.stage = stage;
        this._refresh_stage_pills();
        this._render_stage();
    }

    _render_stage() {
        const $content = this.$mount.find(".grm-step9-bulk-content").empty();
        switch (this.stage) {
            case "template": this._render_template_stage($content); break;
            case "upload":   this._render_upload_stage($content); break;
            case "mapping":  this._render_mapping_stage($content); break;
            case "preview":  this._render_preview_stage($content); break;
        }
    }

    // --- Stage 1: template ---------------------------------------------------
    _render_template_stage($content) {
        $content.html(`
            <p>${__("Download a project-tailored template, fill it in with your users, then upload below.")}</p>
            <p class="text-muted small">${__("Columns include your project's admin levels (e.g. Province / District / Sector), required user fields (email, first name, last name), and required assignment fields (role).")}</p>
            <div class="btn-group" role="group">
              <button type="button" class="btn btn-default grm-template-csv">${__("Download CSV template")}</button>
              <button type="button" class="btn btn-default grm-template-xlsx">${__("Download Excel template")}</button>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-primary grm-stage-next">${__("Continue to upload")}</button>
            </div>
        `);
        $content.find(".grm-template-csv").on("click", () => this._download_template("csv"));
        $content.find(".grm-template-xlsx").on("click", () => this._download_template("xlsx"));
        $content.find(".grm-stage-next").on("click", () => this.set_stage("upload"));
    }

    _download_template(format) {
        // Frappe whitelisted methods that write to `frappe.response` with
        // type=binary are served correctly via /api/method/. Open in a
        // new window so the browser downloads it.
        const project = this.project && this.project.name;
        if (!project) return;
        const params = new URLSearchParams({ project: project, format: format });
        const url = `/api/method/egrm.egrm.page.grm_project_wizard.grm_project_wizard.download_user_template?${params.toString()}`;
        window.open(url, "_blank");
    }

    // --- Stage 2: upload -----------------------------------------------------
    _render_upload_stage($content) {
        const status_html = this.uploaded_file_url
            ? `<p class="grm-upload-status text-success">${__("Uploaded: {0}", [frappe.utils.escape_html(this.uploaded_file_name)])}</p>`
            : `<p class="grm-upload-status text-muted"></p>`;
        $content.html(`
            <div class="grm-step9-upload-zone">
              <div class="grm-upload-icon">⬆</div>
              <p>${__("Drag your CSV or Excel file here, or click to browse.")}</p>
              <button type="button" class="btn btn-default grm-upload-browse">${__("Choose file")}</button>
            </div>
            ${status_html}
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
            </div>
        `);

        const $zone = $content.find(".grm-step9-upload-zone");
        $content.find(".grm-upload-browse").on("click", () => this._open_uploader());
        $zone.on("click", (e) => {
            // Browse-on-zone-click — but ignore clicks that bubbled up from
            // the inner button (which already opens the uploader).
            if ($(e.target).closest(".grm-upload-browse").length) return;
            this._open_uploader();
        });
        $zone.on("dragover", (e) => {
            e.preventDefault();
            $zone.addClass("dragging");
        });
        $zone.on("dragleave", (e) => {
            e.preventDefault();
            $zone.removeClass("dragging");
        });
        $zone.on("drop", (e) => {
            e.preventDefault();
            $zone.removeClass("dragging");
            const files = e.originalEvent && e.originalEvent.dataTransfer
                ? e.originalEvent.dataTransfer.files
                : null;
            if (files && files.length) {
                this._upload_with_files([files[0]]);
            }
        });
        $content.find(".grm-stage-back").on("click", () => this.set_stage("template"));
    }

    _open_uploader() {
        new frappe.ui.FileUploader({
            folder: "Home/Attachments",
            allow_multiple: false,
            disable_file_browser: false,
            allow_toggle_private: false,
            restrictions: {
                allowed_file_types: [".csv", ".xlsx", ".xls"],
                max_file_size: GRM_STEP9_BULK_MAX_FILE_MB * 1024 * 1024,
            },
            on_success: (file_doc) => this._handle_file_doc(file_doc),
        });
    }

    _upload_with_files(files) {
        new frappe.ui.FileUploader({
            files: files,
            folder: "Home/Attachments",
            allow_multiple: false,
            allow_toggle_private: false,
            restrictions: {
                allowed_file_types: [".csv", ".xlsx", ".xls"],
                max_file_size: GRM_STEP9_BULK_MAX_FILE_MB * 1024 * 1024,
            },
            on_success: (file_doc) => this._handle_file_doc(file_doc),
        });
    }

    async _handle_file_doc(file_doc) {
        if (!file_doc || !file_doc.file_url) return;
        this.uploaded_file_url = file_doc.file_url;
        this.uploaded_file_name = file_doc.file_name || file_doc.file_url;
        const $status = this.$mount.find(".grm-upload-status");
        $status
            .removeClass("text-muted text-danger text-success")
            .addClass("text-muted")
            .text(__("Analyzing {0}…", [this.uploaded_file_name]));

        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.auto_detect_user_import_mapping",
                args: { project: this.project.name, file_url: this.uploaded_file_url },
            });
            const m = r.message || {};
            this.headers = m.headers || [];
            this.mapping = m.mapping || {};
            this.project_meta = m.project_meta || {};
            this.validation = m.validation || { ok: false, missing_required: [], errors: [], warnings: [] };
            this.preview_rows = m.preview_rows || [];
            this.total_rows = m.total_rows || 0;
            this.set_stage("mapping");
        } catch (e) {
            $status.removeClass("text-muted text-success").addClass("text-danger")
                .text(__("Could not analyze the file. {0}", [e && e.message ? e.message : ""]));
        }
    }

    // --- Stage 3: mapping ----------------------------------------------------
    _build_target_options() {
        // Mapper dropdown options: skip, User.<field>, Assignment.<field>,
        // administrative_region. Drives the mapping table's <select>s.
        const meta = this.project_meta || {};
        const user_fields = meta.user_fields || [];
        const assignment_fields = meta.assignment_fields || [];

        const options = [{ value: "(skip)", label: __("(skip)") }];

        // Curated subset of User fields — the mapper offers the ones a
        // bulk-import operator is likely to provide. Email/first/last are
        // required (the doctype enforces that); the rest are optional.
        const user_relevant = new Set([
            "email", "first_name", "last_name", "full_name", "username",
            "mobile_no", "phone", "gender",
        ]);
        user_fields.forEach((f) => {
            if (!user_relevant.has(f.fieldname)) return;
            const star = f.reqd ? " *" : "";
            options.push({
                value: `User.${f.fieldname}`,
                label: `${__("User")} → ${f.label}${star}`,
                reqd: !!f.reqd,
            });
        });

        // Assignment fields — exclude framework/system/audit fields and
        // administrative_region (handled separately as a sentinel target).
        const skip_assignment = new Set([
            "project", "user", "name", "owner", "creation",
            "modified", "modified_by", "docstatus", "idx",
            "activation_code", "activation_status", "activation_expires_on",
            "code_sent_on", "activated_on", "activation_attempts",
            "administrative_region",
        ]);
        assignment_fields.forEach((f) => {
            if (skip_assignment.has(f.fieldname)) return;
            if (f.read_only) return;
            const star = f.reqd ? " *" : "";
            options.push({
                value: `Assignment.${f.fieldname}`,
                label: `${__("Assignment")} → ${f.label}${star}`,
                reqd: !!f.reqd,
            });
        });

        options.push({
            value: "administrative_region",
            label: __("Administrative region"),
            reqd: false,
        });
        return options;
    }

    _render_mapping_stage($content) {
        const target_options = this._build_target_options();
        const meta = this.project_meta || {};
        const project_levels = meta.project_levels || [];

        const target_options_html = (selected) => target_options.map((t) => {
            const sel = (t.value === selected) ? "selected" : "";
            return `<option value="${frappe.utils.escape_html(t.value)}" ${sel}>${frappe.utils.escape_html(t.label)}</option>`;
        }).join("");

        const level_options_html = (selected) => project_levels.map((l) => {
            const val = l.name;
            const sel = (val === selected) ? "selected" : "";
            return `<option value="${frappe.utils.escape_html(val)}" ${sel}>${frappe.utils.escape_html(l.level_name || val)}</option>`;
        }).join("");

        const sample_for = (header) => {
            const i = this.headers.indexOf(header);
            const first = this.preview_rows && this.preview_rows[0];
            if (i < 0 || !first || i >= first.length) return "";
            return first[i] == null ? "" : String(first[i]);
        };

        const rows_html = this.headers.map((h) => {
            const m = this.mapping[h] || { target: "(skip)", level_type: null };
            const is_region = m.target === "administrative_region";
            const level_html = is_region ? `
                <select class="form-control form-control-sm grm-level-select" data-header="${frappe.utils.escape_html(h)}">
                  <option value="">${__("(pick level)")}</option>
                  ${level_options_html(m.level_type || "")}
                </select>
            ` : "";
            const warn_html = m.warning
                ? `<span class="text-warning">⚠ ${frappe.utils.escape_html(m.warning)}</span>`
                : "";
            const sample = sample_for(h);
            return `
              <tr data-header="${frappe.utils.escape_html(h)}">
                <td><code>${frappe.utils.escape_html(h)}</code></td>
                <td><code class="text-muted small">${frappe.utils.escape_html(sample)}</code></td>
                <td>
                  <select class="form-control form-control-sm grm-target-select" data-header="${frappe.utils.escape_html(h)}">
                    ${target_options_html(m.target)}
                  </select>
                </td>
                <td class="grm-level-cell">${level_html}</td>
                <td>${warn_html}</td>
              </tr>
            `;
        }).join("");

        const validation_banner = this._render_validation_banner();
        const total_rows_label = this.total_rows === 1
            ? __("1 data row detected")
            : __("{0} data rows detected", [this.total_rows]);

        $content.html(`
            <p>${__("Map each column from your file to a target field. Required fields are marked with an asterisk.")} <span class="text-muted">${total_rows_label}.</span></p>
            <div class="grm-mapper-banner">${validation_banner}</div>
            <div class="grm-mapper-table-wrap">
              <table class="grm-mapper-table">
                <thead>
                  <tr>
                    <th>${__("Source column")}</th>
                    <th>${__("Sample")}</th>
                    <th>${__("Target field")}</th>
                    <th>${__("Level type")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>${rows_html}</tbody>
              </table>
            </div>
            <div class="grm-mapper-options">
              <label>
                <input type="checkbox" class="grm-auto-create-regions" checked>
                ${__("Auto-create missing administrative regions")}
              </label>
              <label class="ml-3" title="${__("Users will log in with their phone number. Username and mobile_no are set from the phone digits; placeholder emails are auto-generated for rows without one.")}">
                <input type="checkbox" class="grm-phone-as-username" checked>
                ${__("Use phone as login (no real email required)")}
              </label>
              <label class="ml-3 grm-synth-domain-wrap">
                ${__("Email domain")}:
                <input type="text" class="form-control form-control-sm grm-synth-domain"
                       placeholder="yopmail.com" value="yopmail.com" style="display:inline-block; width:auto;">
              </label>
              <label class="ml-3 grm-legacy-synth-wrap" title="${__("Legacy: builds firstname.lastname@<domain> for rows without an email. Phone-as-login takes precedence when both are checked.")}">
                <input type="checkbox" class="grm-synthesize-emails">
                ${__("Generate name-based emails (legacy)")}
              </label>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
              <button type="button" class="btn btn-primary grm-stage-next" ${this.validation && this.validation.ok ? "" : "disabled"}>${__("Continue to preview")}</button>
            </div>
        `);

        $content.on("change", ".grm-target-select", (e) => {
            const $sel = $(e.currentTarget);
            const header = $sel.data("header");
            const target = $sel.val();
            this.mapping[header] = this.mapping[header] || {};
            this.mapping[header].target = target;
            // Reset level_type when switching away from region.
            if (target !== "administrative_region") {
                this.mapping[header].level_type = null;
            }
            this._revalidate();
            this._render_mapping_stage($content);
        });
        $content.on("change", ".grm-level-select", (e) => {
            const $sel = $(e.currentTarget);
            const header = $sel.data("header");
            this.mapping[header] = this.mapping[header] || {};
            this.mapping[header].level_type = $sel.val() || null;
            this._revalidate();
            // Re-render to update the validation banner / Continue button.
            this._render_mapping_stage($content);
        });
        // Domain field is visible whenever either synthesis path is on.
        // Phone-as-username defaults to ON so the field starts visible.
        const _refresh_synth_domain_visibility = () => {
            const phone_on = $content.find(".grm-phone-as-username").is(":checked");
            const legacy_on = $content.find(".grm-synthesize-emails").is(":checked");
            $content.find(".grm-synth-domain-wrap").toggle(phone_on || legacy_on);
        };
        $content.on("change", ".grm-phone-as-username, .grm-synthesize-emails", _refresh_synth_domain_visibility);
        _refresh_synth_domain_visibility();
        $content.find(".grm-stage-back").on("click", () => this.set_stage("upload"));
        $content.find(".grm-stage-next").on("click", () => this._start_preview());
    }

    _revalidate() {
        // Doctype-driven required set: Assignment.* with reqd=1, minus fields
        // the operator cannot map (project is set from URL; administrative_region
        // is its own sentinel target; user is auto-derived from User.email
        // during import). Plus the User minimum (email/first/last OR full_name).
        const meta = this.project_meta || {};
        const assignment_fields = meta.assignment_fields || [];
        const non_mappable_assignment = new Set(["project", "administrative_region", "user"]);
        const required = assignment_fields
            .filter((f) => f.reqd && !non_mappable_assignment.has(f.fieldname))
            .map((f) => `Assignment.${f.fieldname}`);

        const targets_in_use = new Set();
        const errors = [];
        const level_seen = new Map(); // level_type -> [headers]
        Object.entries(this.mapping || {}).forEach(([header, m]) => {
            const t = m && m.target;
            if (!t || t === "(skip)") return;
            targets_in_use.add(t);
            if (t === "administrative_region") {
                if (!m.level_type) {
                    errors.push(__("Column '{0}' is mapped to administrative region but has no level type selected.", [header]));
                } else {
                    const arr = level_seen.get(m.level_type) || [];
                    arr.push(header);
                    level_seen.set(m.level_type, arr);
                }
            }
        });
        // At-most-one column per level-type.
        for (const [lt, headers] of level_seen.entries()) {
            if (headers.length > 1) {
                errors.push(__("Multiple columns mapped to admin level '{0}': {1}. Pick exactly one.", [lt, headers.join(", ")]));
            }
        }

        const missing_required = required.filter((r) => !targets_in_use.has(r));
        // User minimum: either full_name OR (email + first + last).
        const has_full_name = targets_in_use.has("User.full_name");
        if (!has_full_name) {
            ["User.email", "User.first_name", "User.last_name"].forEach((t) => {
                if (!targets_in_use.has(t)) missing_required.push(t);
            });
        }

        this.validation = {
            ok: missing_required.length === 0 && errors.length === 0,
            missing_required: missing_required,
            errors: errors,
            warnings: [],
        };
    }

    _render_validation_banner() {
        const v = this.validation || { ok: false, missing_required: [], errors: [] };
        if (v.ok) {
            return `<div class="alert alert-success">${__("Mapping is complete — ready to preview.")}</div>`;
        }
        const parts = [];
        if (v.missing_required && v.missing_required.length) {
            parts.push(`<div>${__("Map these required fields before continuing:")} <code>${v.missing_required.map(frappe.utils.escape_html).join(", ")}</code></div>`);
        }
        if (v.errors && v.errors.length) {
            parts.push(v.errors.map((e) => `<div>${frappe.utils.escape_html(e)}</div>`).join(""));
        }
        return `<div class="alert alert-warning">${parts.join("")}</div>`;
    }

    // --- Stage 4: preview + import ------------------------------------------
    async _start_preview() {
        const $content = this.$mount.find(".grm-step9-bulk-content");
        const auto_create = this.$mount.find(".grm-auto-create-regions").is(":checked");
        const phone_as_username = this.$mount.find(".grm-phone-as-username").is(":checked");
        const synthesize_emails = this.$mount.find(".grm-synthesize-emails").is(":checked");
        const synthesize_email_domain = (this.$mount.find(".grm-synth-domain").val() || "").trim().toLowerCase();

        // Validate the domain whenever any synthesis path is on. Phone-as-
        // username defaults to ``yopmail.com`` server-side when blank, so
        // empty-domain is only a hard error for the legacy path; the
        // server still rejects malformed domains in either mode.
        const domain_re = /^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
        if (synthesize_emails && !phone_as_username) {
            if (!synthesize_email_domain) {
                frappe.msgprint({
                    title: __("Email domain required"),
                    message: __("Enter an email domain (e.g. example.com) to generate emails."),
                    indicator: "orange",
                });
                return;
            }
            if (!domain_re.test(synthesize_email_domain)) {
                frappe.msgprint({
                    title: __("Invalid email domain"),
                    message: __("Email domain '{0}' is not valid.", [synthesize_email_domain]),
                    indicator: "orange",
                });
                return;
            }
        } else if (phone_as_username && synthesize_email_domain && !domain_re.test(synthesize_email_domain)) {
            frappe.msgprint({
                title: __("Invalid email domain"),
                message: __("Email domain '{0}' is not valid.", [synthesize_email_domain]),
                indicator: "orange",
            });
            return;
        }

        // Build the wire-format mappings the server endpoint expects.
        const header_mapping = {};
        const level_mapping = {};
        Object.entries(this.mapping || {}).forEach(([header, m]) => {
            if (!m || !m.target) return;
            header_mapping[header] = m.target;
            if (m.target === "administrative_region" && m.level_type) {
                level_mapping[header] = m.level_type;
            }
        });

        frappe.dom.freeze(__("Preparing preview…"));
        try {
            const r = await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.prepare_user_import",
                args: {
                    project: this.project.name,
                    file_url: this.uploaded_file_url,
                    header_mapping: JSON.stringify(header_mapping),
                    level_mapping: JSON.stringify(level_mapping),
                    auto_create_regions: auto_create ? 1 : 0,
                    synthesize_emails: synthesize_emails ? 1 : 0,
                    synthesize_email_domain: synthesize_email_domain,
                    phone_as_username: phone_as_username ? 1 : 0,
                },
            });
            this.preview = r.message || {};
            this.data_import_name = this.preview.data_import || null;
            this.regions_to_create = this.preview.regions_to_create || [];
            this.set_stage("preview");
        } catch (e) {
            // frappe.call already surfaces server errors via dialog.
        } finally {
            frappe.dom.unfreeze();
        }
    }

    _render_preview_stage($content) {
        const p = this.preview || {};
        const preview_rows = (p.preview || []).slice(0, GRM_STEP9_BULK_PREVIEW_LIMIT);
        const headers = preview_rows.length ? Object.keys(preview_rows[0]) : [];
        const header_html = headers.map((h) => `<th>${frappe.utils.escape_html(h)}</th>`).join("");
        const rows_html = preview_rows.map((row) =>
            `<tr>${headers.map((h) => `<td>${frappe.utils.escape_html(String(row[h] == null ? "" : row[h]))}</td>`).join("")}</tr>`
        ).join("");

        const regions_html = (this.regions_to_create && this.regions_to_create.length) ? `
            <div class="alert alert-info">
              <strong>${__("Regions that will be created:")}</strong>
              ${this.regions_to_create.map((r) => {
                  // Server may return [level_type, value] pairs OR
                  // [level_type, value, parent] triples.
                  const lt = Array.isArray(r) ? r[0] : (r && r.level_type) || "";
                  const v = Array.isArray(r) ? r[1] : (r && r.value) || "";
                  return `<code>${frappe.utils.escape_html(lt)}=${frappe.utils.escape_html(v)}</code>`;
              }).join(", ")}
            </div>` : "";

        const missing_roles = p.missing_roles || [];
        const missing_roles_html = missing_roles.length ? `
            <div class="alert alert-danger">
              <strong>${__("These roles must be created in Step 8 (Roles) first:")}</strong>
              ${missing_roles.map((r) => `<code>${frappe.utils.escape_html(String(r))}</code>`).join(", ")}
            </div>` : "";

        const errors_html = (p.errors && p.errors.length) ? `
            <div class="alert alert-warning">
              ${p.errors.map((e) => `<div>${frappe.utils.escape_html(String(e))}</div>`).join("")}
            </div>` : "";

        const warnings_html = (p.warnings && p.warnings.length) ? `
            <div class="alert alert-info">
              ${p.warnings.map((w) => `<div>${frappe.utils.escape_html(String(w))}</div>`).join("")}
            </div>` : "";

        const summary = __("{0} rows ready, {1} skipped (of {2} total).",
            [p.rows_ready || 0, p.rows_skipped || 0, p.rows_total || 0]);
        const can_start = !!(this.data_import_name && (p.rows_ready || 0) > 0);
        const start_disabled = can_start ? "" : "disabled";
        const no_import_hint = !can_start && (p.rows_ready === 0)
            ? `<p class="text-muted">${__("No rows are ready to import. Adjust your mapping or input file and try again.")}</p>`
            : "";

        $content.html(`
            <p><strong>${frappe.utils.escape_html(summary)}</strong></p>
            ${missing_roles_html}
            ${regions_html}
            ${errors_html}
            ${warnings_html}
            ${headers.length ? `
              <div class="grm-preview-table-wrap">
                <table class="grm-preview-table">
                  <thead><tr>${header_html}</tr></thead>
                  <tbody>${rows_html}</tbody>
                </table>
              </div>
            ` : `<p class="text-muted">${__("No preview rows available.")}</p>`}
            ${no_import_hint}
            <div class="grm-import-progress" hidden>
              <progress class="grm-progress-bar" value="0" max="100"></progress>
              <p class="grm-progress-text text-muted"></p>
              <pre class="grm-progress-log small text-muted"></pre>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-default grm-stage-back">${__("Back")}</button>
              <button type="button" class="btn btn-success grm-import-start" ${start_disabled}>${__("Start import")}</button>
            </div>
        `);

        $content.find(".grm-stage-back").on("click", () => this.set_stage("mapping"));
        $content.find(".grm-import-start").on("click", () => this._start_import());
    }

    async _start_import() {
        if (!this.data_import_name) return;
        const $progress = this.$mount.find(".grm-import-progress");
        $progress.removeAttr("hidden");
        this.$mount.find(".grm-import-start").prop("disabled", true);
        this.$mount.find(".grm-stage-back").prop("disabled", true);
        this.$mount.find(".grm-progress-text").text(__("Starting import…"));
        try {
            await frappe.call({
                method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.start_user_import",
                args: { data_import: this.data_import_name },
            });
            this._poll_progress();
        } catch (e) {
            this.$mount.find(".grm-progress-text")
                .removeClass("text-muted").addClass("text-danger")
                .text(__("Could not start the import."));
            this.$mount.find(".grm-import-start").prop("disabled", false);
            this.$mount.find(".grm-stage-back").prop("disabled", false);
        }
    }

    _poll_progress() {
        const tick = async () => {
            let s = null;
            try {
                const r = await frappe.call({
                    method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.poll_user_import",
                    args: { data_import: this.data_import_name },
                });
                s = r.message || {};
            } catch (e) {
                this.$mount.find(".grm-progress-text").text(__("Polling failed."));
                return;
            }
            const succeeded = s.succeeded || 0;
            const failed = s.failed || 0;
            const done = succeeded + failed;
            const expected = (this.preview && this.preview.rows_ready) || 1;
            const pct = Math.min(100, Math.round((done / expected) * 100));
            this.$mount.find(".grm-progress-bar").val(pct);
            this.$mount.find(".grm-progress-text").text(
                __("{0}: {1} succeeded, {2} failed", [s.status || "", succeeded, failed])
            );
            if (s.import_log_preview) {
                this.$mount.find(".grm-progress-log").text(s.import_log_preview);
            }
            const terminal = ["Success", "Partial Success", "Error", "Failed"];
            if (terminal.indexOf(s.status) >= 0) {
                const indicator = s.status === "Success" ? "green"
                    : (s.status === "Failed" || s.status === "Error") ? "red"
                    : "orange";
                frappe.show_alert({
                    message: __("Import {0}: {1} succeeded, {2} failed", [s.status, succeeded, failed]),
                    indicator: indicator,
                });
                this.$mount.find(".grm-stage-back").prop("disabled", false);
                try { this.on_completed(); } catch (e) { /* non-fatal */ }
                return;
            }
            this.poll_handle = setTimeout(tick, GRM_STEP9_BULK_POLL_MS);
        };
        tick();
    }
}


