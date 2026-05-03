import { useState } from "react";
import { ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import { CitationChip } from "./CitationChip";
import { TypingIndicator } from "./TypingIndicator";
import { cn, formatRelative } from "@/lib/utils";
import { renderMarkdown } from "@/lib/markdown";
import type { ChatMessage, Citation } from "@/api/types";

interface Props {
  message: ChatMessage;
}

// One bubble in the thread. User messages hug the right; assistant
// messages sit left and can carry citations + an expandable Sources
// section.
export function Message({ message }: Props) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";

  return (
    <div className={cn("flex animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "flex max-w-[88%] flex-col gap-1 sm:max-w-[80%]",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "vn-text break-words px-4 py-2.5 text-[14.5px] leading-relaxed",
            isUser
              ? "whitespace-pre-wrap bg-accent text-accent-ink"
              : message.error
                ? "whitespace-pre-wrap border border-danger bg-paper text-danger"
                : "md-content border-l-4 border-accent bg-paper text-ink",
          )}
        >
          {message.pending ? (
            <TypingIndicator />
          ) : message.error ? (
            <span className="inline-flex items-start gap-2">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{message.text}</span>
            </span>
          ) : isUser ? (
            message.text
          ) : (
            renderAssistant(message.text, message.citations ?? [])
          )}
        </div>

        {!message.pending &&
          !message.error &&
          message.citations &&
          message.citations.length > 0 && (
            <div className="w-full">
              <button
                type="button"
                onClick={() => setShowSources((v) => !v)}
                className="meta flex items-center gap-1 uppercase tracking-widest hover:text-ink"
              >
                {showSources ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {message.citations.length} source
                {message.citations.length > 1 ? "s" : ""}
                {message.n_retrieved ? ` · ${message.n_retrieved} retrieved` : ""}
              </button>
              {showSources && (
                <ol className="mt-2 animate-fade-in space-y-1.5">
                  {message.citations.map((c, i) => (
                    <li
                      key={i}
                      className="vn-text border border-line bg-paper px-3 py-2 text-[13px] leading-relaxed"
                    >
                      <div className="meta-strong mb-1 uppercase tracking-widest text-accent">
                        [{i + 1}] doc {c.doc_idx} · chunk {c.chunk_idx} · score {c.score.toFixed(3)}
                      </div>
                      {c.text}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}

        {!message.pending && <span className="meta">{formatRelative(message.ts)}</span>}
      </div>
    </div>
  );
}

/** Render an assistant message: markdown + interactive citation chips.
 *  Strategy:
 *   1. Replace `[N]` markers with placeholder tokens before markdown render
 *      so the formatter doesn't mangle them.
 *   2. Render markdown to safe HTML.
 *   3. Split the HTML on placeholder tokens and interleave React chips
 *      with `dangerouslySetInnerHTML` chunks. Chips stay interactive. */
function renderAssistant(text: string, citations: Citation[]) {
  const TOKEN = (n: number) => `__NOM_CITE_${n}__`;
  const seen: number[] = [];
  const protectedText = text.replace(/\[(\d+)\]/g, (_m, raw) => {
    const n = parseInt(raw, 10);
    seen.push(n);
    return TOKEN(n);
  });
  const html = renderMarkdown(protectedText);
  const parts = html.split(/__NOM_CITE_(\d+)__/);
  // Even-index parts are HTML chunks; odd-index are citation indices.
  return parts.map((p, i) => {
    if (i % 2 === 0) {
      if (!p) return null;
      return <span key={`h-${i}`} dangerouslySetInnerHTML={{ __html: p }} />;
    }
    const n = parseInt(p, 10);
    return <CitationChip key={`c-${i}`} index={n} citation={citations[n - 1]} />;
  });
}
