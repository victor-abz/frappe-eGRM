import { useState } from "react";
import { BarChart3, AlertCircle } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import { useProjects } from "@/hooks/useProjects";
import { useTranslate } from "@/hooks/useTranslate";

const dateRanges = [
  { label: "7 Days", value: "7d" },
  { label: "30 Days", value: "30d" },
  { label: "90 Days", value: "90d" },
  { label: "1 Year", value: "1y" },
];

export default function DashboardPage() {
  const { __ } = useTranslate();
  const [projectId, setProjectId] = useState("");
  const [dateRange, setDateRange] = useState("30d");

  const { data: projects } = useProjects();
  const { data: dashboardResp, isLoading, error } = useDashboard(
    projectId || undefined,
    dateRange
  );

  const dashboard = dashboardResp?.message?.data;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-blue-100 rounded-lg">
          <BarChart3 className="w-6 h-6 text-blue-700" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">{__("Public Dashboard")}</h1>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">{__("All Projects")}</option>
          {projects?.map((p) => (
            <option key={p.name} value={p.name}>{p.title}</option>
          ))}
        </select>

        <div className="flex gap-1.5">
          {dateRanges.map((r) => (
            <button
              key={r.value}
              onClick={() => setDateRange(r.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                dateRange === r.value
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
              }`}
            >
              {__(r.label)}
            </button>
          ))}
        </div>
      </div>

      {/* Loading / Error */}
      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-2" />
          <p className="text-sm">{__("Loading metrics...")}</p>
        </div>
      )}

      {error && (
        <div className="text-center py-12 text-red-500">
          <AlertCircle className="w-8 h-8 mx-auto mb-2" />
          <p className="text-sm">{__("Failed to load dashboard data.")}</p>
        </div>
      )}

      {dashboard && (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <MetricCard label={__("Total Issues")} value={dashboard.overview.total_issues} color="text-gray-900" bgColor="bg-gray-50" />
            <MetricCard label={__("Open")} value={dashboard.overview.open_issues} color="text-orange-600" bgColor="bg-orange-50" />
            <MetricCard label={__("Resolved")} value={dashboard.overview.resolved_issues} color="text-green-600" bgColor="bg-green-50" />
            <MetricCard label={__("Pending")} value={dashboard.overview.pending_issues} color="text-blue-600" bgColor="bg-blue-50" />
          </div>

          {/* Breakdown Tables */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <BreakdownTable title={__("By Status")} items={dashboard.status_breakdown.map((s) => ({ label: s.status, count: s.count }))} />
            <BreakdownTable title={__("By Category")} items={dashboard.category_breakdown.map((c) => ({ label: c.category, count: c.count }))} />
            <BreakdownTable title={__("By Region")} items={dashboard.region_breakdown.map((r) => ({ label: r.region, count: r.count }))} />
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value, color, bgColor }: { label: string; value: number; color: string; bgColor: string }) {
  return (
    <div className={`${bgColor} rounded-xl p-4 border border-grm-border`}>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-grm-muted mt-1">{label}</div>
    </div>
  );
}

function BreakdownTable({ title, items }: { title: string; items: { label: string; count: number }[] }) {
  const { __ } = useTranslate();
  return (
    <div className="border border-grm-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-grm-border">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-grm-muted">{__("No data")}</div>
      ) : (
        <div>
          {items.map((item, idx) => (
            <div key={item.label} className={`flex items-center justify-between px-4 py-2.5 text-sm ${idx % 2 === 1 ? "bg-gray-50" : ""}`}>
              <span className="text-gray-700">{__(item.label)}</span>
              <span className="inline-flex items-center justify-center min-w-[28px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">
                {item.count}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
