import type React from "react";
import { useMemo } from "react";

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

/**
 * Render inline tokens: **bold**, `code`, [p. X] or (p. X) citations
 */
function renderInline(text: string): React.ReactNode {
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[p\.\s*\d+\]|\(p\.\s*\d+\))/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      return (
        <code
          key={index}
          className="px-1.5 py-0.5 rounded-md bg-surface-user border border-border/80 font-mono text-xs text-foreground font-medium"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    // Citations highlight: [p. 2] or (p. 4)
    if (/^(\[p\.\s*\d+\]|\(p\.\s*\d+\))$/.test(part)) {
      return (
        <span
          key={index}
          className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-foreground/10 text-foreground font-mono text-[11px] font-semibold mx-0.5"
          title="Verified Brand Guideline Page"
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content, className = "" }) => {
  const elements = useMemo(() => {
    if (!content) return null;

    const lines = content.split("\n");
    const blocks: React.ReactNode[] = [];
    let currentList: { type: "ul" | "ol"; items: string[] } | null = null;
    let currentParagraph: string[] = [];

    const flushList = () => {
      if (!currentList) return;
      const ListTag = currentList.type;
      const listKey = `list-${blocks.length}`;
      blocks.push(
        <ListTag
          key={listKey}
          className={`${
            currentList.type === "ul" ? "list-disc" : "list-decimal"
          } pl-5 space-y-1 my-2 text-sm leading-relaxed text-foreground`}
        >
          {currentList.items.map((item, idx) => (
            <li key={`${listKey}-${idx}`}>{renderInline(item)}</li>
          ))}
        </ListTag>
      );
      currentList = null;
    };

    const flushParagraph = () => {
      if (currentParagraph.length === 0) return;
      const pText = currentParagraph.join("\n");
      const pKey = `p-${blocks.length}`;
      blocks.push(
        <p key={pKey} className="leading-relaxed mb-2.5 last:mb-0 text-sm text-foreground">
          {renderInline(pText)}
        </p>
      );
      currentParagraph = [];
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i] || "";
      const trimmed = line.trim();

      if (!trimmed) {
        flushList();
        flushParagraph();
        continue;
      }

      // Headings
      if (trimmed.startsWith("### ")) {
        flushList();
        flushParagraph();
        blocks.push(
          <h4
            key={`h3-${blocks.length}`}
            className="font-bold text-sm tracking-tight text-foreground mt-3.5 mb-1.5"
          >
            {renderInline(trimmed.slice(4))}
          </h4>
        );
        continue;
      }

      if (trimmed.startsWith("## ")) {
        flushList();
        flushParagraph();
        blocks.push(
          <h3
            key={`h2-${blocks.length}`}
            className="font-bold text-base tracking-tight text-foreground mt-4 mb-2"
          >
            {renderInline(trimmed.slice(3))}
          </h3>
        );
        continue;
      }

      // Blockquotes
      if (trimmed.startsWith("> ")) {
        flushList();
        flushParagraph();
        blocks.push(
          <blockquote
            key={`bq-${blocks.length}`}
            className="border-l-2 border-foreground/30 pl-3.5 py-0.5 my-2.5 text-xs text-muted-foreground italic bg-foreground/[0.02] rounded-r-lg"
          >
            {renderInline(trimmed.slice(2))}
          </blockquote>
        );
        continue;
      }

      // Unordered list item
      const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/);
      if (bulletMatch) {
        flushParagraph();
        if (currentList?.type !== "ul") {
          flushList();
          currentList = { type: "ul", items: [] };
        }
        currentList.items.push(bulletMatch[1] || "");
        continue;
      }

      // Ordered list item
      const numMatch = trimmed.match(/^\d+\.\s+(.*)$/);
      if (numMatch) {
        flushParagraph();
        if (currentList?.type !== "ol") {
          flushList();
          currentList = { type: "ol", items: [] };
        }
        currentList.items.push(numMatch[1] || "");
        continue;
      }

      // Standard paragraph text
      currentParagraph.push(line);
    }

    flushList();
    flushParagraph();

    return blocks;
  }, [content]);

  return <div className={`text-foreground ${className}`}>{elements}</div>;
};

export default MarkdownViewer;
