"""Dump recent Error Log entries for debugging.

Run::

    bench --site egrm.local execute egrm.cli.dump_errlog.main
"""
import frappe


def main(since: str = "2026-05-17 00:09:00", limit: int = 10) -> None:
    rows = frappe.db.sql(
        """
        SELECT name, creation, LEFT(method, 250) AS method, LEFT(error, 6000) AS err
        FROM `tabError Log`
        WHERE creation > %s
        ORDER BY creation DESC LIMIT %s
        """,
        (since, int(limit)),
        as_dict=1,
    )
    out = ["[errlog dump]"]
    for r in rows:
        out.append("=" * 80)
        out.append(f"{r['creation']} | {r['name']}")
        out.append(f"METHOD: {r['method']}")
        out.append(r["err"] or "")
    text = "\n".join(out)
    # Frappe's CLI swallows print(); write to a file we can grep.
    with open("/tmp/errlog_dump.txt", "w") as f:
        f.write(text)
    import sys
    sys.stderr.write(text + "\n")
    sys.stderr.flush()
