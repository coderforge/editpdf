import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { arrayMove, rectSortingStrategy, SortableContext, sortableKeyboardCoordinates, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useCallback, useMemo, useState } from "react";
import { ActionBar } from "../components/ActionBar";
import { Dropzone, DropOverlay, isPdfFile, useDropHint, useWindowDrop } from "../components/Dropzone";
import { CloseIcon, GripIcon, SortIcon, SwapIcon } from "../components/icons";
import { PageThumb } from "../components/PageThumb";
import { useOperation } from "../components/useOperation";
import { format, useI18n } from "../i18n";
import type { DocumentState } from "../pdf/hooks";
import { releasePreview } from "../pdf/preview";
import { useDocuments } from "../pdf/useDocuments";
import { useService } from "../service";
import { DocumentStatus, Notices, sizeBlocker, ToolHeader } from "./common";

interface Item {
  readonly id: string;
  readonly file: File;
}

let nextId = 0;

function FileCard({
  item,
  index,
  state,
  onRemove,
}: {
  readonly item: Item;
  readonly index: number;
  readonly state: DocumentState | undefined;
  readonly onRemove: () => void;
}) {
  const { t, formatBytes } = useI18n();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id });
  const failed = state?.status === "failed";
  return (
    <li
      ref={setNodeRef}
      className={`file-card${isDragging ? " file-card--dragging" : ""}${failed ? " file-card--failed" : ""}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      aria-label={format(t.file.dragHandle, { name: item.file.name })}
    >
      <span className="file-card__order" aria-hidden="true">
        {index + 1}
      </span>
      <PageThumb file={item.file} number={1} label={item.file.name}>
        <span className="file-card__grip" aria-hidden="true">
          <GripIcon width={16} height={16} />
        </span>
      </PageThumb>
      <div className="file-card__text">
        <span className="file-card__name" title={item.file.name}>
          {item.file.name}
        </span>
        <span className="file-card__meta">
          <DocumentStatus state={state} /> · {formatBytes(item.file.size)}
        </span>
      </div>
      <button
        type="button"
        className="icon-button file-card__remove"
        onClick={onRemove}
        onPointerDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
        aria-label={format(t.file.remove, { name: item.file.name })}
      >
        <CloseIcon width={16} height={16} />
      </button>
    </li>
  );
}

export function MergeTool() {
  const i18n = useI18n();
  const { t } = i18n;
  const { limits } = useService();
  const [items, setItems] = useState<readonly Item[]>([]);
  const [notices, setNotices] = useState<readonly string[]>([]);
  const operation = useOperation();
  const files = useMemo(() => items.map((item) => item.file), [items]);
  const states = useDocuments(files);
  const hint = useDropHint(true, limits.maxFiles, limits.maxUploadBytes);

  const add = useCallback(
    (dropped: File[]) => {
      const messages: string[] = [];
      const pdfs = dropped.filter((file) => {
        if (!isPdfFile(file)) {
          messages.push(format(t.file.notPdf, { name: file.name }));
          return false;
        }
        return true;
      });
      setItems((current) => {
        const room = Math.max(0, limits.maxFiles - current.length);
        if (pdfs.length > room) {
          messages.push(format(t.file.tooMany, { max: limits.maxFiles }));
        }
        return [...current, ...pdfs.slice(0, room).map((file) => ({ id: `file-${(nextId += 1)}`, file }))];
      });
      setNotices(messages);
      operation.reset();
    },
    [t, limits.maxFiles, operation.reset],
  );

  const dragging = useWindowDrop(add);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const remove = (id: string) => {
    const removed = items.find((item) => item.id === id);
    if (removed !== undefined) {
      releasePreview(removed.file);
    }
    setItems((current) => current.filter((item) => item.id !== id));
    operation.reset();
  };

  const reorder = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over !== null && active.id !== over.id) {
      setItems((current) => {
        const from = current.findIndex((item) => item.id === active.id);
        const to = current.findIndex((item) => item.id === over.id);
        return arrayMove([...current], from, to);
      });
      operation.reset();
    }
  };

  const startOver = () => {
    for (const item of items) {
      releasePreview(item.file);
    }
    setItems([]);
    setNotices([]);
    operation.reset();
  };

  const totalBytes = items.reduce((sum, item) => sum + item.file.size, 0);
  const totalPages = items.reduce((sum, item) => {
    const state = states.get(item.file);
    return sum + (state?.status === "ready" ? state.pageCount : 0);
  }, 0);
  const failure = items.map((item) => states.get(item.file)).find((state) => state?.status === "failed");
  const blocker =
    items.length < 2
      ? t.merge.needTwo
      : failure?.status === "failed"
        ? failure.reason === "encrypted"
          ? t.file.passwordProtected
          : t.file.unreadable
        : sizeBlocker(totalBytes, limits.maxUploadBytes, i18n);

  const run = () => {
    const form = new FormData();
    for (const item of items) {
      form.append("files", item.file, item.file.name);
    }
    void operation.run("merge", form);
  };

  return (
    <div className="tool">
      <ToolHeader title={t.merge.title} description={t.merge.description} />
      <DropOverlay visible={dragging} />
      <Notices messages={notices} onDismiss={() => setNotices([])} />
      {items.length === 0 ? (
        <Dropzone multiple onFiles={add} hint={hint} />
      ) : (
        <>
          <div className="toolbar">
            <span className="toolbar__summary">
              {format(t.merge.total, {
                files: t.merge.files(items.length),
                pages: t.file.pages(totalPages),
                size: i18n.formatBytes(totalBytes),
              })}
            </span>
            <button
              type="button"
              className="button button--ghost"
              onClick={() =>
                setItems((current) =>
                  [...current].sort((a, b) => a.file.name.localeCompare(b.file.name, undefined, { numeric: true })),
                )
              }
            >
              <SortIcon width={16} height={16} />
              {t.merge.sortByName}
            </button>
            <button type="button" className="button button--ghost" onClick={() => setItems((current) => [...current].reverse())}>
              <SwapIcon width={16} height={16} />
              {t.merge.reverse}
            </button>
          </div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={reorder}>
            <SortableContext items={items.map((item) => item.id)} strategy={rectSortingStrategy}>
              <ol className="file-grid">
                {items.map((item, index) => (
                  <FileCard
                    key={item.id}
                    item={item}
                    index={index}
                    state={states.get(item.file)}
                    onRemove={() => remove(item.id)}
                  />
                ))}
                {items.length < limits.maxFiles ? (
                  <li className="file-grid__add">
                    <Dropzone multiple compact onFiles={add} hint={hint} />
                  </li>
                ) : null}
              </ol>
            </SortableContext>
          </DndContext>
          <ActionBar
            label={t.merge.action(items.length)}
            blocker={blocker}
            state={operation.state}
            onRun={run}
            onStartOver={startOver}
          />
        </>
      )}
    </div>
  );
}
