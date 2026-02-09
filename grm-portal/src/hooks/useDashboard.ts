import { useFrappeGetCall } from "frappe-react-sdk";

export interface DashboardOverview {
  total_issues: number;
  open_issues: number;
  resolved_issues: number;
  pending_issues: number;
}

export interface DashboardData {
  overview: DashboardOverview;
  status_breakdown: { status: string; count: number }[];
  category_breakdown: { category: string; count: number }[];
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
