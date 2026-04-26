import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  applyMappingTemplate,
  applyUpload,
  confirmUploadSourceType,
  createMappingTemplate,
  createUploadJob,
  getMappingTemplates,
  getUploadFileDetail,
  getUploadIssues,
  getUploadJobs,
  saveUploadMapping,
  suggestMappingForUpload,
  validateUpload,
} from "@/services/upload.service";

export function useUploadJobsQuery(filters: {
  status?: string;
  sourceType?: string;
  page?: number;
  pageSize?: number;
}) {
  return useQuery({
    queryKey: queryKeys.uploads.files(filters),
    queryFn: () =>
      getUploadJobs({
        status: filters.status as any,
        sourceType: filters.sourceType as any,
        page: filters.page,
        pageSize: filters.pageSize,
      }),
  });
}

export function useUploadFileDetailQuery(fileId: string | null) {
  return useQuery({
    queryKey: queryKeys.uploads.file(fileId),
    queryFn: () => getUploadFileDetail(fileId as string),
    enabled: Boolean(fileId),
  });
}

export function useUploadIssuesQuery(fileId: string | null, filters: { severity?: string } = {}) {
  return useQuery({
    queryKey: queryKeys.uploads.issues(fileId, filters),
    queryFn: () => getUploadIssues(fileId as string, filters),
    enabled: Boolean(fileId),
  });
}

export function useMappingTemplatesQuery(sourceType?: string) {
  return useQuery({
    queryKey: queryKeys.uploads.mappingTemplates(sourceType),
    queryFn: () => getMappingTemplates(sourceType as any),
    enabled: Boolean(sourceType),
  });
}

function invalidateUploadQueries(queryClient: ReturnType<typeof useQueryClient>, fileId?: string | null) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.quality.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  if (fileId) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.uploads.file(fileId) });
  }
}

export function useCreateUploadMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, sourceType }: { file: File; sourceType?: string }) =>
      createUploadJob(file, sourceType as any),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}

export function useConfirmUploadSourceTypeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      fileId,
      sourceType,
      newEntityName,
    }: {
      fileId: string;
      sourceType: string;
      newEntityName?: string;
    }) => confirmUploadSourceType(fileId, { sourceType: sourceType as any, newEntityName }),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}

export function useSuggestMappingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fileId, templateId }: { fileId: string; templateId?: string }) =>
      suggestMappingForUpload(fileId, templateId),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}

export function useSaveUploadMappingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      fileId,
      mappings,
      templateId,
    }: {
      fileId: string;
      mappings: Record<string, string>;
      templateId?: string;
    }) => saveUploadMapping(fileId, mappings, templateId),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}

export function useValidateUploadMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => validateUpload(fileId),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}

export function useApplyUploadMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => applyUpload(fileId),
    onSuccess: (_response, fileId) => invalidateUploadQueries(queryClient, fileId),
  });
}

export function useCreateMappingTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMappingTemplate,
    onSuccess: (template) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.uploads.mappingTemplates(template.sourceType),
      });
    },
  });
}

export function useApplyMappingTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, fileId }: { templateId: string; fileId: string }) =>
      applyMappingTemplate(templateId, fileId),
    onSuccess: (detail) => invalidateUploadQueries(queryClient, detail.file.id),
  });
}
