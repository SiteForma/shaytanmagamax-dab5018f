import {
  dashboardOverviewApiToViewModel,
  type DashboardOverviewViewModel,
} from "@/adapters/dashboard.adapter";
import { api } from "@/lib/api/client";
export type DashboardOverview = DashboardOverviewViewModel;

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const response = await api.get<any>("/dashboard/overview");
  return dashboardOverviewApiToViewModel(response);
}
