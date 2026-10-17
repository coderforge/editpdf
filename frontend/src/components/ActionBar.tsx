import { useId, useState, type ReactNode } from "react";
import { saveFile } from "../api/client";
import { format, useI18n } from "../i18n";
import { TERMS_VERSION } from "../service";
import { readStored, writeStored } from "../storage";
import { Link } from "../router";
import { AlertIcon, CheckIcon } from "./icons";
import type { OperationState } from "./useOperation";

const CONSENT_KEY = "editpdf.termsAccepted";

/**
 * Whether the visitor accepted the Terms and Conditions in force. Kept per
 * browser and per version of the terms: new terms are accepted again.
 */
export function useConsent(): [boolean, (accepted: boolean) => void] {
  const [accepted, setAccepted] = useState(() => readStored(CONSENT_KEY) === TERMS_VERSION);
  const update = (value: boolean) => {
    setAccepted(value);
    writeStored(CONSENT_KEY, value ? TERMS_VERSION : "");
  };
  return [accepted, update];
}

interface ActionBarProps {
  readonly label: string;
  /** Why the action cannot run yet, if it cannot; shown instead of running it. */
  readonly blocker: string | null;
  readonly state: OperationState;
  readonly onRun: () => void;
  readonly onStartOver: () => void;
  readonly summary?: ReactNode;
}

/** The terms, the button, and what happened when it was pressed. */
export function ActionBar({ label, blocker, state, onRun, onStartOver, summary }: ActionBarProps) {
  const { t } = useI18n();
  const [accepted, setAccepted] = useConsent();
  const consentId = useId();
  const running = state.status === "running";
  const problem = !accepted ? t.consent.required : blocker;

  return (
    <section className="action-bar" aria-live="polite">
      <div className="action-bar__main">
        {summary === undefined ? null : <div className="action-bar__summary">{summary}</div>}
        <label className="consent" htmlFor={consentId}>
          <input id={consentId} type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          <span>
            {t.consent.before}
            <Link to="terms" target="_blank">
              {t.consent.link}
            </Link>
            {t.consent.after}
          </span>
        </label>
      </div>
      <div className="action-bar__action">
        <button type="button" className="button button--primary button--large" disabled={problem !== null || running} onClick={onRun}>
          {running ? (
            <>
              <span className="spinner" aria-hidden="true" />
              {state.progress.phase === "uploading"
                ? format(t.progress.uploading, { percent: state.progress.percent })
                : t.progress.processing}
            </>
          ) : (
            label
          )}
        </button>
        {problem !== null && !running ? <p className="action-bar__blocker">{problem}</p> : null}
      </div>
      {running ? (
        <div
          className="progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={state.progress.phase === "uploading" ? state.progress.percent : undefined}
        >
          <div
            className={`progress__bar${state.progress.phase === "processing" ? " progress__bar--busy" : ""}`}
            style={{ width: state.progress.phase === "uploading" ? `${state.progress.percent}%` : "100%" }}
          />
        </div>
      ) : null}
      {state.status === "done" ? (
        <div className="notice notice--success">
          <CheckIcon />
          <span>{format(t.progress.done, { name: state.download.filename })}</span>
          <button type="button" className="button button--link" onClick={() => saveFile(state.download.blob, state.download.filename)}>
            {t.progress.downloadAgain}
          </button>
          <button type="button" className="button button--link" onClick={onStartOver}>
            {t.progress.startOver}
          </button>
        </div>
      ) : null}
      {state.status === "failed" ? (
        <div className="notice notice--error" role="alert">
          <AlertIcon />
          <div>
            <p>{t.errors[state.problem.code]}</p>
            {state.problem.detail !== undefined && state.problem.code !== "network" ? (
              <p className="notice__detail">
                {t.errors.details}: {state.problem.detail}
                {state.problem.requestId === undefined ? null : ` (${t.errors.requestId} ${state.problem.requestId})`}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
