import { PDFDocument } from "pdf-lib";

/**
 * Count pages in a PDF file without rendering it.
 * Returns null on failure (graceful degradation — let backend catch it).
 */
export async function getPdfPageCount(file: File): Promise<number | null> {
  try {
    const buffer = await file.arrayBuffer();
    const pdf = await PDFDocument.load(buffer, { ignoreEncryption: true });
    return pdf.getPageCount();
  } catch {
    return null;
  }
}
