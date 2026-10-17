/**
 * Previews of the documents dropped, rendered in the browser with pdf.js: the
 * page count and page thumbnails, before anything is uploaded. pdf.js is big,
 * so it is loaded the first time a document is dropped, not with the page.
 */
import type { PDFDocumentProxy } from "pdfjs-dist";

type PdfJs = typeof import("pdfjs-dist");

let pdfjs: Promise<PdfJs> | undefined;

// The legacy build: the modern one relies on JavaScript features only the
// newest browsers have (Map.prototype.getOrInsertComputed, for one), and fails
// on the rest; the legacy one carries polyfills for them.
function loadPdfJs(): Promise<PdfJs> {
  pdfjs ??= Promise.all([
    import("pdfjs-dist/legacy/build/pdf.mjs"),
    import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url"),
  ]).then(
    ([library, worker]) => {
      library.GlobalWorkerOptions.workerSrc = worker.default;
      return library;
    },
  );
  return pdfjs;
}

export type PreviewFailure = "encrypted" | "unreadable";

export class PreviewError extends Error {
  override readonly name = "PreviewError";
  readonly reason: PreviewFailure;

  constructor(reason: PreviewFailure) {
    super(reason);
    this.reason = reason;
  }
}

// Rendering is CPU work on the main thread's canvas: a few at a time keeps
// the page responsive while a 300-page document scrolls by.
const MAX_RENDERING = 2;
let rendering = 0;
const waiting: (() => void)[] = [];

async function slot<T>(work: () => Promise<T>): Promise<T> {
  if (rendering >= MAX_RENDERING) {
    await new Promise<void>((resolve) => waiting.push(resolve));
  }
  rendering += 1;
  try {
    return await work();
  } finally {
    rendering -= 1;
    waiting.shift()?.();
  }
}

/** Thumbnails are this many CSS pixels on their longest side. */
export const THUMBNAIL_SIZE = 180;

export class Preview {
  readonly #file: File;
  readonly #thumbnails = new Map<number, Promise<string>>();
  #document: Promise<PDFDocumentProxy> | undefined;
  #destroyed = false;

  constructor(file: File) {
    this.#file = file;
  }

  #open(): Promise<PDFDocumentProxy> {
    this.#document ??= (async () => {
      const library = await loadPdfJs();
      const data = new Uint8Array(await this.#file.arrayBuffer());
      try {
        return await library.getDocument({ data, wasmUrl: "/pdfjs/wasm/", useSystemFonts: true }).promise;
      } catch (error) {
        const name = error instanceof Error ? error.name : "";
        throw new PreviewError(name === "PasswordException" ? "encrypted" : "unreadable");
      }
    })();
    return this.#document;
  }

  /** The number of pages; rejects with a PreviewError. */
  async pageCount(): Promise<number> {
    return (await this.#open()).numPages;
  }

  /** An object URL of a PNG of page `number` (1-based), as the page is displayed. */
  thumbnail(number: number): Promise<string> {
    let thumbnail = this.#thumbnails.get(number);
    if (thumbnail === undefined) {
      thumbnail = slot(async () => {
        const document = await this.#open();
        const page = await document.getPage(number);
        const base = page.getViewport({ scale: 1 });
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        const scale = (THUMBNAIL_SIZE * ratio) / Math.max(base.width, base.height);
        const viewport = page.getViewport({ scale });
        const canvas = window.document.createElement("canvas");
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        await page.render({ canvas, viewport }).promise;
        page.cleanup();
        const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
        if (blob === null) {
          throw new PreviewError("unreadable");
        }
        if (this.#destroyed) {
          throw new PreviewError("unreadable");
        }
        return URL.createObjectURL(blob);
      });
      // A failed render may succeed later (a scroll back): do not keep failures.
      thumbnail.catch(() => this.#thumbnails.delete(number));
      this.#thumbnails.set(number, thumbnail);
    }
    return thumbnail;
  }

  /** Frees the document and its thumbnails. */
  destroy(): void {
    this.#destroyed = true;
    for (const thumbnail of this.#thumbnails.values()) {
      thumbnail.then(URL.revokeObjectURL, () => undefined);
    }
    this.#thumbnails.clear();
    this.#document?.then((document) => document.loadingTask.destroy(), () => undefined);
  }
}

const previews = new WeakMap<File, Preview>();

/** The one preview of a file. */
export function previewOf(file: File): Preview {
  let preview = previews.get(file);
  if (preview === undefined) {
    preview = new Preview(file);
    previews.set(file, preview);
  }
  return preview;
}

/** Done with a file: free what its preview holds. */
export function releasePreview(file: File): void {
  previews.get(file)?.destroy();
  previews.delete(file);
}
