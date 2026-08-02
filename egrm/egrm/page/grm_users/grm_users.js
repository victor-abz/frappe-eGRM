// Custom desk page: "GRM Users by Project".
// Lists GRM User Project Assignment records, grouped by project, with
// create/edit/delete/resend/expire actions. Mirrors the layout/JS
// structure of egrm/page/grm_project_wizard.

frappe.pages["grm-users"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("GRM Users by Project"),
		single_column: true,
	});
	new GRMUsersPage(page);
};

const SERVER = "egrm.egrm.page.grm_users.grm_users";
const ACTIVATION_INDICATOR = {
	Activated: "green",
	"Pending Activation": "blue",
	Expired: "red",
	Suspended: "red",
	Draft: "grey",
};

const PAGE_SIZE_CHOICES = [20, 50, 100];
const DEFAULT_PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 250;

class GRMUsersPage {
	constructor(page) {
		this.page = page;
		this.assignments = [];
		this.projects = [];
		this.editing_name = null; // null = create mode; else doc name
		this.form_open = false;
		this.lookups_cache = {}; // project -> { roles, departments, regions }
		this.selected_project = "all";
		this.form_state = this.empty_form_state();
		this.user_search_timer = null;
		this.user_search_seq = 0;
		this.submitting = false;

		// Pagination + search state
		this.search_query = "";
		this.search_timer = null;
		this.start = 0;
		this.page_length = DEFAULT_PAGE_SIZE;
		this.total_count = 0;
		this.list_seq = 0; // monotonic to discard stale list responses

		this.render_shell();
		this.boot();
	}

	empty_form_state() {
		return {
			user: "",
			user_full_name: "",
			user_email: "",
			project: "",
			role: "",
			department: "",
			administrative_region: "",
			position_title: "",
			is_active: 1,
		};
	}

	// ---------------------------------------------------------------
	// Server helpers
	// ---------------------------------------------------------------
	async call(method, args = {}) {
		try {
			const res = await frappe.call({
				method: `${SERVER}.${method}`,
				args,
			});
			return res ? res.message : null;
		} catch (err) {
			// frappe.call already surfaces the error to the user.
			console.error(`[grm-users] ${method} failed`, err);
			throw err;
		}
	}

	// ---------------------------------------------------------------
	// Boot / shell
	// ---------------------------------------------------------------
	async boot() {
		await this.reload_projects();
		await this.reload_assignments();
	}

