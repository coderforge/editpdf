import { useEffect, useRef, useState } from "react";
import type { DocumentState } from "./hooks";
import { previewOf, PreviewError } from "./preview";

/** The state of each of several files, read in the browser as they arrive. */
export function useDocuments(files: readonly File[]): ReadonlyMap<File, DocumentState> {
  const [states, setStates] = useState<ReadonlyMap<File, DocumentState>>(new Map());
  const started = useRef(new Set<File>());

  useEffect(() => {
    const current = new Set(files);
    for (const file of started.current) {
      if (!current.has(file)) {
        started.current.delete(file);
      }
    }
    setStates((previous) => {
      const next = new Map([...previous].filter(([file]) => current.has(file)));
      return next.size === previous.size ? previous : next;
    });

    for (const file of files) {
      if (started.current.has(file)) {
        continue;
      }
      started.current.add(file);
      // Dropped while it was being read: its answer is no longer wanted.
      const settle = (state: DocumentState) =>
        setStates((previous) => (started.current.has(file) ? new Map(previous).set(file, state) : previous));
      previewOf(file)
        .pageCount()
        .then(
          (pageCount) => settle({ status: "ready", pageCount }),
          (error: unknown) => settle({ status: "failed", reason: error instanceof PreviewError ? error.reason : "unreadable" }),
        );
    }
  }, [files]);

  return states;
}
