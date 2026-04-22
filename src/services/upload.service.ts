import type { UploadJob, MappingField } from "@/types";
import { UPLOAD_JOBS, MAPPING_FIELDS } from "@/mocks/data/seed";
import { latency } from "./_latency";

export async function getUploadJobs(): Promise<UploadJob[]> {
  await latency(180);
  return UPLOAD_JOBS;
}

export async function getMappingFields(): Promise<MappingField[]> {
  await latency(180);
  return MAPPING_FIELDS;
}
