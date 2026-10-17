import type { ReactNode } from "react";

/**
 * Renders the small Markdown subset the legal texts use: headings, paragraphs,
 * bullet and numbered lists, rules, **bold**, _italics_, `code` and links.
 * It builds React elements, never HTML strings, so nothing in a text can
 * become markup.
 */

function slug(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function safeHref(href: string): string | null {
  return /^(https?:|mailto:|\/|#)/i.test(href) ? href : null;
}

const INLINE = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+\)|`[^`]+`|_[^_]+_)/g;

export function renderInline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index}>{renderInline(part.slice(2, -2))}</strong>;
    }
    if (part.startsWith("_") && part.endsWith("_") && part.length > 2) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link !== null) {
      const href = safeHref(link[2] ?? "");
      return href === null ? (
        link[1]
      ) : (
        <a key={index} href={href} {...(/^https?:/i.test(href) ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
          {link[1]}
        </a>
      );
    }
    return part;
  });
}

interface ListItem {
  text: string;
  /** A bullet list nested under the item (indented lines). */
  children: string[];
}

type Block =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: ListItem[] }
  | { kind: "rule" };

export function parseBlocks(source: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: ListItem[] } | null = null;

  const flush = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
    if (list !== null) {
      blocks.push({ kind: "list", ...list });
      list = null;
    }
  };

  for (const raw of source.split(/\r?\n/)) {
    const line = raw.trimEnd();
    const indented = /^\s{2,}\S/.test(raw);
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+\.\s+(.*)$/.exec(line);
    const last = list?.items[list.items.length - 1];
    if (line.trim() === "") {
      // A blank line ends a paragraph; a list goes on if the next line continues it.
      if (paragraph.length > 0) {
        flush();
      }
    } else if (heading !== null) {
      flush();
      blocks.push({ kind: "heading", level: heading[1]!.length as 1 | 2 | 3, text: heading[2] ?? "" });
    } else if (/^-{3,}$/.test(line.trim())) {
      flush();
      blocks.push({ kind: "rule" });
    } else if (indented && bullet !== null && last !== undefined) {
      last.children.push(bullet[1] ?? "");
    } else if (bullet !== null || numbered !== null) {
      const ordered = numbered !== null;
      if (paragraph.length > 0 || (list !== null && list.ordered !== ordered)) {
        flush();
      }
      list ??= { ordered, items: [] };
      list.items.push({ text: (bullet ?? numbered)![1] ?? "", children: [] });
    } else if (indented && last !== undefined) {
      // A continuation line of the last list item, or of its last child.
      if (last.children.length > 0) {
        last.children[last.children.length - 1] += ` ${line.trim()}`;
      } else {
        last.text += ` ${line.trim()}`;
      }
    } else {
      if (list !== null) {
        flush();
      }
      paragraph.push(line.trim());
    }
  }
  flush();
  return blocks;
}

export function Markdown({ source }: { readonly source: string }) {
  return (
    <>
      {parseBlocks(source).map((block, index) => {
        switch (block.kind) {
          case "heading": {
            const Tag = `h${block.level}` as const;
            return (
              <Tag key={index} id={slug(block.text)}>
                {renderInline(block.text)}
              </Tag>
            );
          }
          case "paragraph":
            return <p key={index}>{renderInline(block.text)}</p>;
          case "list": {
            const items = block.items.map((item, i) => (
              <li key={i}>
                {renderInline(item.text)}
                {item.children.length === 0 ? null : (
                  <ul>
                    {item.children.map((child, j) => (
                      <li key={j}>{renderInline(child)}</li>
                    ))}
                  </ul>
                )}
              </li>
            ));
            return block.ordered ? <ol key={index}>{items}</ol> : <ul key={index}>{items}</ul>;
          }
          case "rule":
            return <hr key={index} />;
        }
      })}
    </>
  );
}
