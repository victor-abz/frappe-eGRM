import { useMemo } from "react";
import { useTranslate } from "@/hooks/useTranslate";

type Point = { date: string; count: number };

const VIEW_W = 720;
const VIEW_H = 180;
const PAD_L = 32;
const PAD_R = 8;
const PAD_T = 12;
const PAD_B = 24;

function formatDay(iso: string, lang: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang || undefined, { day: "numeric", month: "short" });
}

/**
 * The mobile Statistics screen plots submissions over time; the public
 * dashboard returned the same series from the API and then threw it away.
 *
 * Drawn by hand in SVG rather than pulled from a charting library: the
 * portal ships no chart dependency, and a citizen on a metered connection
 * should not download 400KB of library to see thirty numbers. The series
 * is also emitted as a real table for screen readers, because a path
 * element conveys nothing to one.
 */
export default function TrendChart({ data }: { data: Point[] }) {
  const { __, lang } = useTranslate();

  const { line, area, max, ticks } = useMemo(() => {
    const max = Math.max(1, ...data.map((d) => d.count));
    const innerW = VIEW_W - PAD_L - PAD_R;
    const innerH = VIEW_H - PAD_T - PAD_B;
    const x = (i: number) =>
      PAD_L + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = (v: number) => PAD_T + innerH - (v / max) * innerH;

    const line = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d.count).toFixed(1)}`).join(" ");
    const area =
      data.length === 0
        ? ""
        : `${line} L${x(data.length - 1).toFixed(1)},${(PAD_T + innerH).toFixed(1)} L${x(0).toFixed(1)},${(PAD_T + innerH).toFixed(1)} Z`;

    // Only the ends and the middle are labelled -- thirty dates along a
    // phone-width axis is noise, not information.
    const idxs = data.length <= 2 ? data.map((_, i) => i) : [0, Math.floor((data.length - 1) / 2), data.length - 1];
    const ticks = idxs.map((i) => ({ i, x: x(i), label: formatDay(data[i].date, lang) }));

    return { line, area, max, ticks };
  }, [data, lang]);

  const total = data.reduce((sum, d) => sum + d.count, 0);

  if (data.length === 0) {
    return (
      <p className="px-4 py-6 text-center text-sm text-grm-secondary">{__("No data")}</p>
    );
  }

  return (
    <div>
      {/* A fixed height with preserveAspectRatio="none" stretched the
          drawing horizontally by whatever the container happened to be,
          so the same series looked steeper on a phone than on a laptop and
          the 11px tick labels were squashed with it. Letting the box keep
          the viewBox's ratio means the curve is drawn to scale at every
          width. */}
      <div className="relative" style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="h-full w-full"
        role="img"
        aria-label={__("Complaints submitted per day over the selected period")}
      >
        {/* Horizontal guides at 0, half and peak, so a reader can judge the
            height of the curve without hovering anything. */}
        {[0, 0.5, 1].map((f) => {
          const yy = PAD_T + (VIEW_H - PAD_T - PAD_B) * (1 - f);
          return (
            <g key={f}>
              <line x1={PAD_L} y1={yy} x2={VIEW_W - PAD_R} y2={yy} stroke="#EDEDED" strokeWidth={1} />
            </g>
          );
        })}
        <path d={area} fill="#17855b" fillOpacity={0.12} />
        <path d={line} fill="none" stroke="#17855b" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      </svg>

      {/* The axis labels are HTML laid over the drawing, not <text> inside
          it. Inside, their size was in viewBox user units, which scale with
          the box: 11 units in a 720-unit-wide viewBox rendered at about 5
          CSS pixels on a 360px phone, a third of the body size and immune to
          browser text zoom, which does not touch SVG user units. As HTML
          they are real pixels at every width. Percentages place them because
          the box keeps the viewBox's ratio, so viewBox coordinates and
          percentages of the rendered box are the same thing. */}
      <div className="pointer-events-none absolute inset-0 text-xs text-grm-secondary">
        {[0, 0.5, 1].map((f) => {
          const yy = PAD_T + (VIEW_H - PAD_T - PAD_B) * (1 - f);
          return (
            <span
              key={f}
              className="absolute -translate-y-1/2 tabular-nums"
              style={{ left: 0, top: `${(yy / VIEW_H) * 100}%` }}
            >
              {Math.round(max * f)}
            </span>
          );
        })}
        {ticks.map((t) => (
          <span
            key={t.i}
            className="absolute bottom-0 whitespace-nowrap"
            style={{
              left: `${(t.x / VIEW_W) * 100}%`,
              transform:
                t.i === 0
                  ? "none"
                  : t.i === data.length - 1
                    ? "translateX(-100%)"
                    : "translateX(-50%)",
            }}
          >
            {t.label}
          </span>
        ))}
      </div>
      </div>

      <p className="px-4 pb-3 text-sm text-grm-secondary">
        {__("Total in period")}: <strong className="text-grm-text">{total.toLocaleString(lang || undefined)}</strong>
      </p>

      <table className="sr-only">
        <caption>{__("Complaints submitted per day")}</caption>
        <thead>
          <tr>
            <th scope="col">{__("Date")}</th>
            <th scope="col">{__("Complaints")}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.date}>
              <th scope="row">{d.date}</th>
              <td>{d.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
