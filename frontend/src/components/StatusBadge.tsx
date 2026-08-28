import type { JobStatus } from "../api/types";
import { badgeClass, listBadgeLabel, stageLabel } from "../lib/status";

export function StatusBadge({ status, compact = false }: { status: JobStatus; compact?: boolean }) {
  return <span className={badgeClass(status)}>{compact ? listBadgeLabel(status) : stageLabel(status)}</span>;
}
