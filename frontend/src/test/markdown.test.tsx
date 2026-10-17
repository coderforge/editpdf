import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown, parseBlocks } from "../legal/Markdown";
import termsEn from "../../../legal/terms.en.md?raw";
import termsIt from "../../../legal/terms.it.md?raw";

describe("Markdown", () => {
  it("keeps a numbered list going across nested bullets", () => {
    const blocks = parseBlocks("1. First:\n   - a\n   - b\n2. Second\n\nAfter.");
    expect(blocks).toEqual([
      {
        kind: "list",
        ordered: true,
        items: [
          { text: "First:", children: ["a", "b"] },
          { text: "Second", children: [] },
        ],
      },
      { kind: "paragraph", text: "After." },
    ]);
  });

  it("renders links, bold and code, and never raw HTML", () => {
    const { container } = render(
      <Markdown source={"Read **this** and `that` at [the site](https://example.org). <img src=x onerror=alert(1)>"} />,
    );
    expect(container.querySelector("strong")?.textContent).toBe("this");
    expect(container.querySelector("code")?.textContent).toBe("that");
    expect(container.querySelector("a")?.getAttribute("href")).toBe("https://example.org");
    expect(container.querySelector("img")).toBeNull();
  });

  it("drops links to other schemes", () => {
    const { container } = render(<Markdown source="[x](javascript:alert(1))" />);
    expect(container.querySelector("a")).toBeNull();
  });

  it("gives both versions of the terms the same sections", () => {
    const headings = (source: string) =>
      parseBlocks(source).filter((block) => block.kind === "heading" && block.level === 2).length;
    expect(headings(termsEn)).toBe(15);
    expect(headings(termsIt)).toBe(headings(termsEn));
  });
});
