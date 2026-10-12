import { useTranslate } from "@/hooks/useTranslate";

export type BreakdownItem = { label: string; count: number };

/**
 * A real <table>, not a stack of divs. The previous markup gave a screen
 * reader a flat run of words and numbers with no column headers and no row
 * relationship, which is exactly the information the table conveys.
 *
 * The bar is a second, redundant encoding of the same number -- the figure
 * is always printed, so nothing depends on seeing the bar or on telling
 * its colour apart.
 */
export default function BreakdownTable({
  title,
  items,
  caption,
}: {
  title: string;
  items: BreakdownItem[];
  caption: string;
}) {
  const { __, lang } = useTranslate();
  const total = items.reduce((sum, i) => sum + i.count, 0);
  const max = Math.max(1, ...items.map((i) => i.count));

  return (
    <section className="overflow-hidden rounded-xl border border-grm-border">
      {/* h2, not h3. These four sections sit beside the trend chart's own
          h2 directly under the page h1, so an h3 here announced them as
          sub-parts of the chart above rather than as four tables of their
          own. Nothing on the page is deeper than level 2. */}
      <div className="border-b border-grm-border bg-gray-50 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
      </div>

      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-grm-secondary">{__("No data")}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col" className="sr-only">{title}</th>
              <th scope="col" className="sr-only">{__("Complaints")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const pct = total ? Math.round((item.count / total) * 100) : 0;
              return (
                <tr key={item.label} className={idx % 2 === 1 ? "bg-gray-50" : undefined}>
                  <th
                    scope="row"
                    className="px-4 py-2.5 text-left font-medium text-gray-800"
                  >
                    {__(item.label)}
                  </th>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-3">
                      <div
                        aria-hidden="true"
                        className="hidden h-2 w-20 shrink-0 overflow-hidden rounded-full bg-gray-200 sm:block"
                      >
                        <div
                          className="h-full rounded-full bg-primary-700"
                          style={{ width: `${Math.round((item.count / max) * 100)}%` }}
                        />
                      </div>
                      <span className="whitespace-nowrap tabular-nums text-gray-900">
                        <span className="font-semibold">
                          {item.count.toLocaleString(lang || undefined)}
                        </span>{" "}
                        <span className="text-grm-secondary">({pct}%)</span>
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
