import type {
  AliasEntry,
  MappingField,
  MappingTemplate,
  PaginatedResult,
  UploadFileDetail,
  UploadIssue,
  UploadJob,
  UploadMappingState,
  UploadPreview,
} from "@/types";
import {
  aliasEntryApiToViewModel,
  mappingFieldApiToViewModel,
  mappingTemplateApiToViewModel,
  paginatedUploadIssuesApiToViewModel,
  paginatedUploadJobsApiToViewModel,
  uploadFileDetailApiToViewModel,
  uploadMappingApiToViewModel,
  uploadPreviewApiToViewModel,
} from "@/adapters/upload.adapter";
import { api } from "@/lib/api/client";

type PaginatedResponse<T> = {
  items: T[];
  meta: {
    page: number;
    pageSize: number;
    total: number;
  };
};

export async function getUploadJobs(
  filters: {
    status?: UploadJob["state"];
    sourceType?: UploadJob["sourceType"];
    page?: number;
    pageSize?: number;
  } = {},
): Promise<PaginatedResult<UploadJob>> {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.sourceType) query.set("source_type", filters.sourceType);
  if (filters.page) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  const response = await api.get<PaginatedResponse<any>>(
    `/uploads/files${query.size ? `?${query.toString()}` : ""}`,
  );
  return paginatedUploadJobsApiToViewModel(response);
}

export async function getUploadFileDetail(fileId: string): Promise<UploadFileDetail> {
  const response = await api.get<any>(`/uploads/files/${fileId}`);
  return uploadFileDetailApiToViewModel(response);
}

export async function getUploadPreview(fileId: string): Promise<UploadPreview> {
  const response = await api.get<any>(`/uploads/files/${fileId}/preview`);
  return uploadPreviewApiToViewModel(response);
}

export async function getUploadMapping(fileId: string): Promise<UploadMappingState> {
  const response = await api.get<any>(`/uploads/files/${fileId}/mapping`);
  return uploadMappingApiToViewModel(response);
}

export async function getUploadIssues(
  fileId: string,
  filters: { severity?: string; page?: number; pageSize?: number } = {},
): Promise<PaginatedResult<UploadIssue>> {
  const query = new URLSearchParams();
  if (filters.severity) query.set("severity", filters.severity);
  if (filters.page) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  const response = await api.get<PaginatedResponse<any>>(
    `/uploads/files/${fileId}/issues${query.size ? `?${query.toString()}` : ""}`,
  );
  return paginatedUploadIssuesApiToViewModel(response);
}

export async function getMappingFields(batchId?: string): Promise<MappingField[]> {
  const query = batchId ? `?batch_id=${batchId}` : "";
  const response = await api.get<any[]>(`/mapping/suggestions${query}`);
  return response.map(mappingFieldApiToViewModel);
}

export async function createUploadJob(file: File, sourceType?: UploadJob["sourceType"]) {
  const formData = new FormData();
  formData.set("file", file);
  if (sourceType) formData.set("source_type", sourceType);
  const response = await api.postForm<any>("/uploads/files", formData);
  return uploadFileDetailApiToViewModel(response);
}

export async function suggestMappingForUpload(
  fileId: string,
  templateId?: string,
): Promise<UploadFileDetail> {
  const query = templateId ? `?template_id=${templateId}` : "";
  const response = await api.post<any>(`/uploads/files/${fileId}/mapping/suggest${query}`, {});
  return uploadFileDetailApiToViewModel(response);
}

export async function saveUploadMapping(
  fileId: string,
  mappings: Record<string, string>,
  templateId?: string,
): Promise<UploadFileDetail> {
  const response = await api.post<any>(`/uploads/files/${fileId}/mapping`, {
    mappings,
    template_id: templateId,
  });
  return uploadFileDetailApiToViewModel(response);
}

export async function validateUpload(fileId: string): Promise<UploadFileDetail> {
  const response = await api.post<any>(`/uploads/files/${fileId}/validate`, {});
  return uploadFileDetailApiToViewModel(response);
}

export async function applyUpload(fileId: string) {
  return api.post<any>(`/uploads/files/${fileId}/apply`, {});
}

export async function getMappingTemplates(
  sourceType?: UploadJob["sourceType"],
): Promise<MappingTemplate[]> {
  const query = sourceType ? `?source_type=${sourceType}` : "";
  const response = await api.get<any[]>(`/mapping/templates${query}`);
  return response.map(mappingTemplateApiToViewModel);
}

export async function createMappingTemplate(payload: {
  name: string;
  sourceType: UploadJob["sourceType"];
  mappings: Record<string, string>;
  requiredFields?: string[];
  transformationHints?: Record<string, unknown>;
  isDefault?: boolean;
  isActive?: boolean;
}): Promise<MappingTemplate> {
  const response = await api.post<any>("/mapping/templates", {
    name: payload.name,
    source_type: payload.sourceType,
    mappings: payload.mappings,
    required_fields: payload.requiredFields ?? [],
    transformation_hints: payload.transformationHints ?? {},
    is_default: payload.isDefault ?? false,
    is_active: payload.isActive ?? true,
  });
  return mappingTemplateApiToViewModel(response);
}

export async function applyMappingTemplate(templateId: string, fileId: string): Promise<UploadFileDetail> {
  const response = await api.post<any>(`/mapping/templates/${templateId}/apply`, {
    file_id: fileId,
  });
  return uploadFileDetailApiToViewModel(response);
}

export async function getSkuAliases(): Promise<AliasEntry[]> {
  const response = await api.get<any[]>("/mapping/aliases/skus");
  return response.map(aliasEntryApiToViewModel);
}

export async function getClientAliases(): Promise<AliasEntry[]> {
  const response = await api.get<any[]>("/mapping/aliases/clients");
  return response.map(aliasEntryApiToViewModel);
}
