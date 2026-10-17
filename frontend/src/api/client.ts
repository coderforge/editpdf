import type { components } from "./schema.gen";

export type ServiceInfo = components["schemas"]["ServiceInfo"];
export type Limits = components["schemas"]["Limits"];
export type Problem = components["schemas"]["Problem"];
export type ProblemCode = components["schemas"]["ProblemCode"];
export type SplitMode = components["schemas"]["SplitMode"];
export type Rotation = components["schemas"]["Rotation"];

/** What the interface assumes until /api/v1/info answers; the service's defaults. */
export const DEFAULT_LIMITS: Limits = { maxUploadBytes: 25 * 1024 * 1024, maxFiles: 20, maxPages: 2000 };

const API = "/api/v1";

/** A failed call: the service's problem document, or a network failure (code "network"). */
export class ApiProblem extends Error {
  override readonly name = "ApiProblem";
  readonly code: ProblemCode | "network";
  readonly detail: string | undefined;
  readonly requestId: string | undefined;

  constructor(code: ProblemCode | "network", detail?: string, requestId?: string) {
    super(detail ?? code);
    this.code = code;
    this.detail = detail;
    this.requestId = requestId;
  }
}

export async function getServiceInfo(signal?: AbortSignal): Promise<ServiceInfo> {
  const response = await fetch(`${API}/info`, signal === undefined ? {} : { signal });
  if (!response.ok) {
    throw new ApiProblem("internal_error", `GET ${API}/info answered ${response.status}`);
  }
  return (await response.json()) as ServiceInfo;
}

/** The name in a Content-Disposition header: filename* (RFC 5987) first, then filename. */
export function filenameFrom(header: string | null, fallback: string): string {
  if (header === null) {
    return fallback;
  }
  const extended = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)?.[1];
  if (extended !== undefined) {
    try {
      return decodeURIComponent(extended.trim());
    } catch {
      // fall through to the plain name
    }
  }
  return /filename\s*=\s*"([^"]*)"/i.exec(header)?.[1] ?? fallback;
}

export interface Download {
  readonly blob: Blob;
  readonly filename: string;
  /** X-Page-Count or X-Part-Count, when the service sent one. */
  readonly count: number | undefined;
}

export type Progress = { readonly phase: "uploading"; readonly percent: number } | { readonly phase: "processing" };

export type Operation = "merge" | "split" | "rotate";

const FALLBACK_NAMES: Readonly<Record<Operation, string>> = {
  merge: "merged.pdf",
  split: "split.zip",
  rotate: "rotated.pdf",
};

async function problemFrom(blob: Blob, status: number, requestId: string | undefined): Promise<ApiProblem> {
  try {
    const problem = JSON.parse(await blob.text()) as Partial<Problem>;
    if (typeof problem.code === "string") {
      return new ApiProblem(problem.code, problem.detail, problem.requestId ?? requestId);
    }
  } catch {
    // Not a problem document: a proxy's error page, say.
  }
  return new ApiProblem(status >= 500 ? "internal_error" : "invalid_request", `HTTP ${status}`, requestId);
}

/**
 * Sends a form to an operation and resolves with the file it answers.
 * XMLHttpRequest rather than fetch, for the upload progress.
 */
export function submit(
  operation: Operation,
  form: FormData,
  onProgress: (progress: Progress) => void,
  signal?: AbortSignal,
): Promise<Download> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API}/pdf/${operation}`);
    request.responseType = "blob";
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent >= 100 ? { phase: "processing" } : { phase: "uploading", percent });
      }
    });
    request.upload.addEventListener("load", () => onProgress({ phase: "processing" }));
    request.addEventListener("load", () => {
      const blob = request.response as Blob;
      const requestId = request.getResponseHeader("x-request-id") ?? undefined;
      if (request.status !== 200) {
        void problemFrom(blob, request.status, requestId).then(reject);
        return;
      }
      const count = request.getResponseHeader("x-page-count") ?? request.getResponseHeader("x-part-count");
      resolve({
        blob,
        filename: filenameFrom(request.getResponseHeader("content-disposition"), FALLBACK_NAMES[operation]),
        count: count === null ? undefined : Number(count),
      });
    });
    request.addEventListener("error", () => reject(new ApiProblem("network")));
    request.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    signal?.addEventListener("abort", () => request.abort(), { once: true });
    onProgress({ phase: "uploading", percent: 0 });
    request.send(form);
  });
}

/** Hands a file to the browser to save. */
export function saveFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  // Long enough for the download to start everywhere.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
