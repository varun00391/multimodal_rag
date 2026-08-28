import type {
  ApiErrorBody,
  CanonicalDocument,
  ExtractionReport,
  JobCreateResponse,
  JobListItem,
  JobStatusResponse,
  UiConfig,
} from "./types";

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function parseError(response: Response): Promise<never> {
  let body: { error?: ApiErrorBody } | null = null;
  try {
    body = (await response.json()) as { error?: ApiErrorBody };
  } catch {
    body = null;
  }
  const error = body?.error;
  throw new ApiError(
    error?.code ?? "HTTP_ERROR",
    error?.message ?? response.statusText,
    response.status,
    error?.details ?? {},
  );
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    await parseError(response);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<{ status: string }> {
  return getJson("/api/v1/health");
}

export function getUiConfig(): Promise<UiConfig> {
  return getJson("/api/v1/ui-config");
}

export function listJobs(limit = 50): Promise<JobListItem[]> {
  return getJson(`/api/v1/extractions?limit=${limit}`);
}

export function getJob(jobId: string): Promise<JobStatusResponse> {
  return getJson(`/api/v1/extractions/${jobId}`);
}

export function getDocument(jobId: string): Promise<CanonicalDocument> {
  return getJson(`/api/v1/extractions/${jobId}/document`);
}

export function getReport(jobId: string): Promise<ExtractionReport> {
  return getJson(`/api/v1/extractions/${jobId}/report`);
}

export function sourceUrl(jobId: string): string {
  return `/api/v1/extractions/${jobId}/source`;
}

export function assetUrl(jobId: string, asset: string): string {
  const path = asset.replace(/^\//, "");
  return `/api/v1/extractions/${jobId}/assets/${path}`;
}

export async function createExtraction(form: FormData): Promise<JobCreateResponse> {
  const response = await fetch("/api/v1/extractions", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    await parseError(response);
  }
  return (await response.json()) as JobCreateResponse;
}

export async function fetchSourceBlob(jobId: string): Promise<Blob> {
  const response = await fetch(sourceUrl(jobId));
  if (!response.ok) {
    await parseError(response);
  }
  return response.blob();
}
