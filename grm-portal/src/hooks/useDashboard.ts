import { useFrappeGetCall } from "frappe-react-sdk";

export interface DashboardOverview {
  total_issues: number;
  open_issues: number;
  resolved_issues: number;
  pending_issues: number;
  issues_this_week: number;
  issues_this_month: number;
  /** Percentage, already rounded to one decimal by the server. */
  resolution_rate: number;
  /** null when nothing has been resolved yet -- distinct from 0 days. */
  avg_resolution_days: number | null;
}

export interface DashboardData {
  overview: DashboardOverview;
  status_breakdown: { status: string; count: number }[];
  category_breakdown: { category: string; count: number }[];
  type_breakdown: { issue_type: string; count: number }[];
  region_breakdown: { region: string; count: number }[];
  trend_data: { date: string; count: number }[];
}

export function useDashboard(projectId?: string, dateRange?: string) {
  return useFrappeGetCall<{ message: { data: DashboardData } }>(
    "egrm.api.public_metrics.get_public_dashboard",
    {
      project_id: projectId || undefined,
      date_range: dateRange || "30d",
    }
  );
}
