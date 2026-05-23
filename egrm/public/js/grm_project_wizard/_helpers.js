
// Display order is dependency-driven, NOT class-name order:
//   Categories (now display 5) needs Roles + Departments to exist first,
//   so User Types and Departments are promoted to display 3 and 4. The
//   underlying step classes keep their original numeric names — only the
//   slot they occupy in `step_class()` and the title shown to the user
//   changes. See comments above `step_class()` for the full mapping.
const STEP_TITLES = [
    "",
    "Project Information",            //  1
    "Administrative Levels & Regions", //  2
    "User Types",                     //  3 (was 7) — must precede Categories
    "Departments",                    //  4 (was 8) — must precede Categories
    "Issue Categories",               //  5 (was 3)
    "Issue Types",                    //  6 (was 4)
    "Citizen Groups",                 //  7 (was 5)
    "Notification Templates",         //  8 (was 6)
    "Users",                          //  9
    "Issue Routing",                  // 10
    "SLAs",                           // 11
    "Issue Statuses",                 // 12
    "Activate",                       // 13
];

const TOTAL_STEPS = 13;

// ---------------------------------------------------------------------------
// Reusable bulk-selection helper for wizard tables that use the simple HTML
// `<table class="table table-borderless">` markup (Steps 5, 6, 7, 8, 9, 11, 12).
// Steps 3 and 4 use the Frappe div-grid pattern and inline their own bulk
// wiring — see `bind_bulk_select` / `refresh_bulk_actions` on those classes.
//
// Caller responsibilities:
//   1. Maintain `this.selected = new Set()` on the step instance and pass it in.
//   2. Render `${grm_render_bulk_toolbar(key)}` above the table.
//   3. Add a leading checkbox cell to the header + each row:
//          <th class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-all"></th>
//          <td class="grm-bulk-cell"><input type="checkbox" class="grm-bulk-row-check"></td>
//      Each <tr> must carry `data-name="{row.name}"`.
//   4. After mounting, call `grm_wire_bulk_table($wrap, opts)`.
//
// The helper is idempotent: it namespaces handlers (`.grm-bulk`) and rebinds
// safely on every re-render.
// ---------------------------------------------------------------------------
function grm_render_bulk_toolbar(key) {
    return `
      <div class="grm-bulk-actions" data-grm-bulk-for="${key}" hidden>
        <span class="grm-bulk-count"></span>
        <button type="button" class="btn btn-xs btn-danger grm-bulk-delete">${__("Delete")}</button>
        <button type="button" class="btn btn-xs btn-secondary grm-bulk-clear">${__("Clear selection")}</button>
      </div>
    `;
}

function grm_wire_bulk_table($wrap, opts) {
    const { selected, row_names, key, delete_one, on_done } = opts;
    const singular = opts.singular || __("row");
    const plural = opts.plural || (singular + "s");
    const confirm_msg = opts.confirm_msg || ((n) => n === 1
        ? __("Delete this {0}?", [singular])
        : __("Delete {0} selected {1}?", [n, plural]));

    const $bar = $wrap.find(`.grm-bulk-actions[data-grm-bulk-for='${key}']`);
    const $tbl = $wrap.find("table");

    function refresh() {
        const n = selected.size;
        $bar.attr("hidden", n === 0 ? "hidden" : null);
        $bar.find(".grm-bulk-count").text(
            n === 0 ? "" : (n === 1 ? __("1 selected") : __("{0} selected", [n])),
        );
        $bar.find(".grm-bulk-delete").text(
            n <= 1 ? __("Delete") : __("Delete {0}", [n]),
        );
        const total = row_names.length;
        const $all = $tbl.find(".grm-bulk-all");
        if (total > 0) {
            $all.prop("checked", n === total);
            $all.prop("indeterminate", n > 0 && n < total);
        }
        $tbl.find(".grm-bulk-row-check").each(function () {
            const name = $(this).closest("tr").attr("data-name");
            $(this).prop("checked", !!name && selected.has(name));
        });
    }

    $wrap.off(".grm-bulk")
        .on("change.grm-bulk", ".grm-bulk-all", function () {
            const checked = $(this).prop("checked");
            if (checked) row_names.forEach((n) => selected.add(n));
            else selected.clear();
            refresh();
        })
        .on("change.grm-bulk", ".grm-bulk-row-check", function () {
            const name = $(this).closest("tr").attr("data-name");
            if (!name) return;
            if ($(this).prop("checked")) selected.add(name);
            else selected.delete(name);
            refresh();
        })
        .on("click.grm-bulk", ".grm-bulk-clear", () => {
            selected.clear();
            refresh();
        })
        .on("click.grm-bulk", ".grm-bulk-delete", async () => {
            const names = [...selected];
            if (!names.length) return;
            const proceed = await new Promise((res) =>
                frappe.confirm(confirm_msg(names.length), () => res(true), () => res(false)),
            );
            if (!proceed) return;
            const errs = [];
            frappe.dom.freeze(__("Deleting…"));
            for (const name of names) {
                try { await delete_one(name); }
                catch (e) { errs.push(name); }
            }
            frappe.dom.unfreeze();
            selected.clear();
            if (errs.length) {
                frappe.show_alert({
                    message: __("Could not delete {0} {1} — they may still be referenced.",
                        [errs.length, errs.length === 1 ? singular : plural]),
                    indicator: "red",
                });
            } else {
                frappe.show_alert({
                    message: __("{0} {1} deleted.",
                        [names.length, names.length === 1 ? singular : plural]),
                    indicator: "green",
                });
            }
            if (on_done) await on_done();
        });

    refresh();
}

