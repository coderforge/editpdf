import { useEffect, useRef, useState, type RefObject } from "react";
import { previewOf, PreviewError, type PreviewFailure } from "./preview";

export type DocumentState =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly pageCount: number }
  | { readonly status: "failed"; readonly reason: PreviewFailure };

/** The page count of a file, read in the browser. */
export function useDocument(file: File | null): DocumentState {
  const [state, setState] = useState<DocumentState>({ status: "loading" });
  useEffect(() => {
    if (file === null) {
      return;
    }
    let live = true;
    setState({ status: "loading" });
    previewOf(file)
      .pageCount()
      .then(
        (pageCount) => live && setState({ status: "ready", pageCount }),
        (error: unknown) =>
          live && setState({ status: "failed", reason: error instanceof PreviewError ? error.reason : "unreadable" }),
      );
    return () => {
      live = false;
    };
  }, [file]);
  return state;
}

/** Whether an element has come near the viewport (once it has, it stays true). */
export function useNearViewport<T extends Element>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (element === null || near) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setNear(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);
  return [ref, near];
}

export type ThumbnailState =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly url: string }
  | { readonly status: "failed" };

/** A thumbnail of page `number`, rendered once `enabled`. */
export function useThumbnail(file: File, number: number, enabled: boolean): ThumbnailState {
  const [state, setState] = useState<ThumbnailState>({ status: "loading" });
  useEffect(() => {
    if (!enabled) {
      return;
    }
    let live = true;
    previewOf(file)
      .thumbnail(number)
      .then(
        (url) => live && setState({ status: "ready", url }),
        (error: unknown) => {
          console.warn("editpdf: no preview of page", number, error);
          if (live) {
            setState({ status: "failed" });
          }
        },
      );
    return () => {
      live = false;
    };
  }, [file, number, enabled]);
  return state;
}