	render_shell() {
		const page_size_options = PAGE_SIZE_CHOICES.map((n) => {
			const sel = n === this.page_length ? "selected" : "";
			return `<option value="${n}" ${sel}>${n}</option>`;
		}).join("");

		$(this.page.body).html(`
            <div class="grm-users">
              <div class="grm-users-toolbar">
                <div class="grm-users-toolbar-left">
                  <label class="control-label" for="grm-users-project-filter">
                    ${__("Project")}
                  </label>
                  <select id="grm-users-project-filter" class="form-control">
                    <option value="all">${__("All Projects")}</option>
                  </select>

                  <div class="grm-users-search">
                    <input
                      type="search"
                      id="grm-users-search"
                      class="form-control user-search"
                      placeholder="${__("Search users by name or email…")}"
                      autocomplete="off"
                      value="">
                    <button type="button"
                            id="grm-users-search-clear"
                            class="grm-users-search-clear hidden"
                            aria-label="${__("Clear search")}">×</button>
                  </div>
                </div>
                <div class="grm-users-toolbar-right">
                  <button class="btn btn-primary" id="grm-users-add">
                    + ${__("Add Assignment")}
                  </button>
                </div>
              </div>

              <div id="grm-users-form" class="grm-users-form hidden"></div>

              <div id="grm-users-table-region" class="grm-users-table-region"></div>

              <div class="grm-users-paginator" id="grm-users-paginator">
                <div class="grm-users-paginator-status" id="grm-users-status">
                  ${__("Loading…")}
                </div>
                <div class="grm-users-paginator-controls">
                  <label class="control-label" for="grm-users-page-size">
                    ${__("Page size")}
                  </label>
                  <select id="grm-users-page-size"
                          class="form-control page-size">
                    ${page_size_options}
                  </select>
                  <button type="button"
                          class="btn btn-default btn-sm prev-page"
                          id="grm-users-prev"
                          disabled>‹ ${__("Prev")}</button>
                  <span class="grm-users-page-numbers"
                        id="grm-users-page-numbers"></span>
                  <button type="button"
                          class="btn btn-default btn-sm next-page"
                          id="grm-users-next"
                          disabled>${__("Next")} ›</button>
                </div>
              </div>
            </div>
        `);

		$("#grm-users-project-filter").on("change", (e) => {
			this.selected_project = $(e.currentTarget).val() || "all";
			this.start = 0;
			this.reload_assignments();
		});

		$("#grm-users-add").on("click", () => this.show_form(null));

		// Search input — debounced 250ms, server-side filtering.
		const $search = $("#grm-users-search");
		const $clear = $("#grm-users-search-clear");
		$search.on("input", (e) => {
			const val = $(e.currentTarget).val() || "";
			$clear.toggleClass("hidden", !val);
			if (this.search_timer) clearTimeout(this.search_timer);
			this.search_timer = setTimeout(() => {
				this.search_query = val.trim();
				this.start = 0;
				this.reload_assignments();
			}, SEARCH_DEBOUNCE_MS);
		});
		$clear.on("click", () => {
			$search.val("");
			$clear.addClass("hidden");
			if (this.search_timer) clearTimeout(this.search_timer);
			this.search_query = "";
			this.start = 0;
			this.reload_assignments();
			$search.trigger("focus");
		});

		// Page-size selector.
		$("#grm-users-page-size").on("change", (e) => {
			const n = parseInt($(e.currentTarget).val(), 10) || DEFAULT_PAGE_SIZE;
			this.page_length = n;
			this.start = 0;
			this.reload_assignments();
		});

		// Prev / Next.
		$("#grm-users-prev").on("click", () => {
			const next_start = Math.max(0, this.start - this.page_length);
			if (next_start === this.start) return;
			this.start = next_start;
			this.reload_assignments();
		});
		$("#grm-users-next").on("click", () => {
			const next_start = this.start + this.page_length;
			if (next_start >= this.total_count) return;
			this.start = next_start;
			this.reload_assignments();
		});
	}

	// ---------------------------------------------------------------
	// Projects + assignments loading
	// ---------------------------------------------------------------
	async reload_projects() {
		const rows = (await this.call("list_projects")) || [];
		this.projects = rows;

		const $sel = $("#grm-users-project-filter");
		const current = this.selected_project;
		$sel.empty();
		$sel.append(`<option value="all">${__("All Projects")}</option>`);
		for (const p of rows) {
			const label = frappe.utils.escape_html(p.title || p.name);
			const code = p.project_code ? ` (${frappe.utils.escape_html(p.project_code)})` : "";
			$sel.append(
				`<option value="${frappe.utils.escape_html(p.name)}">${label}${code}</option>`
			);
		}
		// Restore selection if still valid
		if (current && (current === "all" || rows.find((p) => p.name === current))) {
			$sel.val(current);
		}
	}

	async reload_assignments() {
		const project =
			this.selected_project && this.selected_project !== "all"
				? this.selected_project
				: null;
		const seq = ++this.list_seq;
		const resp = await this.call("list_assignments", {
			project,
			search: this.search_query || "",
			start: this.start,
			page_length: this.page_length,
		});
		if (seq !== this.list_seq) return; // stale response — discard

		// Backwards-compat: list_assignments now returns
		//   {rows, total, start, page_length}
		// but historically returned a bare list. Tolerate either shape.
		let rows = [];
		let total = 0;
		if (Array.isArray(resp)) {
			rows = resp;
			total = resp.length;
		} else if (resp && Array.isArray(resp.rows)) {
			rows = resp.rows;
			total = Number.isFinite(resp.total) ? resp.total : rows.length;
		}
		this.assignments = rows;
		this.total_count = total;

		// Defensive: if `start` overshoots after a project/search change,
		// clamp back to page 0 and refetch once.
		if (this.start > 0 && this.start >= total) {
			this.start = 0;
			return this.reload_assignments();
		}

		this.render_table();
		this.render_paginator();
	}

