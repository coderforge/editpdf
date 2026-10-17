import { describe, expect, it } from "vitest";
import { cutsFromRanges, parseSelection, rangesFromCuts, selectionOf, splitParts } from "../pdf/selection";

describe("parseSelection", () => {
  it("reads numbers, ranges and open ranges", () => {
    expect(parseSelection("1-3, 5 ,8-", 10)).toEqual({
      ok: true,
      ranges: [
        { start: 1, end: 3 },
        { start: 5, end: 5 },
        { start: 8, end: 10 },
      ],
    });
  });

  it.each(["", "a", "0", "3-1", "1,,2", "-2"])("refuses %j", (text) => {
    expect(parseSelection(text, 10)).toEqual({ ok: false, reason: "invalid" });
  });

  it("names the page past the end", () => {
    expect(parseSelection("2-12", 10)).toEqual({ ok: false, reason: "out_of_range", page: 12 });
    expect(parseSelection("11-", 10)).toEqual({ ok: false, reason: "out_of_range", page: 11 });
  });
});

describe("cuts", () => {
  it("turns cuts into ranges and back", () => {
    const text = rangesFromCuts(new Set([3, 7]), 10);
    expect(text).toBe("1-3,4-7,8-10");
    const parsed = parseSelection(text, 10);
    expect(parsed.ok && cutsFromRanges(parsed.ranges, 10)).toEqual(new Set([3, 7]));
  });

  it("has no cuts for selections that are not a partition", () => {
    const parsed = parseSelection("1-3,5-10", 10);
    expect(parsed.ok && cutsFromRanges(parsed.ranges, 10)).toBeNull();
    const overlapping = parseSelection("1-5,5-10", 10);
    expect(overlapping.ok && cutsFromRanges(overlapping.ranges, 10)).toBeNull();
  });

  it("gives single pages as numbers", () => {
    expect(rangesFromCuts(new Set([1, 2]), 3)).toBe("1,2,3");
  });
});

describe("splitParts", () => {
  it("cuts every N pages", () => {
    expect(splitParts("every", 5, 2, [])).toEqual([
      { start: 1, end: 2 },
      { start: 3, end: 4 },
      { start: 5, end: 5 },
    ]);
  });
});

describe("selectionOf", () => {
  it("compresses runs of pages", () => {
    expect(selectionOf([5, 1, 2, 3, 9, 8])).toBe("1-3,5,8-9");
    expect(selectionOf([])).toBe("");
  });
});
