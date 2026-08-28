import type { ElementType } from "../api/types";

export const ELEMENT_COLORS: Record<ElementType, string> = {
  heading: "var(--el-heading)",
  paragraph: "var(--el-paragraph)",
  list: "var(--el-list)",
  table: "var(--el-table)",
  picture: "var(--el-picture)",
  chart: "var(--el-chart)",
  diagram: "var(--el-diagram)",
  formula: "var(--el-formula)",
  code: "var(--el-code)",
  key_value: "var(--el-key-value)",
  form_field: "var(--el-form-field)",
  header: "var(--el-header)",
  footer: "var(--el-footer)",
  footnote: "var(--el-footnote)",
  page_number: "var(--el-page-number)",
  unknown: "var(--el-unknown)",
};

export function extractorColor(name: string | null | undefined): string {
  if (!name) return "var(--ex-mixed)";
  if (name.startsWith("docling")) return "var(--ex-docling)";
  if (name === "pymupdf") return "var(--ex-pymupdf)";
  if (name === "gemini") return "var(--ex-gemini)";
  if (name === "groq-vision") return "var(--ex-groq)";
  return "var(--ex-mixed)";
}

export function typeFill(type: ElementType, selected: boolean): string {
  const color = ELEMENT_COLORS[type];
  return `color-mix(in srgb, ${color} ${selected ? 28 : 14}%, transparent)`;
}
