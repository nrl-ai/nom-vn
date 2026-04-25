import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Citation } from "@/api/types";

interface Props {
  index: number; // 1-based as the LLM cites it
  citation: Citation | undefined;
  onClick?: () => void;
}

// An inline `[N]` chip that:
// - hovers a tooltip showing a short preview of the cited chunk
// - clicks to scroll the Sources panel below the message into view
// Sized to sit in the run of text without breaking the line.
export function CitationChip({ index, citation, onClick }: Props) {
  const preview = citation
    ? citation.text.slice(0, 240) + (citation.text.length > 240 ? "…" : "")
    : "Citation not available.";

  return (
    <Tooltip delayDuration={150}>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="mx-0.5 inline-flex h-5 -translate-y-px items-center justify-center bg-accent px-1.5 align-baseline font-mono text-[10.5px] font-semibold text-accent-ink transition-colors hover:bg-accent-soft"
        >
          {index}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="vn-text">
        {citation ? (
          <>
            <div className="mb-1 font-mono text-[9.5px] uppercase tracking-wider text-accent-soft">
              doc {citation.doc_idx} · chunk {citation.chunk_idx} · score{" "}
              {citation.score.toFixed(3)}
            </div>
            <div className="leading-relaxed">{preview}</div>
          </>
        ) : (
          preview
        )}
      </TooltipContent>
    </Tooltip>
  );
}