	// ---------------------------------------------------------------
	// Table rendering
	// ---------------------------------------------------------------
	render_table() {
		const $region = $("#grm-users-table-region").empty();

		if (!this.assignments.length) {
			$region.html(`
                <div class="grm-users-empty">
                  <p class="text-muted">${__("No assignments to display.")}</p>
                </div>
            `);
			return;
		}

		const project_title = (name) => {
			const p = this.projects.find((x) => x.name === name);
			return p ? p.title || p.name : name;
		};

		const rows_html = this.assignments
			.map((row) => this.render_row(row, project_title))
			.join("");

		$region.html(`
            <div class="grm-users-table-wrap">
              <table class="table table-bordered grm-users-table">
                <thead>
                  <tr>
                    <th>${__("User")}</th>
                    <th>${__("Project")}</th>
                    <th>${__("Project Role")}</th>
                    <th>${__("Department")}</th>
                    <th>${__("Region")}</th>
                    <th>${__("Active")}</th>
                    <th>${__("Activation")}</th>
                    <th>${__("Code")}</th>
                    <th>${__("Actions")}</th>
                  </tr>
                </thead>
                <tbody>${rows_html}</tbody>
              </table>
            </div>
        `);

		this.bind_row_actions();
	}

	render_paginator() {
		const total = Math.max(0, this.total_count || 0);
		const page_length = Math.max(1, this.page_length || DEFAULT_PAGE_SIZE);
		const start = Math.max(0, this.start || 0);
		const end = total === 0 ? 0 : Math.min(total, start + this.assignments.length);
		const human_start = total === 0 ? 0 : start + 1;

		const $status = $("#grm-users-status");
		if (total === 0) {
			if (this.search_query) {
				$status.text(__("No users match “{0}”.", [this.search_query]));
			} else {
				$status.text(__("No assignments to display."));
			}
		} else {
			$status.text(__("Showing {0}–{1} of {2}", [human_start, end, total]));
		}

		// Page numbers (windowed: current ±2, with first/last anchors).
		const total_pages = Math.max(1, Math.ceil(total / page_length));
		const current_page = Math.floor(start / page_length) + 1;
		const $nums = $("#grm-users-page-numbers").empty();

		const make_btn = (label, page_idx, opts = {}) => {
			const cls = opts.active ? "btn-primary" : "btn-default";
			const disabled = opts.disabled ? "disabled" : "";
			return `
                <button type="button"
                        class="btn ${cls} btn-sm grm-users-page-num"
                        data-page="${page_idx}"
                        ${disabled}>${label}</button>
            `;
		};

		if (total > 0) {
			const pages = new Set();
			// Always include first + last + current ±2.
			pages.add(1);
			pages.add(total_pages);
			for (let p = current_page - 2; p <= current_page + 2; p++) {
				if (p >= 1 && p <= total_pages) pages.add(p);
			}
			const ordered = Array.from(pages).sort((a, b) => a - b);
			let prev_p = 0;
			const html_parts = [];
			for (const p of ordered) {
				if (prev_p && p - prev_p > 1) {
					html_parts.push(`<span class="grm-users-page-ellipsis">…</span>`);
				}
				html_parts.push(make_btn(String(p), p, { active: p === current_page }));
				prev_p = p;
			}
			$nums.html(html_parts.join(""));
			$nums.find(".grm-users-page-num").on("click", (e) => {
				const p = parseInt($(e.currentTarget).data("page"), 10) || 1;
				const next_start = (p - 1) * this.page_length;
				if (next_start === this.start) return;
				this.start = next_start;
				this.reload_assignments();
			});
		}

		$("#grm-users-prev").prop("disabled", start <= 0 || total === 0);
		$("#grm-users-next").prop("disabled", total === 0 || start + page_length >= total);

		// Mark the paginator visible (hidden by default until first load completes).
		$("#grm-users-paginator").toggleClass("is-empty", total === 0);
	}

