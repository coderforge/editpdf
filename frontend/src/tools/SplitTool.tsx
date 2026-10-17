import { useCallback, useId, useMemo, useState } from "react";
import { ActionBar } from "../components/ActionBar";
import { Dropzone, DropOverlay, isPdfFile, useDropHint, useWindowDrop } from "../components/Dropzone";
import { SplitIcon } from "../components/icons";
import { PageThumb } from "../components/PageThumb";
import { useOperation } from "../components/useOperation";
import { format, useI18n } from "../i18n";
import { useDocument } from "../pdf/hooks";
import { releasePreview } from "../pdf/preview";
import { cutsFromRanges, parseSelection, rangesFromCuts, splitParts, type Range } from "../pdf/selection";
import { useService } from "../service";
import { FileHeader, Notices, sizeBlocker, ToolHeader } from "./common";

type Mode = "each" | "every" | "ranges";

const PART_COLORS = 8;

function pretty(selection: string): string {
  return selection.split(",").join(", ");
}

export function SplitTool() {
  const i18n = useI18n();
  const { t } = i18n;
  const { limits } = useService();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<Mode>("each");
  const [size, setSize] = useState("2");
  const [rangesText, setRangesText] = useState("");
  const [notices, setNotices] = useState<readonly string[]>([]);
  const operation = useOperation();
  const document = useDocument(file);
  const pageCount = document.status === "ready" ? document.pageCount : 0;
  const hint = useDropHint(false, 1, limits.maxUploadBytes);
  const modeName = useId();
  const sizeId = useId();
  const rangesId = useId();

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
      setRangesText("");
      operation.reset();
    },
    [t, operation.reset],
  );
  const dragging = useWindowDrop(accept);

  const sizeNumber = /^\d{1,7}$/.test(size.trim()) && Number(size) >= 1 ? Number(size) : null;
  const parsed = mode === "ranges" && pageCount > 0 ? parseSelection(rangesText, pageCount) : null;

  const parts: readonly Range[] = useMemo(() => {
    if (pageCount === 0) {
      return [];
    }
    if (mode === "ranges") {
      return parsed?.ok === true ? parsed.ranges : [];
    }
    if (mode === "every") {
      return sizeNumber === null ? [] : splitParts("every", pageCount, sizeNumber, []);
    }
    return splitParts("each", pageCount, 1, []);
  }, [mode, pageCount, parsed, sizeNumber]);

  // Where the document is cut, when the parts are a plain partition of it.
  const cuts = useMemo(() => (parts.length === 0 ? null : cutsFromRanges(parts, pageCount)), [parts, pageCount]);

  // The parts each page goes into, for the coloured badges.
  const partsOfPage = useMemo(() => {
    const map = new Map<number, number[]>();
    parts.forEach((part, index) => {
      for (let page = part.start; page <= part.end; page += 1) {
        map.set(page, [...(map.get(page) ?? []), index]);
      }
    });
    return map;
  }, [parts]);

  const chooseMode = (next: Mode) => {
    if (next === "ranges" && rangesText.trim() === "" && pageCount > 0) {
      // Start from what is on screen, or halves: an example of the syntax.
      const start = cuts ?? (pageCount > 1 ? new Set([Math.ceil(pageCount / 2)]) : new Set<number>());
      setRangesText(pretty(rangesFromCuts(start, pageCount)));
    }
    setMode(next);
    operation.reset();
  };

  const toggleCut = (page: number) => {
    const next = new Set(cuts ?? []);
    if (next.has(page)) {
      next.delete(page);
    } else {
      next.add(page);
    }
    setMode("ranges");
    setRangesText(pretty(rangesFromCuts(next, pageCount)));
    operation.reset();
  };

  const startOver = () => {
    if (file !== null) {
      releasePreview(file);
    }
    setFile(null);
    setMode("each");
    setRangesText("");
    operation.reset();
  };

  let blocker: string | null = null;
  if (document.status === "loading") {
    blocker = t.file.loadingPreview;
  } else if (document.status === "failed") {
    blocker = document.reason === "encrypted" ? t.file.passwordProtected : t.file.unreadable;
  } else if (mode === "every" && sizeNumber === null) {
    blocker = t.split.invalid;
  } else if (parsed !== null && !parsed.ok) {
    blocker =
      parsed.reason === "out_of_range"
        ? format(t.split.outOfRange, { page: parsed.page, count: pageCount })
        : t.split.invalid;
  } else if (file !== null) {
    blocker = sizeBlocker(file.size, limits.maxUploadBytes, i18n);
  }

  const run = () => {
    if (file === null) {
      return;
    }
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("mode", mode);
    if (mode === "every") {
      form.append("size", String(sizeNumber));
    } else if (mode === "ranges") {
      form.append("ranges", rangesText);
    }
    void operation.run("split", form);
  };

  return (
    <div className="tool">
      <ToolHeader title={t.split.title} description={t.split.description} />
      <DropOverlay visible={dragging} />
      <Notices messages={notices} onDismiss={() => setNotices([])} />
      {file === null ? (
        <Dropzone multiple={false} onFiles={accept} hint={hint} />
      ) : (
        <>
          <FileHeader file={file} state={document} onReplace={startOver} />
          <fieldset className="options" disabled={document.status !== "ready"}>
            <legend>{t.split.mode}</legend>
            <div className="segmented" role="radiogroup">
              {(["each", "every", "ranges"] as const).map((value) => (
                <label key={value} className={`segmented__option${mode === value ? " segmented__option--active" : ""}`}>
                  <input type="radio" name={modeName} value={value} checked={mode === value} onChange={() => chooseMode(value)} />
                  {value === "each" ? t.split.modeEach : value === "every" ? t.split.modeEvery : t.split.modeRanges}
                </label>
              ))}
            </div>
            {mode === "every" ? (
              <div className="field field--inline">
                <label htmlFor={sizeId}>{t.split.everyLabel}</label>
                <input
                  id={sizeId}
                  type="number"
                  min={1}
                  max={Math.max(pageCount, 1)}
                  inputMode="numeric"
                  value={size}
                  onChange={(event) => {
                    setSize(event.target.value);
                    operation.reset();
                  }}
                />
              </div>
            ) : null}
            {mode === "ranges" ? (
              <div className="field">
                <label htmlFor={rangesId}>{t.split.rangesLabel}</label>
                <input
                  id={rangesId}
                  type="text"
                  spellCheck={false}
                  autoComplete="off"
                  value={rangesText}
                  aria-invalid={parsed !== null && !parsed.ok}
                  aria-describedby={`${rangesId}-hint`}
                  placeholder="1-3, 4-8, 9-"
                  onChange={(event) => {
                    setRangesText(event.target.value);
                    operation.reset();
                  }}
                />
                <p className="field__hint" id={`${rangesId}-hint`}>
                  {t.split.rangesHint}
                </p>
              </div>
            ) : null}
          </fieldset>
          {pageCount > 0 ? (
            <ol className="page-grid page-grid--split">
              {Array.from({ length: pageCount }, (_, i) => i + 1).map((page) => {
                const inParts = partsOfPage.get(page) ?? [];
                const first = inParts[0];
                return (
                  <li
                    key={page}
                    className={`page-grid__item${first === undefined ? " page-grid__item--unused" : ` part-${first % PART_COLORS}`}`}
                  >
                    <PageThumb file={file} number={page} label={format(t.file.page, { number: page })}>
                      <span className="part-badges">
                        {inParts.slice(0, 3).map((index) => (
                          <span key={index} className={`part-badge part-${index % PART_COLORS}`}>
                            {format(t.split.part, { number: index + 1 })}
                          </span>
                        ))}
                      </span>
                    </PageThumb>
                    {page < pageCount ? (
                      <button
                        type="button"
                        className={`cut${cuts?.has(page) === true ? " cut--active" : ""}`}
                        aria-pressed={cuts?.has(page) === true}
                        aria-label={
                          cuts?.has(page) === true
                            ? format(t.split.uncutAfter, { number: page, next: page + 1 })
                            : format(t.split.cutAfter, { number: page })
                        }
                        title={
                          cuts?.has(page) === true
                            ? format(t.split.uncutAfter, { number: page, next: page + 1 })
                            : format(t.split.cutAfter, { number: page })
                        }
                        onClick={() => toggleCut(page)}
                      >
                        <SplitIcon width={16} height={16} />
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          ) : null}
          <ActionBar
            label={parts.length > 0 ? t.split.action(parts.length) : t.split.title}
            blocker={blocker}
            state={operation.state}
            onRun={run}
            onStartOver={startOver}
            summary={parts.length > 0 ? <span>{t.split.parts(parts.length)}</span> : undefined}
          />
        </>
      )}
    </div>
  );
}
