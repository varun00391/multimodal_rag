import type { JobStatus } from "../api/types";
import { TERMINAL_STATUSES } from "../api/types";

export const HARD_FAILURE_CODES = new Set([
  "NATIVE_TEXT_CORRUPT",
  "NATIVE_TEXT_MISSING",
  "READING_ORDER_INVALID",
  "BBOX_OUT_OF_BOUNDS",
  "BBOX_NON_POSITIVE_AREA",
  "TABLE_STRUCTURE_INVALID",
  "TABLE_EMPTY",
  "VISUAL_CROP_MISSING",
]);

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function isRunning(status: JobStatus): boolean {
  return !isTerminal(status);
}

export function stageLabel(status: JobStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "validating_input":
      return "Validating PDF";
    case "inspecting":
      return "Inspecting pages";
    case "planning":
      return "Planning routes";
    case "extracting":
      return "Extracting";
    case "validating_output":
      return "Validating output";
    case "retrying":
      return "Retrying failed work";
    case "merging":
      return "Merging results";
    case "completed":
      return "Completed";
    case "completed_with_warnings":
      return "Completed with warnings";
    case "failed":
      return "Failed";
  }
}

export function listBadgeLabel(status: JobStatus): string {
  if (status === "completed") return "Done";
  if (status === "completed_with_warnings") return "Done · warnings";
  if (status === "failed") return "Failed";
  return stageLabel(status);
}

export function badgeClass(status: JobStatus): string {
  if (status === "completed") return "badge badge-completed";
  if (status === "completed_with_warnings") return "badge badge-warn";
  if (status === "failed") return "badge badge-failed";
  if (status === "queued") return "badge badge-queued";
  return "badge badge-running";
}
