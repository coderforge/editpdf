import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { format, useI18n } from "../i18n";
import { UploadIcon } from "./icons";

export const PDF_ACCEPT = "application/pdf,.pdf";

/** Whether a file looks like a PDF by its type or its name; the content is checked later. */
export function isPdfFile(file: File): boolean {
  return file.type === "application/pdf" || /\.pdf$/i.test(file.name);
}

function hasFiles(event: DragEvent | globalThis.DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

interface DropzoneProps {
  readonly multiple: boolean;
  readonly onFiles: (files: File[]) => void;
  /** The line under the title: what is accepted. */
  readonly hint: string;
  /** A small tile (to add more files) instead of the full panel. */
  readonly compact?: boolean;
}

/** A place to drop files, or to click to choose them. */
export function Dropzone({ multiple, onFiles, hint, compact = false }: DropzoneProps) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const hintId = useId();

  const drop = (event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setOver(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      onFiles(multiple ? files : files.slice(0, 1));
    }
  };

  return (
    <div
      className={`dropzone${compact ? " dropzone--compact" : ""}${over ? " dropzone--over" : ""}`}
      onDragEnter={(event) => hasFiles(event) && setOver(true)}
      onDragOver={(event) => {
        if (hasFiles(event)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "copy";
        }
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOver(false);
        }
      }}
      onDrop={drop}
    >
      <UploadIcon className="dropzone__icon" width={compact ? 22 : 40} height={compact ? 22 : 40} />
      {compact ? null : (
        <>
          <p className="dropzone__title">{multiple ? t.drop.titleMany : t.drop.titleOne}</p>
          <p className="dropzone__or">{t.drop.or}</p>
        </>
      )}
      <button type="button" className={compact ? "button button--ghost" : "button button--primary"} onClick={() => input.current?.click()} aria-describedby={hintId}>
        {compact ? t.drop.addMore : multiple ? t.drop.chooseMany : t.drop.chooseOne}
      </button>
      <p className="dropzone__hint" id={hintId}>
        {hint}
      </p>
      <input
        ref={input}
        type="file"
        accept={PDF_ACCEPT}
        multiple={multiple}
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) {
            onFiles(files);
          }
        }}
      />
    </div>
  );
}

/**
 * Files dropped anywhere on the page go to `onFiles`, and the browser does not
 * open them in place of the page (its default for a file dropped outside a
 * drop target). Returns whether files are being dragged over the window.
 */
export function useWindowDrop(onFiles: (files: File[]) => void): boolean {
  const [dragging, setDragging] = useState(false);
  const handler = useRef(onFiles);
  handler.current = onFiles;

  useEffect(() => {
    let depth = 0;
    const enter = (event: globalThis.DragEvent) => {
      if (hasFiles(event)) {
        depth += 1;
        setDragging(true);
      }
    };
    const leave = (event: globalThis.DragEvent) => {
      if (hasFiles(event)) {
        depth = Math.max(0, depth - 1);
        if (depth === 0) {
          setDragging(false);
        }
      }
    };
    const over = (event: globalThis.DragEvent) => {
      if (hasFiles(event)) {
        event.preventDefault();
      }
    };
    // In the capture phase, so the overlay goes away even when a dropzone
    // handles the drop itself and stops it there.
    const end = () => {
      depth = 0;
      setDragging(false);
    };
    const drop = (event: globalThis.DragEvent) => {
      if (!hasFiles(event)) {
        return;
      }
      event.preventDefault();
      const files = Array.from(event.dataTransfer?.files ?? []);
      if (files.length > 0) {
        handler.current(files);
      }
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", end, true);
    window.addEventListener("dragend", end, true);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", end, true);
      window.removeEventListener("dragend", end, true);
      window.removeEventListener("drop", drop);
    };
  }, []);

  return dragging;
}

export function DropOverlay({ visible }: { readonly visible: boolean }) {
  const { t } = useI18n();
  if (!visible) {
    return null;
  }
  return (
    <div className="drop-overlay" aria-hidden="true">
      <div className="drop-overlay__panel">
        <UploadIcon width={48} height={48} />
        <span>{t.drop.overlay}</span>
      </div>
    </div>
  );
}

/** The hint under a dropzone, from the service's limits. */
export function useDropHint(multiple: boolean, maxFiles: number, maxBytes: number): string {
  const { t, formatBytes } = useI18n();
  return multiple
    ? format(t.drop.hintMany, { maxFiles, size: formatBytes(maxBytes) })
    : format(t.drop.hintOne, { size: formatBytes(maxBytes) });
}