	render_row(row, project_title) {
		const status = row.activation_status || "Draft";
		const indicator = ACTIVATION_INDICATOR[status] || "grey";
		const can_resend = status === "Pending Activation" || status === "Expired";
		const can_expire = status === "Pending Activation";
		const name_attr = frappe.utils.escape_html(row.name);
		const user_label =
			row.user_full_name && row.user_full_name !== row.user
				? `${frappe.utils.escape_html(
						row.user_full_name
				  )} <small class="text-muted">${frappe.utils.escape_html(row.user)}</small>`
				: frappe.utils.escape_html(row.user || "");
		const role_label = frappe.utils.escape_html(row.role_name || row.role || "");
		const dept_label = frappe.utils.escape_html(row.department_name || row.department || "");
		const region_label = frappe.utils.escape_html(
			row.region_name || row.administrative_region || ""
		);
		const active_badge = row.is_active
			? `<span class="grm-status-badge grm-active-yes">${__("Yes")}</span>`
			: `<span class="grm-status-badge grm-active-no">${__("No")}</span>`;
		const status_badge = `<span class="grm-status-badge grm-indicator-${indicator}">${frappe.utils.escape_html(
			__(status)
		)}</span>`;
		const code_cell = row.activation_code
			? `<code>${frappe.utils.escape_html(row.activation_code)}</code>`
			: "<span class='text-muted'>—</span>";

		return `
            <tr data-name="${name_attr}">
              <td>${user_label}${
			row.position_title
				? `<div class="text-muted small">${frappe.utils.escape_html(
						row.position_title
				  )}</div>`
				: ""
		}</td>
              <td>${frappe.utils.escape_html(project_title(row.project))}</td>
              <td>${role_label}</td>
              <td>${dept_label}</td>
              <td>${region_label}</td>
              <td>${active_badge}</td>
              <td>${status_badge}</td>
              <td>${code_cell}</td>
              <td class="grm-users-actions">
                <button class="btn btn-xs btn-default grm-act-edit"
                        data-name="${name_attr}">${__("Edit")}</button>
                <button class="btn btn-xs btn-default grm-act-resend"
                        data-name="${name_attr}"
                        ${can_resend ? "" : "disabled"}>${__("Resend")}</button>
                <button class="btn btn-xs btn-default grm-act-expire"
                        data-name="${name_attr}"
                        ${can_expire ? "" : "disabled"}>${__("Expire")}</button>
                <button class="btn btn-xs btn-danger grm-act-delete"
                        data-name="${name_attr}">${__("Delete")}</button>
              </td>
            </tr>
        `;
	}

	bind_row_actions() {
		const $tbl = $("#grm-users-table-region");
		$tbl.off("click", ".grm-act-edit").on("click", ".grm-act-edit", (e) => {
			const name = $(e.currentTarget).data("name");
			const row = this.assignments.find((r) => r.name === name);
			if (row) this.show_form(row);
		});
		$tbl.off("click", ".grm-act-delete").on("click", ".grm-act-delete", (e) => {
			const name = $(e.currentTarget).data("name");
			this.on_delete(name);
		});
		$tbl.off("click", ".grm-act-resend").on("click", ".grm-act-resend", (e) => {
			const name = $(e.currentTarget).data("name");
			this.on_resend(name);
		});
		$tbl.off("click", ".grm-act-expire").on("click", ".grm-act-expire", (e) => {
			const name = $(e.currentTarget).data("name");
			this.on_expire(name);
		});
	}

	// ---------------------------------------------------------------
	// Form rendering / state machine
	// ---------------------------------------------------------------
	async show_form(existing) {
		this.editing_name = existing ? existing.name : null;
		this.form_open = true;

		if (existing) {
			this.form_state = {
				user: existing.user || "",
				user_full_name: existing.user_full_name || existing.user || "",
				user_email: "",
				project: existing.project || "",
				role: existing.role || "",
				department: existing.department || "",
				administrative_region: existing.administrative_region || "",
				position_title: existing.position_title || "",
				is_active: existing.is_active ? 1 : 0,
			};
		} else {
			this.form_state = this.empty_form_state();
			// Default project to current filter when not "all"
			if (this.selected_project && this.selected_project !== "all") {
				this.form_state.project = this.selected_project;
			}
		}

		this.render_form_shell();

		if (this.form_state.project) {
			await this.load_lookups(this.form_state.project);
			this.populate_lookup_selects();
		}
	}

