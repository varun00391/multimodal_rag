import type { BoundingBox } from "../api/types";

export function bboxToCss(
  bbox: BoundingBox,
  pageWidth: number,
  pageHeight: number,
  cssWidth: number,
  cssHeight: number,
): { left: number; top: number; width: number; height: number } {
  const scaleX = cssWidth / pageWidth;
  const scaleY = cssHeight / pageHeight;
  return {
    left: bbox.left * scaleX,
    top: bbox.top * scaleY,
    width: Math.max(0, bbox.right - bbox.left) * scaleX,
    height: Math.max(0, bbox.bottom - bbox.top) * scaleY,
  };
}
