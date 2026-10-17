import { useCallback, useState } from "react";
import { ActionBar } from "../components/ActionBar";
import { Dropzone, DropOverlay, isPdfFile, useDropHint, useWindowDrop } from "../components/Dropzone";
import { RotateIcon, RotateLeftIcon } from "../components/icons";
import { PageThumb } from "../components/PageThumb";
import { useOperation } from "../components/useOperation";
import { format, useI18n } from "../i18n";
import { useDocument } from "../pdf/hooks";
import { releasePreview } from "../pdf/preview";
import { selectionOf } from "../pdf/selection";
import type { Rotation } from "../api/client";
import { useService } from "../service";
import { FileHeader, Notices, sizeBlocker, ToolHeader } from "./common";

/** The rotations the API takes for these turns: one item per angle, pages compressed. */
export function rotationsOf(turns: ReadonlyMap<number, number>): Rotation[] {
  const byAngle = new Map<90 | 180 | 270, number[]>();
  for (const [page, turn] of turns) {
    const angle = ((turn % 360) + 360) % 360;
    if (angle === 90 || angle === 180 || angle === 270) {
      byAngle.set(angle, [...(byAngle.get(angle) ?? []), page]);
    }
  }
  return [...byAngle].map(([angle, pages]) => ({ pages: selectionOf(pages), angle }));
}

export function RotateTool() {
  const i18n = useI18n();
  const { t } = i18n;
  const { limits } = useService();
  const [file, setFile] = useState<File | null>(null);
  // Clockwise turn per page, in degrees; may go past 360 so the preview animates the short way.
  const [turns, setTurns] = useState<ReadonlyMap<number, number>>(new Map());
  const [notices, setNotices] = useState<readonly string[]>([]);
  const operation = useOperation();
  const document = useDocument(file);
  const pageCount = document.status === "ready" ? document.pageCount : 0;
  const hint = useDropHint(false, 1, limits.maxUploadBytes);

  const accept = useCallback(
    (dropped: File[]) => {
      const pdf = dropped.find(isPdfFile);
      if (pdf === undefined) {
        setNotices(dropped.map((item) => format(t.file.notPdf, { name: item.name })));
        return;
      }
      setNotices([]);
      setFile((current) => {
        if (current !== null) {
          releasePreview(current);
        }
        return pdf;
      });
      setTurns(new Map());
      operation.reset();
    },
    [t, operation.reset],
  );
  const dragging = useWindowDrop(accept);

  const turn = (pages: readonly number[], by: number) => {
    setTurns((current) => {
      const next = new Map(current);
      for (const page of pages) {
        next.set(page, (next.get(page) ?? 0) + by);
      }
      return next;
    });
    operation.reset();
  };
  const allPages = Array.from({ length: pageCount }, (_, i) => i + 1);

  const rotations = rotationsOf(turns);
  const changed = [...turns.values()].filter((angle) => ((angle % 360) + 360) % 360 !== 0).length;

  const startOver = () => {
    if (file !== null) {
      releasePreview(file);
    }
    setFile(null);
    setTurns(new Map());
    operation.reset();
  };

  let blocker: string | null = null;
  if (document.status === "loading") {
    blocker = t.file.loadingPreview;
  } else if (document.status === "failed") {
    blocker = document.reason === "encrypted" ? t.file.passwordProtected : t.file.unreadable;
  } else if (rotations.length === 0) {
    blocker = t.rotate.noChanges;
  } else if (file !== null) {
    blocker = sizeBlocker(file.size, limits.maxUploadBytes, i18n);
  }

  const run = () => {
    if (file === null) {
      return;
    }
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("rotations", JSON.stringify(rotations));
    void operation.run("rotate", form);
  };

  return (
    <div className="tool">
      <ToolHeader title={t.rotate.title} description={t.rotate.description} />
      <DropOverlay visible={dragging} />
      <Notices messages={notices} onDismiss={() => setNotices([])} />
      {file === null ? (
        <Dropzone multiple={false} onFiles={accept} hint={hint} />
      ) : (
        <>
          <FileHeader file={file} state={document} onReplace={startOver} />
          {pageCount > 0 ? (
            <>
              <div className="toolbar">
                <button type="button" className="button button--ghost" onClick={() => turn(allPages, -90)}>
                  <RotateLeftIcon width={16} height={16} />
                  {t.rotate.allLeft}
                </button>
                <button type="button" className="button button--ghost" onClick={() => turn(allPages, 90)}>
                  <RotateIcon width={16} height={16} />
                  {t.rotate.allRight}
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  disabled={turns.size === 0}
                  onClick={() => {
                    setTurns(new Map());
                    operation.reset();
                  }}
                >
                  {t.rotate.reset}
                </button>
              </div>
              <ol className="page-grid">
                {allPages.map((page) => {
                  const angle = turns.get(page) ?? 0;
                  const turned = ((angle % 360) + 360) % 360 !== 0;
                  return (
                    <li key={page} className={`page-grid__item${turned ? " page-grid__item--turned" : ""}`}>
                      <PageThumb file={file} number={page} rotation={angle} label={format(t.file.page, { number: page })}>
                        <span className="thumb__actions">
                          <button
                            type="button"
                            className="icon-button icon-button--solid"
                            onClick={() => turn([page], -90)}
                            aria-label={format(t.rotate.left, { number: page })}
                            title={format(t.rotate.left, { number: page })}
                          >
                            <RotateLeftIcon width={16} height={16} />
                          </button>
                          <button
                            type="button"
                            className="icon-button icon-button--solid"
                            onClick={() => turn([page], 90)}
                            aria-label={format(t.rotate.right, { number: page })}
                            title={format(t.rotate.right, { number: page })}
                          >
                            <RotateIcon width={16} height={16} />
                          </button>
                        </span>
                      </PageThumb>
                    </li>
                  );
                })}
              </ol>
            </>
          ) : null}
          <ActionBar
            label={t.rotate.action}
            blocker={blocker}
            state={operation.state}
            onRun={run}
            onStartOver={startOver}
            summary={changed > 0 ? <span>{t.rotate.changed(changed)}</span> : undefined}
          />
        </>
      )}
    </div>
  );
}
