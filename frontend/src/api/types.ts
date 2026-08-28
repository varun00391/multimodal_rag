export type JobStatus =
  | "queued"
  | "validating_input"
  | "inspecting"
  | "planning"
  | "extracting"
  | "validating_output"
  | "retrying"
  | "merging"
  | "completed"
  | "completed_with_warnings"
  | "failed";

export type ElementType =
  | "heading"
  | "paragraph"
  | "list"
  | "table"
  | "picture"
  | "chart"
  | "diagram"
  | "formula"
  | "code"
  | "key_value"
  | "form_field"
  | "header"
  | "footer"
  | "footnote"
  | "page_number"
  | "unknown";

export interface BoundingBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  coordinate_origin: string;
  unit: string;
}

export interface ExtractorProvenance {
  name: string;
  version?: string | null;
  adapter_version?: string | null;
  profile?: string | null;
  model?: string | null;
  prompt_version?: number | null;
}

export interface ElementProvenance {
  source_page: number;
  source_coordinate_system?: string;
  routing_policy_version?: string | null;
  attempt?: number;
}

export interface CanonicalElement {
  element_id: string;
  type: ElementType;
  page: number;
  reading_order: number;
  text?: string | null;
  markdown?: string | null;
  html?: string | null;
  bbox?: BoundingBox | null;
  asset?: string | null;
  confidence?: number | null;
  extractor?: ExtractorProvenance | null;
  provenance?: ElementProvenance | null;
  metadata?: Record<string, unknown>;
}

export interface ExtractionError {
  code: string;
  message: string;
  page?: number | null;
  details?: Record<string, unknown>;
}

export interface ExtractionAttempt {
  attempt: number;
  extractor: string;
  profile?: string | null;
  status: string;
  duration_ms?: number | null;
  element_count?: number;
  warnings?: string[];
  errors?: ExtractionError[];
}

export interface CanonicalPage {
  page: number;
  width: number;
  height: number;
  rotation?: number;
  primary_route?: string | null;
  routing_confidence?: number | null;
  validation_confidence?: number | null;
  overall_confidence?: number | null;
  routing_reasons?: string[];
  extraction_routes?: string[];
  elements: CanonicalElement[];
  attempts?: ExtractionAttempt[];
  warnings?: string[];
  errors?: ExtractionError[];
}

export interface DocumentSummary {
  element_counts?: Record<string, number>;
  route_counts?: Record<string, number>;
  failed_pages?: number[];
  scanned_pages?: number[];
  duration_ms?: number;
  estimated_cost_usd?: number;
}

export interface CanonicalDocument {
  schema_version: string;
  document_id: string;
  source: {
    filename?: string | null;
    media_type?: string;
    sha256: string;
    size_bytes: number;
  };
  status: string;
  page_count: number;
  pages: CanonicalPage[];
  summary: DocumentSummary;
}

export interface ExtractionPolicy {
  allow_managed_apis: boolean;
  visual_understanding: boolean;
  page_start?: number | null;
  page_end?: number | null;
  force_extractor?: string | null;
  compare_extractors?: boolean;
}

export interface JobStatusResponse {
  job_id: string;
  document_id: string;
  status: JobStatus;
  original_filename?: string | null;
  page_count: number;
  sha256: string;
  policy: ExtractionPolicy;
  error_code?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
  cache_hit: boolean;
  created_at: string;
  updated_at: string;
}

export interface JobListItem {
  job_id: string;
  original_filename?: string | null;
  status: JobStatus;
  page_count: number;
  duration_ms?: number | null;
  cache_hit: boolean;
  created_at: string;
  force_extractor?: string | null;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
}

export interface UiConfig {
  max_file_bytes: number;
  max_pages: number;
  benchmark_enabled: boolean;
  allow_managed_apis_default: boolean;
}

export interface ValidationFailure {
  code: string;
  message: string;
  element_id?: string | null;
  details?: Record<string, unknown>;
}

export interface ValidationResult {
  page: number;
  confidence: number;
  passed: boolean;
  failures: ValidationFailure[];
}

export interface FallbackRecord {
  page: number;
  reason_code: string;
  from_extractor?: string | null;
  to_extractor?: string | null;
  to_profile?: string | null;
  status?: string | null;
  message?: string | null;
}

export interface ReportPage {
  page: number;
  primary_route?: string | null;
  routing_reasons?: string[];
  routing_confidence?: number | null;
  extraction_routes?: string[];
  element_count?: number;
  attempt_count?: number;
  validation_passed?: boolean | null;
  validation_confidence?: number | null;
  task_kinds?: string[];
  overall_confidence?: number | null;
  status?: string;
}

export interface ExtractionReport {
  job_id: string;
  schema_version?: string;
  status: string;
  inspection_summary?: {
    page_count?: number;
    scanned_pages?: number[];
    pymupdf_fast_path_pages?: number[];
  };
  route_counts?: Record<string, number>;
  element_counts?: Record<string, number>;
  duration_ms?: number;
  durations?: Record<string, number>;
  extractors?: string[];
  profiles?: string[];
  force_extractor?: string | null;
  allow_managed_apis?: boolean;
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: number;
  };
  cache?: {
    enabled?: boolean;
    hit?: boolean;
    group_hits?: number;
    group_misses?: number;
  };
  circuit_breakers?: Record<string, { state?: string; consecutive_failures?: number }>;
  routing?: {
    plans?: unknown[];
    groups?: Array<{
      group_id?: string;
      extractor?: string;
      profile?: string | null;
      kind?: string;
      pages?: number[];
    }>;
  };
  fallbacks?: FallbackRecord[];
  pages?: ReportPage[];
  validation?: {
    min_confidence?: number;
    page_count?: number;
    failed_pages?: number[];
    pages?: ValidationResult[];
  };
  versions?: Record<string, string>;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export const FORCE_EXTRACTORS = [
  "",
  "pymupdf",
  "docling",
  "docling:digital-layout",
  "docling:digital-table",
  "docling:formula-code",
  "docling:private-ocr",
  "gemini",
  "groq-vision",
] as const;

export const TERMINAL_STATUSES: JobStatus[] = [
  "completed",
  "completed_with_warnings",
  "failed",
];
