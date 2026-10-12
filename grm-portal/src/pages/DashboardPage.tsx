import { useState } from "react";
import { BarChart3, AlertCircle } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import { useProjects } from "@/hooks/useProjects";
import { useTranslate } from "@/hooks/useTranslate";
import BreakdownTable from "@/components/BreakdownTable";
import TrendChart from "@/components/TrendChart";

const dateRanges = [
  { label: "7 Days", value: "7d" },
  { label: "30 Days", value: "30d" },
  { label: "90 Days", value: "90d" },
  { label: "1 Year", value: "1y" },
];

export default function DashboardPage() {
  const { __, lang } = useTranslate();
  const [projectId, setProjectId] = useState("");
  const [dateRange, setDateRange] = useState("30d");

  const { data: projects } = useProjects();
  const { data: dashboardResp, isLoading, error } = useDashboard(
    projectId || undefined,
    dateRange
  );

  const dashboard = dashboardResp?.message?.data;
  const o = dashboard?.overview;
  const num = (n: number) => n.toLocaleString(lang || undefined);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-lg bg-blue-100 p-2">
          <BarChart3 className="h-6 w-6 text-blue-800" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">{__("Public Dashboard")}</h1>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-end gap-4">
        {/* min-w-0 on the flex item, max-w-full on the control. A <select>
            is as wide as its longest <option>, and a flex item's floor is
            its content, so one long project title pushed this past the
            viewport and put a horizontal scrollbar on the whole page --
            on the narrow screens most of these citizens are using. */}
        <div className="min-w-0">
          <label htmlFor="dash-project" className="mb-1 block text-sm font-medium text-grm-secondary">
            {__("Project")}
          </label>
          <select
            id="dash-project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="min-h-[44px] max-w-full truncate rounded-lg border border-grm-field bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-700"
          >
            <option value="">{__("All Projects")}</option>
            {projects?.map((p) => (
              <option key={p.name} value={p.name}>{p.title}</option>
            ))}
          </select>
        </div>

        <fieldset className="min-w-0">
          <legend className="mb-1 block text-sm font-medium text-grm-secondary">
            {__("Period")}
          </legend>
          <div className="flex flex-wrap gap-1.5">
            {dateRanges.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setDateRange(r.value)}
                aria-pressed={dateRange === r.value}
                className={`min-h-[44px] rounded-lg px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-1 ${
                  dateRange === r.value
                    ? "bg-primary-700 text-white shadow-sm"
                    : "border border-grm-field bg-white text-gray-800 hover:bg-gray-50"
                }`}
              >
                {__(r.label)}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      {/* The figures change under the filters without the page moving, so a
          screen reader is told when a new set has arrived. */}
      {/* aria-busy alone. This wrapper also carried aria-live, which made
          every later change inside it -- a chart redrawing, a row
          appearing -- read out as though it were new. The loading and
          empty states below announce themselves with role="status", and
          that is the only thing worth announcing here. */}
      <div aria-busy={isLoading}>
        {isLoading && (
          <div className="py-12 text-center text-grm-secondary" role="status">
            <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-2 border-primary-700 border-t-transparent" />
            <p className="text-sm">{__("Loading metrics...")}</p>
          </div>
        )}

        {error && (
          <div className="py-12 text-center text-red-700" role="alert">
            <AlertCircle className="mx-auto mb-2 h-8 w-8" aria-hidden="true" />
            <p className="text-sm">{__("Failed to load dashboard data.")}</p>
          </div>
        )}

        {dashboard && o && (
          <>
            {/* The same four headline figures the mobile app leads with, so
                a supervisor reading the phone and a citizen reading the web
                are looking at one programme and not two. */}
            <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard
                label={__("Total Issues")}
                value={num(o.total_issues)}
                sub={`+${num(o.issues_this_month)} ${__("in the last 30 days")}`}
                color="text-gray-900"
                bgColor="bg-gray-50"
              />
              <MetricCard
                label={__("This Week")}
                value={num(o.issues_this_week)}
                sub={__("submitted in the last 7 days")}
                color="text-blue-800"
                bgColor="bg-blue-50"
              />
              <MetricCard
                label={__("Resolved")}
                value={num(o.resolved_issues)}
                sub={`${o.resolution_rate}% ${__("resolution rate")}`}
                color="text-green-800"
                bgColor="bg-green-50"
              />
              <MetricCard
                label={__("Avg. Resolution")}
                value={o.avg_resolution_days === null ? "—" : num(o.avg_resolution_days)}
                sub={
                  o.avg_resolution_days === null
                    ? __("nothing resolved yet")
                    : __("days from report to resolution")
                }
                color="text-amber-900"
                bgColor="bg-amber-50"
              />
            </div>

            <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label={__("Open")} value={num(o.open_issues)} color="text-orange-800" bgColor="bg-orange-50" />
              <MetricCard label={__("Pending")} value={num(o.pending_issues)} color="text-indigo-800" bgColor="bg-indigo-50" />
            </div>

            <section className="mb-8 overflow-hidden rounded-xl border border-grm-border">
              <div className="border-b border-grm-border bg-gray-50 px-4 py-3">
                <h2 className="text-sm font-semibold text-gray-900">{__("Submissions over time")}</h2>
              </div>
              <div className="pt-3">
                <TrendChart data={dashboard.trend_data} />
              </div>
            </section>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <BreakdownTable
                title={__("By Status")}
                caption={__("Complaints by status")}
                items={dashboard.status_breakdown.map((s) => ({ label: s.status, count: s.count }))}
              />
              <BreakdownTable
                title={__("By Category")}
                caption={__("Complaints by category")}
                items={dashboard.category_breakdown.map((c) => ({ label: c.category, count: c.count }))}
              />
              <BreakdownTable
                title={__("By Type")}
                caption={__("Complaints by channel the report arrived through")}
                items={dashboard.type_breakdown.map((t) => ({ label: t.issue_type, count: t.count }))}
              />
              <BreakdownTable
                title={__("By Region")}
                caption={__("Complaints by administrative region")}
                items={dashboard.region_breakdown.map((r) => ({ label: r.region, count: r.count }))}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  color,
  bgColor,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
  bgColor: string;
}) {
  return (
    <div className={`${bgColor} rounded-xl border border-grm-border p-4`}>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="mt-1 text-sm font-semibold text-grm-text">{label}</div>
      {sub && <div className="mt-0.5 text-xs leading-snug text-grm-secondary">{sub}</div>}
    </div>
  );
}
