import { useCallback, useEffect, useRef, useState } from "react";
import { ApiProblem, saveFile, submit, type Download, type Operation, type Progress } from "../api/client";

export type OperationState =
  | { readonly status: "idle" }
  | { readonly status: "running"; readonly progress: Progress }
  | { readonly status: "done"; readonly download: Download }
  | { readonly status: "failed"; readonly problem: ApiProblem };

/** Runs an operation, tracks its progress, and saves what it answers. */
export function useOperation() {
  const [state, setState] = useState<OperationState>({ status: "idle" });
  const controller = useRef<AbortController | null>(null);

  // Leaving the page cancels an upload in flight.
  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(async (operation: Operation, form: FormData) => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setState({ status: "running", progress: { phase: "uploading", percent: 0 } });
    try {
      const download = await submit(operation, form, (progress) => setState({ status: "running", progress }), current.signal);
      saveFile(download.blob, download.filename);
      setState({ status: "done", download });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      setState({ status: "failed", problem: error instanceof ApiProblem ? error : new ApiProblem("internal_error", String(error)) });
    }
  }, []);

  const reset = useCallback(() => {
    controller.current?.abort();
    setState({ status: "idle" });
  }, []);

  return { state, run, reset };
}
