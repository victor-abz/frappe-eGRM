"""One-shot debug helper: dump recent push_changes errors.

Run with::

    bench --site egrm.local execute egrm.cli.dump_push_errors.dump_recent
"""
import frappe


def dump_recent():
    errs = frappe.db.sql(
        """
        SELECT name, creation, method, LEFT(error, 4000) as error
        FROM `tabError Log`
        ORDER BY creation DESC
        LIMIT 6
        """,
        as_dict=True,
    )
    print(f"Most recent 6 errors:")
    for e in errs:
        print('---', e['name'], e['creation'], (e.get('method') or '')[:140])
        print((e.get('error') or '')[:1200])
        print()
    keep = []
    for e in errs:
        err = e["error"] or ""
        if (
            "push_changes" in err
            or "Permission denied to create" in err
            or "validate_user_record_access" in err
            or "administrative_region" in err
        ):
            keep.append(e)
    print(f"matched {len(keep)} of {len(errs)} recent errors")
    for e in keep[:6]:
        print("=" * 80)
        print("METHOD:", e["method"])
        print(e["error"][:3500])