	hide_form() {
		this.form_open = false;
		this.editing_name = null;
		this.form_state = this.empty_form_state();
		$("#grm-users-form").addClass("hidden").empty();
	}

	render_form_shell() {
		const editing = !!this.editing_name;
		const title = editing ? __("Edit Assignment") : __("New Assignment");
		const user_locked = editing;
		const project_locked = editing;

		const project_options = [`<option value="">${__("Select project…")}</option>`]
			.concat(
				this.projects.map((p) => {
					const sel = p.name === this.form_state.project ? "selected" : "";
					const label = frappe.utils.escape_html(p.title || p.name);
					return `<option value="${frappe.utils.escape_html(
						p.name
					)}" ${sel}>${label}</option>`;
				})
			)
			.join("");

		const user_value = frappe.utils.escape_html(
			this.form_state.user_full_name
				? `${this.form_state.user_full_name} <${this.form_state.user}>`
				: this.form_state.user
		);

		const html = `
            <div class="grm-users-form-inner">
              <div class="grm-users-form-header">
                <h4>${title}</h4>
                <button class="btn btn-xs btn-default" id="grm-form-close">
                  ${__("Close")}
                </button>
              </div>

              <div class="form-group">
                <label class="control-label reqd">${__("User")}</label>
                ${
					user_locked
						? `<input type="text" class="form-control" id="grm-f-user-display"
                                  value="${user_value}" disabled>`
						: `<div class="grm-user-typeahead">
                              <input type="text" class="form-control" id="grm-f-user-search"
                                     placeholder="${__("Search by name or email…")}"
                                     value="${user_value}"
                                     autocomplete="off">
                              <div id="grm-user-results" class="grm-user-results hidden"></div>
                          </div>`
				}
                <input type="hidden" id="grm-f-user" value="${frappe.utils.escape_html(
					this.form_state.user
				)}">
              </div>

              <div class="form-group">
                <label class="control-label reqd">${__("Project")}</label>
                <select class="form-control" id="grm-f-project" ${
					project_locked ? "disabled" : ""
				}>
                  ${project_options}
                </select>
              </div>

              <div class="form-group">
                <label class="control-label reqd">${__("Project Role")}</label>
                <select class="form-control" id="grm-f-role">
                  <option value="">${__("Select role…")}</option>
                </select>
                <small class="text-muted" id="grm-f-role-hint">
                  ${__("Pick a project to load roles.")}
                </small>
              </div>

              <div class="form-group">
                <label class="control-label">${__("Department")}</label>
                <select class="form-control" id="grm-f-department">
                  <option value="">${__("(none)")}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="control-label">${__("Administrative Region")}</label>
                <select class="form-control" id="grm-f-region">
                  <option value="">${__("(none)")}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="control-label">${__("Position Title")}</label>
                <input type="text" class="form-control" id="grm-f-position-title"
                       value="${frappe.utils.escape_html(this.form_state.position_title)}">
              </div>

              <div class="form-group">
                <label class="checkbox">
                  <input type="checkbox" id="grm-f-is-active"
                         ${this.form_state.is_active ? "checked" : ""}>
                  ${__("Active")}
                </label>
              </div>

              <div class="grm-users-form-footer">
                <button class="btn btn-default" id="grm-form-cancel">${__("Cancel")}</button>
                <button class="btn btn-primary" id="grm-form-submit">
                  ${editing ? __("Save Changes") : __("Create Assignment")}
                </button>
              </div>
            </div>
        `;

		$("#grm-users-form").removeClass("hidden").html(html);
		this.bind_form_events();
	}

