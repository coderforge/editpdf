import { describe, expect, it } from "vitest";
import { filenameFrom } from "../api/client";
import { rotationsOf } from "../tools/RotateTool";

describe("filenameFrom", () => {
  it("prefers the UTF-8 name", () => {
    expect(filenameFrom(`attachment; filename="Relazione _.pdf"; filename*=UTF-8''Relazione%20%C3%A8.pdf`, "x.pdf")).toBe(
      "Relazione è.pdf",
    );
  });

  it("falls back to the plain name, then to the default", () => {
    expect(filenameFrom('attachment; filename="merged.pdf"', "x.pdf")).toBe("merged.pdf");
    expect(filenameFrom(null, "x.pdf")).toBe("x.pdf");
  });
});

describe("rotationsOf", () => {
  it("groups pages by net angle and drops full turns", () => {
    const turns = new Map([
      [1, 90],
      [2, 90],
      [3, -90],
      [4, 360],
      [5, 450],
      [6, 180],
    ]);
    expect(rotationsOf(turns)).toEqual([
      { pages: "1-2,5", angle: 90 },
      { pages: "3", angle: 270 },
      { pages: "6", angle: 180 },
    ]);
  });
});
