import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export type PdfDocument = pdfjs.PDFDocumentProxy;

export async function loadPdfDocument(data: ArrayBuffer): Promise<PdfDocument> {
  return pdfjs.getDocument({ data: new Uint8Array(data) }).promise;
}

export async function renderPage(
  pdf: PdfDocument,
  pageNumber: number,
  canvas: HTMLCanvasElement,
  cssWidth: number,
): Promise<{ cssWidth: number; cssHeight: number }> {
  const page = await pdf.getPage(pageNumber);
  const unscaled = page.getViewport({ scale: 1 });
  const scale = cssWidth / unscaled.width;
  const viewport = page.getViewport({ scale });
  const outputScale = window.devicePixelRatio || 1;
  canvas.width = Math.floor(viewport.width * outputScale);
  canvas.height = Math.floor(viewport.height * outputScale);
  canvas.style.width = `${Math.floor(viewport.width)}px`;
  canvas.style.height = `${Math.floor(viewport.height)}px`;
  const context = canvas.getContext("2d");
  if (!context) {
    return { cssWidth: viewport.width, cssHeight: viewport.height };
  }
  await page.render({
    canvasContext: context,
    viewport,
    transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
  }).promise;
  return { cssWidth: viewport.width, cssHeight: viewport.height };
}
