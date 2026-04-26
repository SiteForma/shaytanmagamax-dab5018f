export interface ApiErrorEnvelope {
  code: string;
  message: string;
  request_id?: string;
  details?: Record<string, unknown>;
}
