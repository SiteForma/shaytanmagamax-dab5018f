import {
  adminHealthDetailsApiToViewModel,
  adminJobApiToViewModel,
  adminSystemFreshnessApiToViewModel,
  adminUserApiToViewModel,
  paginatedAdminJobsApiToViewModel,
  paginatedAuditEventsApiToViewModel,
} from "@/adapters/admin.adapter";
import { api } from "@/lib/api/client";
import type {
  AdminHealthDetails,
  AdminJob,
  AdminSystemFreshness,
  AdminUser,
  AuditEvent,
  PaginatedResult,
} from "@/types";

export async function getAdminUsers(): Promise<AdminUser[]> {
  const response = await api.get<any[]>("/admin/users");
  return response.map(adminUserApiToViewModel);
}

export async function updateAdminUserRole(userId: string, role: string): Promise<AdminUser> {
  const response = await api.patch<any>(`/admin/users/${userId}/role`, { role });
  return adminUserApiToViewModel(response);
}

export async function getAdminJobs(filters: {
  status?: string;
  queueName?: string;
  jobName?: string;
} = {}): Promise<PaginatedResult<AdminJob>> {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.queueName) query.set("queueName", filters.queueName);
  if (filters.jobName) query.set("jobName", filters.jobName);
  const response = await api.get<any>(`/admin/jobs${query.size ? `?${query.toString()}` : ""}`);
  return paginatedAdminJobsApiToViewModel(response);
}

export async function retryAdminJob(jobId: string): Promise<AdminJob> {
  const response = await api.post<any>(`/admin/jobs/${jobId}/retry`, {});
  return adminJobApiToViewModel(response);
}

export async function getAdminAuditEvents(filters: {
  action?: string;
  targetType?: string;
  page?: number;
  pageSize?: number;
}): Promise<PaginatedResult<AuditEvent>> {
  const query = new URLSearchParams();
  if (filters.action) query.set("action", filters.action);
  if (filters.targetType) query.set("targetType", filters.targetType);
  if (filters.page) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("pageSize", String(filters.pageSize));
  const response = await api.get<any>(`/admin/audit-events${query.size ? `?${query.toString()}` : ""}`);
  return paginatedAuditEventsApiToViewModel(response);
}

export async function getAdminSystemFreshness(): Promise<AdminSystemFreshness> {
  const response = await api.get<any>("/admin/system/freshness");
  return adminSystemFreshnessApiToViewModel(response);
}

export async function getAdminHealthDetails(): Promise<AdminHealthDetails> {
  const response = await api.get<any>("/admin/system/health-details");
  return adminHealthDetailsApiToViewModel(response);
}