	bind_form_events() {
		$("#grm-form-close").on("click", () => this.hide_form());
		$("#grm-form-cancel").on("click", () => this.hide_form());
		$("#grm-form-submit").on("click", () => this.submit_form());

		// Project change reloads lookups
		$("#grm-f-project").on("change", async (e) => {
			const project = $(e.currentTarget).val() || "";
			this.form_state.project = project;
			// Reset dependent fields when project changes
			this.form_state.role = "";
			this.form_state.department = "";
			this.form_state.administrative_region = "";
			if (project) {
				await this.load_lookups(project);
				this.populate_lookup_selects();
			} else {
				this.populate_lookup_selects(true);
			}
		});

		$("#grm-f-role").on("change", (e) => {
			this.form_state.role = $(e.currentTarget).val() || "";
		});
		$("#grm-f-department").on("change", (e) => {
			this.form_state.department = $(e.currentTarget).val() || "";
		});
		$("#grm-f-region").on("change", (e) => {
			this.form_state.administrative_region = $(e.currentTarget).val() || "";
		});
		$("#grm-f-position-title").on("input", (e) => {
			this.form_state.position_title = $(e.currentTarget).val() || "";
		});
		$("#grm-f-is-active").on("change", (e) => {
			this.form_state.is_active = $(e.currentTarget).is(":checked") ? 1 : 0;
		});

		// User typeahead (only on create)
		const $search = $("#grm-f-user-search");
		if ($search.length) {
			$search.on("input", (e) => {
				const txt = $(e.currentTarget).val() || "";
				if (this.user_search_timer) clearTimeout(this.user_search_timer);
				this.user_search_timer = setTimeout(() => this.user_search(txt), 200);
			});
			$search.on("focus", (e) => {
				const txt = $(e.currentTarget).val() || "";
				this.user_search(txt);
			});
			// Hide dropdown on outside click
			$(document)
				.off("click.grmUsers")
				.on("click.grmUsers", (e) => {
					if (!$(e.target).closest(".grm-user-typeahead").length) {
						$("#grm-user-results").addClass("hidden");
					}
				});
		}
	}

	// ---------------------------------------------------------------
	// Lookups
	// ---------------------------------------------------------------
	async load_lookups(project) {
		if (!project) return;
		if (this.lookups_cache[project]) return;
		const data = (await this.call("list_project_lookups", { project })) || {
			roles: [],
			departments: [],
			regions: [],
		};
		this.lookups_cache[project] = data;
	}

	populate_lookup_selects(empty = false) {
		const data = empty
			? { roles: [], departments: [], regions: [] }
			: this.lookups_cache[this.form_state.project] || {
					roles: [],
					departments: [],
					regions: [],
			  };

		const $role = $("#grm-f-role").empty();
		$role.append(`<option value="">${__("Select role…")}</option>`);
		for (const r of data.roles || []) {
			const sel = r.name === this.form_state.role ? "selected" : "";
			const label = frappe.utils.escape_html(r.role_name || r.name);
			$role.append(
				`<option value="${frappe.utils.escape_html(r.name)}" ${sel}>${label}</option>`
			);
		}
		const $hint = $("#grm-f-role-hint");
		if ((data.roles || []).length) {
			$hint.text(__("Choose a project role for this assignment."));
		} else if (this.form_state.project) {
			$hint.text(__("No active roles for this project. Define one first."));
		} else {
			$hint.text(__("Pick a project to load roles."));
		}

		const $dept = $("#grm-f-department").empty();
		$dept.append(`<option value="">${__("(none)")}</option>`);
		for (const d of data.departments || []) {
			const sel = d.name === this.form_state.department ? "selected" : "";
			const label = frappe.utils.escape_html(d.department_name || d.name);
			$dept.append(
				`<option value="${frappe.utils.escape_html(d.name)}" ${sel}>${label}</option>`
			);
		}

		const $region = $("#grm-f-region").empty();
		$region.append(`<option value="">${__("(none)")}</option>`);
		for (const r of data.regions || []) {
			const sel = r.name === this.form_state.administrative_region ? "selected" : "";
			const label = frappe.utils.escape_html(r.region_name || r.name);
			$region.append(
				`<option value="${frappe.utils.escape_html(r.name)}" ${sel}>${label}</option>`
			);
		}
	}

