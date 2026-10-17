import type { ReactNode } from "react";
import { format, useI18n } from "../i18n";
import type { DocumentState } from "../pdf/hooks";
import { AlertIcon, CloseIcon, FileIcon, LockIcon } from "../components/icons";

export function ToolHeader({ title, description }: { readonly title: string; readonly description: string }) {
  return (
    <header className="tool-header">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

/** Notices about files that were not taken (not PDFs, too many...). */
export function Notices({ messages, onDismiss }: { readonly messages: readonly string[]; readonly onDismiss: () => void }) {
  const { t } = useI18n();
  if (messages.length === 0) {
    return null;
  }
  return (
    <div className="notice notice--warning" role="alert">
      <AlertIcon />
      <ul>
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
      <button type="button" className="icon-button" onClick={onDismiss} aria-label={t.progress.startOver}>
        <CloseIcon width={16} height={16} />
      </button>
    </div>
  );
}

/** What is known of a document so far: its pages, or why it cannot be used. */
export function DocumentStatus({ state }: { readonly state: DocumentState | undefined }) {
  const { t } = useI18n();
  if (state === undefined || state.status === "loading") {
    return <span className="muted">{t.file.loadingPreview}</span>;
  }
  if (state.status === "ready") {
    return <span>{t.file.pages(state.pageCount)}</span>;
  }
  return (
    <span className="file-problem">
      {state.reason === "encrypted" ? <LockIcon width={14} height={14} /> : <AlertIcon width={14} height={14} />}
      {state.reason === "encrypted" ? t.file.passwordProtected : t.file.unreadable}
    </span>
  );
}

/** The one document a split or a rotation works on. */
export function FileHeader({
  file,
  state,
  onReplace,
  children,
}: {
  readonly file: File;
  readonly state: DocumentState;
  readonly onReplace: () => void;
  readonly children?: ReactNode;
}) {
  const { t, formatBytes } = useI18n();
  return (
    <div className="file-header">
      <FileIcon className="file-header__icon" />
      <div className="file-header__text">
        <strong className="file-header__name" title={file.name}>
          {file.name}
        </strong>
        <span className="file-header__meta">
          <DocumentStatus state={state} /> · {formatBytes(file.size)}
        </span>
      </div>
      {children}
      <button type="button" className="button button--ghost" onClick={onReplace}>
        {t.file.replace}
      </button>
    </div>
  );
}

/** Why a set of files cannot be sent, judged in the browser; null when they can. */
export function sizeBlocker(totalBytes: number, maxBytes: number, t: ReturnType<typeof useI18n>): string | null {
  // Leave room for the multipart envelope around the files.
  return totalBytes + 64 * 1024 > maxBytes
    ? format(t.t.file.tooLarge, { size: t.formatBytes(totalBytes), max: t.formatBytes(maxBytes) })
    : null;
}
