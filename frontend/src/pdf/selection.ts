/**
 * Page selections as the API takes them ("1-3,5,8-"), checked here first so
 * the interface can explain a mistake before anything is uploaded. The rules
 * are the service's (backend/src/pdf/pages.ts); the service checks again.
 */

export interface Range {
  readonly start: number;
  readonly end: number;
}

export type SelectionResult =
  | { readonly ok: true; readonly ranges: readonly Range[] }
  | { readonly ok: false; readonly reason: "invalid" }
  | { readonly ok: false; readonly reason: "out_of_range"; readonly page: number };

const ITEM = /^(\d{1,7})(?:\s*-\s*(\d{1,7})?)?$/;

/** Parses a selection against a document of `pageCount` pages. */
export function parseSelection(text: string, pageCount: number): SelectionResult {
  const items = text.split(",").map((item) => item.trim());
  if (items.length > 1000) {
    return { ok: false, reason: "invalid" };
  }
  const ranges: Range[] = [];
  for (const item of items) {
    const match = ITEM.exec(item);
    if (match === null) {
      return { ok: false, reason: "invalid" };
    }
    const start = Number(match[1]);
    if (start < 1) {
      return { ok: false, reason: "invalid" };
    }
    if (start > pageCount) {
      return { ok: false, reason: "out_of_range", page: start };
    }
    const end = match[2] !== undefined ? Number(match[2]) : item.includes("-") ? pageCount : start;
    if (end < start) {
      return { ok: false, reason: "invalid" };
    }
    if (end > pageCount) {
      return { ok: false, reason: "out_of_range", page: end };
    }
    ranges.push({ start, end });
  }
  return { ok: true, ranges };
}

/** "1-3,4-6,7" for the contiguous parts that cutting after `cuts` makes. */
export function rangesFromCuts(cuts: ReadonlySet<number>, pageCount: number): string {
  const parts: string[] = [];
  let start = 1;
  for (let page = 1; page <= pageCount; page += 1) {
    if (cuts.has(page) || page === pageCount) {
      parts.push(start === page ? `${start}` : `${start}-${page}`);
      start = page + 1;
    }
  }
  return parts.join(",");
}

/**
 * The cuts a selection amounts to, when it is a plain partition of the
 * document (every page once, in order); null when it is anything else.
 */
export function cutsFromRanges(ranges: readonly Range[], pageCount: number): Set<number> | null {
  let next = 1;
  const cuts = new Set<number>();
  for (const range of ranges) {
    if (range.start !== next) {
      return null;
    }
    next = range.end + 1;
    if (range.end < pageCount) {
      cuts.add(range.end);
    }
  }
  return next === pageCount + 1 ? cuts : null;
}

/** The parts of a split, as page ranges. */
export function splitParts(
  mode: "each" | "every" | "ranges",
  pageCount: number,
  size: number,
  ranges: readonly Range[],
): Range[] {
  switch (mode) {
    case "each":
      return Array.from({ length: pageCount }, (_, i) => ({ start: i + 1, end: i + 1 }));
    case "every": {
      const parts: Range[] = [];
      for (let start = 1; start <= pageCount; start += size) {
        parts.push({ start, end: Math.min(start + size - 1, pageCount) });
      }
      return parts;
    }
    case "ranges":
      return [...ranges];
  }
}

/** Compresses page numbers into a selection: [1,2,3,5] is "1-3,5". */
export function selectionOf(pages: readonly number[]): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; ) {
    const start = sorted[i]!;
    let end = start;
    while (sorted[i + 1] === end + 1) {
      end += 1;
      i += 1;
    }
    parts.push(start === end ? `${start}` : `${start}-${end}`);
    i += 1;
  }
  return parts.join(",");
}
