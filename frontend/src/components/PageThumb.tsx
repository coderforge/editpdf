import type { ReactNode } from "react";
import { useNearViewport, useThumbnail } from "../pdf/hooks";
import { useI18n } from "../i18n";
import { FileIcon } from "./icons";

interface PageThumbProps {
  readonly file: File;
  readonly number: number;
  /** Extra clockwise turn to preview, in degrees. */
  readonly rotation?: number;
  readonly label: string;
  readonly children?: ReactNode;
}

/** A page, rendered once it scrolls near the viewport. */
export function PageThumb({ file, number, rotation = 0, label, children }: PageThumbProps) {
  const { t } = useI18n();
  const [ref, near] = useNearViewport<HTMLDivElement>();
  const thumbnail = useThumbnail(file, number, near);

  return (
    <figure className="thumb">
      <div ref={ref} className="thumb__frame">
        {thumbnail.status === "ready" ? (
          <img
            className="thumb__image"
            src={thumbnail.url}
            alt={label}
            style={{ transform: `rotate(${rotation}deg)` }}
            draggable={false}
          />
        ) : thumbnail.status === "failed" ? (
          <span className="thumb__placeholder">
            <FileIcon width={32} height={32} />
            <span>{t.file.noPreview}</span>
          </span>
        ) : (
          <span className="thumb__placeholder thumb__placeholder--loading" aria-label={t.file.loadingPreview} />
        )}
        {children}
      </div>
      <figcaption className="thumb__caption">{number}</figcaption>
    </figure>
  );
}