	// ---------------------------------------------------------------
	// User typeahead
	// ---------------------------------------------------------------
	async user_search(txt) {
		const seq = ++this.user_search_seq;
		const results = (await this.call("search_users", { txt })) || [];
		if (seq !== this.user_search_seq) return; // stale response — discard

		const $box = $("#grm-user-results");
		if (!results.length) {
			$box.html(
				`<div class="grm-user-result-empty text-muted">${__("No users found.")}</div>`
			).removeClass("hidden");
			return;
		}
		const html = results
			.map((u) => {
				const id = frappe.utils.escape_html(u.name);
				const label = frappe.utils.escape_html(u.full_name || u.name);
				const email = frappe.utils.escape_html(u.email || u.name);
				return `
                    <div class="grm-user-result" data-name="${id}"
                         data-full-name="${label}" data-email="${email}">
                      <div class="grm-user-result-name">${label}</div>
                      <div class="grm-user-result-email text-muted small">${email}</div>
                    </div>
                `;
			})
			.join("");
		$box.html(html).removeClass("hidden");
		$box.find(".grm-user-result").on("click", (e) => {
			const $el = $(e.currentTarget);
			this.pick_user({
				name: $el.data("name"),
				full_name: $el.data("full-name"),
				email: $el.data("email"),
			});
		});
	}

	pick_user(user) {
		this.form_state.user = user.name;
		this.form_state.user_full_name = user.full_name || user.name;
		this.form_state.user_email = user.email || "";
		$("#grm-f-user").val(user.name);
		$("#grm-f-user-search").val(`${this.form_state.user_full_name} <${user.name}>`);
		$("#grm-user-results").addClass("hidden");
	}

	// ---------------------------------------------------------------
	// Submit
	// ---------------------------------------------------------------
	async submit_form() {
		if (this.submitting) return;

		// Validate
		if (!this.form_state.user) {
			frappe.show_alert({ message: __("Please pick a user."), indicator: "red" });
			return;
		}
		if (!this.form_state.project) {
			frappe.show_alert({ message: __("Please pick a project."), indicator: "red" });
			return;
		}
		if (!this.form_state.role) {
			frappe.show_alert({
				message: __("Please pick a project role."),
				indicator: "red",
			});
			return;
		}

		const payload = {
			user: this.form_state.user,
			project: this.form_state.project,
			role: this.form_state.role,
			department: this.form_state.department || null,
			administrative_region: this.form_state.administrative_region || null,
			position_title: this.form_state.position_title || null,
			is_active: this.form_state.is_active ? 1 : 0,
		};

		this.submitting = true;
		const $btn = $("#grm-form-submit").prop("disabled", true);
		try {
			if (this.editing_name) {
				await this.call("update_assignment", {
					name: this.editing_name,
					payload,
				});
				frappe.show_alert({
					message: __("Assignment updated"),
					indicator: "green",
				});
			} else {
				await this.call("create_assignment", { payload });
				frappe.show_alert({
					message: __("Assignment created"),
					indicator: "green",
				});
			}
			this.hide_form();
			await this.reload_assignments();
		} catch (e) {
			// frappe.call already surfaced the error
		} finally {
			this.submitting = false;
			$btn.prop("disabled", false);
		}
	}

	// ---------------------------------------------------------------
	// Row actions
	// ---------------------------------------------------------------
	on_delete(name) {
		if (!name) return;
		frappe.confirm(
			__("Delete this assignment? The user's project access will be revoked."),
			async () => {
				try {
					await this.call("delete_assignment", { name });
					frappe.show_alert({
						message: __("Assignment deleted"),
						indicator: "green",
					});
					await this.reload_assignments();
				} catch (e) {
					/* error already surfaced */
				}
			}
		);
	}

	async on_resend(name) {
		if (!name) return;
		try {
			await this.call("resend_activation", { name });
			frappe.show_alert({
				message: __("Activation code resent"),
				indicator: "green",
			});
			await this.reload_assignments();
		} catch (e) {
			/* error already surfaced */
		}
	}

	async on_expire(name) {
		if (!name) return;
		frappe.confirm(__("Expire this activation code?"), async () => {
			try {
				await this.call("expire_activation", { name });
				frappe.show_alert({
					message: __("Activation code expired"),
					indicator: "orange",
				});
				await this.reload_assignments();
			} catch (e) {
				/* error already surfaced */
			}
		});
	}
}
