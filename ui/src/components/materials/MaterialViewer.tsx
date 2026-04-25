import { useState } from "react";
import { Download, Loader2, AlertCircle, FileText, Eye } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useMaterialText } from "@/api/queries";
import { api } from "@/api/client";
import { getFileTypeMeta, type FileKind } from "@/lib/fileTypes";
import { cn, formatBytes } from "@/lib/utils";
import type { Material } from "@/api/types";

interface Props {
  spaceId: string | null;
  material: Material | null;
  onClose: () => void;
}

type Tab = "original" | "extracted";

export function MaterialViewer({ spaceId, material, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("original");
  const open = !!spaceId && !!material;
  const meta = material ? getFileTypeMeta(material.name) : null;
  const rawUrl = open ? api.materialRawUrl(spaceId!, material!.id) : "";
  // Office formats need pages for the Original-tab structured view too,
  // so we fetch unconditionally (cached, cheap after first hit).
  const officeKinds: FileKind[] = ["docx", "xlsx", "pptx"];
  const needsPages = tab === "extracted" || (meta && officeKinds.includes(meta.kind));
  const textQ = useMaterialText(spaceId, needsPages && material ? material.id : null);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent className="flex max-h-[90vh] !w-[92vw] !max-w-4xl flex-col p-0">
        {material && meta && (
          <>
            <DialogHeader className="border-b border-line-soft px-5 pb-3 pt-4">
              <div className="flex items-center gap-2">
                <meta.icon size={16} className={meta.colorClass} />
                <DialogTitle className="vn-text flex-1 truncate">{material.name}</DialogTitle>
              </div>
              <DialogDescription className="font-mono text-[10.5px] uppercase tracking-widest">
                {meta.label} · {formatBytes(material.n_bytes)} ·{" "}
                {material.n_chunks > 0 ? `${material.n_chunks} chunks` : "pending index"}
              </DialogDescription>
            </DialogHeader>

            <div className="flex shrink-0 border-b border-line-soft px-3">
              <TabButton active={tab === "original"} onClick={() => setTab("original")}>
                <Eye size={12} /> Original
              </TabButton>
              <TabButton active={tab === "extracted"} onClick={() => setTab("extracted")}>
                <FileText size={12} /> Extracted
              </TabButton>
              <div className="ml-auto flex items-center pr-1">
                <a
                  href={rawUrl}
                  download={material.name}
                  className="inline-flex items-center gap-1 px-2 py-1 font-mono text-[10.5px] uppercase tracking-widest text-ink-mute hover:text-ink"
                >
                  <Download size={11} />
                  Download
                </a>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-hidden bg-bg">
              {tab === "original" ? (
                <OriginalView
                  material={material}
                  kind={meta.kind}
                  url={rawUrl}
                  pages={textQ.data?.pages ?? null}
                  pagesLoading={textQ.isLoading}
                />
              ) : (
                <ExtractedView
                  loading={textQ.isLoading}
                  error={textQ.isError ? (textQ.error as Error).message : null}
                  chunks={textQ.data?.chunks ?? []}
                  fallbackText={textQ.data?.text ?? ""}
                  nChars={textQ.data?.n_chars ?? 0}
                  nChunks={material.n_chunks}
                />
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 border-b-2 px-3 py-2 font-mono text-[11px] uppercase tracking-widest transition-colors",
        active ? "border-accent text-ink" : "border-transparent text-ink-mute hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

function OriginalView({
  material,
  kind,
  url,
  pages,
  pagesLoading,
}: {
  material: Material;
  kind: FileKind;
  url: string;
  pages: string[] | null;
  pagesLoading: boolean;
}) {
  if (kind === "pdf") {
    return (
      <iframe
        title={material.name}
        src={url + "#view=Fit"}
        className="h-full w-full border-0 bg-white"
      />
    );
  }
  if (kind === "image") {
    return (
      <div className="flex h-full w-full items-center justify-center overflow-auto bg-bg-soft p-4">
        <img
          src={url}
          alt={material.name}
          className="max-h-full max-w-full bg-white object-contain shadow-editorial-soft"
        />
      </div>
    );
  }
  if (kind === "html") {
    return (
      <iframe
        title={material.name}
        src={url}
        sandbox=""
        className="h-full w-full border-0 bg-white"
      />
    );
  }
  if (kind === "text" || kind === "code" || kind === "json") {
    return <RawTextEmbed url={url} />;
  }
  // Office formats — render server-extracted structure as HTML.
  if (kind === "docx") return <DocxView pages={pages} loading={pagesLoading} />;
  if (kind === "xlsx") return <XlsxView pages={pages} loading={pagesLoading} />;
  if (kind === "pptx") return <PptxView pages={pages} loading={pagesLoading} />;

  // Truly unknown — last-resort download.
  return (
    <div className="flex h-full items-center justify-center p-8 text-center">
      <div className="max-w-sm">
        <FileText size={28} className="mx-auto mb-3 text-ink-mute" />
        <p className="mb-4 text-xs text-ink-soft">
          No browser preview for this format. Download the original or check the Extracted tab.
        </p>
        <a
          href={url}
          download={material.name}
          className="inline-flex items-center gap-1 border border-ink px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-ink hover:text-accent"
        >
          <Download size={12} /> Download
        </a>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DOCX — paragraphs (one per page entry, with table-row entries inline)
// ---------------------------------------------------------------------------
function DocxView({ pages, loading }: { pages: string[] | null; loading: boolean }) {
  if (loading) return <Centered>Loading document…</Centered>;
  if (!pages || pages.length === 0) return <Centered>No content extracted.</Centered>;
  return (
    <ScrollArea className="h-full">
      <article className="vn-text mx-auto my-6 max-w-2xl bg-white px-8 py-10 shadow-editorial-soft">
        {pages.map((p, i) => {
          // Heuristic: table rows in our extractor have " | " separators
          // and look like `cell | cell | cell`. Render those as a row.
          const looksLikeRow = p.includes(" | ") && p.split(" | ").length >= 2;
          if (looksLikeRow) {
            return (
              <div
                key={i}
                className="grid border-b border-line-soft py-1.5"
                style={{
                  gridTemplateColumns: `repeat(${p.split(" | ").length}, minmax(0, 1fr))`,
                  gap: "0 1.25rem",
                }}
              >
                {p.split(" | ").map((c, j) => (
                  <span key={j} className="text-[14px] text-ink">
                    {c}
                  </span>
                ))}
              </div>
            );
          }
          return (
            <p key={i} className="mb-3 text-[15px] leading-relaxed text-ink">
              {p}
            </p>
          );
        })}
      </article>
    </ScrollArea>
  );
}

// ---------------------------------------------------------------------------
// XLSX — one tab per sheet, render rows as <table>
// ---------------------------------------------------------------------------
function XlsxView({ pages, loading }: { pages: string[] | null; loading: boolean }) {
  const [activeSheet, setActiveSheet] = useState(0);
  if (loading) return <Centered>Loading workbook…</Centered>;
  if (!pages || pages.length === 0) return <Centered>No content extracted.</Centered>;
  // Each page format: "# SheetName\n<TSV rows>"
  const sheets = pages.map((p) => parseSheet(p));
  const idx = Math.min(activeSheet, sheets.length - 1);
  const cur = sheets[idx]!;
  return (
    <div className="flex h-full flex-col">
      {sheets.length > 1 && (
        <div className="flex items-center gap-1 overflow-x-auto border-b border-line-soft bg-bg-soft px-3 py-1.5">
          {sheets.map((s, i) => (
            <button
              key={i}
              onClick={() => setActiveSheet(i)}
              className={cn(
                "shrink-0 border px-3 py-1 font-mono text-[11px]",
                i === idx
                  ? "border-ink bg-paper text-ink"
                  : "border-transparent bg-transparent text-ink-mute hover:text-ink",
              )}
            >
              {s.name || `Sheet ${i + 1}`}
            </button>
          ))}
        </div>
      )}
      <ScrollArea className="min-h-0 flex-1">
        <div className="p-4">
          {cur.rows.length === 0 ? (
            <p className="text-xs italic text-ink-mute">empty sheet</p>
          ) : (
            <table className="border-collapse bg-white shadow-editorial-soft">
              <tbody>
                {cur.rows.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td
                        key={ci}
                        className={cn(
                          "vn-text border border-line-soft px-3 py-1.5 align-top text-[13px]",
                          ri === 0 && "bg-bg-soft font-semibold",
                        )}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function parseSheet(page: string): { name: string; rows: string[][] } {
  const lines = page.split("\n");
  let name = "";
  let start = 0;
  if (lines[0]?.startsWith("# ")) {
    name = lines[0]!.slice(2).trim();
    start = 1;
  }
  const rows = lines
    .slice(start)
    .map((l) => l.split("\t"))
    .filter((r) => r.some((c) => c));
  return { name, rows };
}

// ---------------------------------------------------------------------------
// PPTX — one card per slide, with optional speaker notes section
// ---------------------------------------------------------------------------
function PptxView({ pages, loading }: { pages: string[] | null; loading: boolean }) {
  if (loading) return <Centered>Loading slides…</Centered>;
  if (!pages || pages.length === 0) return <Centered>No content extracted.</Centered>;
  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-3xl space-y-5 p-6">
        {pages.map((p, i) => {
          const lines = p.split("\n");
          // First non-empty line is the slide title; remaining are body.
          // `_notes:` line (anywhere) is split off and shown separately.
          const notesIdx = lines.findIndex((l) => l.startsWith("_notes:"));
          const notes =
            notesIdx >= 0
              ? lines
                  .slice(notesIdx)
                  .join("\n")
                  .replace(/^_notes:\s*/, "")
              : "";
          const contentLines = (notesIdx >= 0 ? lines.slice(0, notesIdx) : lines).filter((l) =>
            l.trim(),
          );
          const title = contentLines[0] ?? "";
          const body = contentLines.slice(1).join("\n");
          return (
            <article
              key={i}
              className="flex aspect-[16/10] flex-col border border-line bg-white p-6 shadow-editorial-soft"
            >
              <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-accent">
                Slide {i + 1}
              </div>
              {title && (
                <h2 className="vn-text mb-3 font-display text-xl font-semibold tracking-tight text-ink">
                  {title}
                </h2>
              )}
              <div className="vn-text flex-1 whitespace-pre-wrap text-[14px] leading-relaxed text-ink">
                {body}
              </div>
              {notes && (
                <div className="vn-text mt-4 border-t border-line-soft pt-3 text-[11px] italic text-ink-mute">
                  <span className="mr-2 font-mono text-[9.5px] uppercase tracking-widest">
                    notes
                  </span>
                  {notes}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </ScrollArea>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center gap-2 text-sm italic text-ink-mute">
      <Loader2 size={12} className="animate-spin" /> {children}
    </div>
  );
}

function RawTextEmbed({ url }: { url: string }) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (text === null && err === null) {
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(setText)
      .catch((e: Error) => setErr(e.message));
  }
  if (err) {
    return (
      <div className="p-6 text-sm text-danger">
        <AlertCircle size={14} className="mr-2 inline" />
        {err}
      </div>
    );
  }
  if (text === null) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm italic text-ink-mute">
        <Loader2 size={12} className="animate-spin" /> Loading…
      </div>
    );
  }
  return (
    <ScrollArea className="h-full">
      <pre className="vn-text whitespace-pre-wrap break-words p-5 font-sans text-[13px] leading-relaxed text-ink">
        {text}
      </pre>
    </ScrollArea>
  );
}

function ExtractedView({
  loading,
  error,
  chunks,
  fallbackText,
  nChars,
  nChunks,
}: {
  loading: boolean;
  error: string | null;
  chunks: string[];
  fallbackText: string;
  nChars: number;
  nChunks: number;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm italic text-ink-mute">
        <Loader2 size={12} className="animate-spin" /> Extracting text…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        <AlertCircle size={14} className="mr-2 inline" />
        {error}
      </div>
    );
  }
  if (chunks.length === 0 && !fallbackText) {
    return (
      <div className="p-6 text-sm italic text-ink-mute">
        Not indexed yet. Upload triggers indexing automatically; check the right panel for the
        indexing banner.
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-line-soft px-5 py-2 font-mono text-[10.5px] uppercase tracking-widest text-ink-mute">
        <span>{nChars.toLocaleString()} chars</span>
        <span className="opacity-50">·</span>
        <span>
          {nChunks > 0 ? `${nChunks} chunk${nChunks === 1 ? "" : "s"} indexed` : "not indexed yet"}
        </span>
        <span className="opacity-50">·</span>
        <span>what the chunker + embedder saw</span>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-5">
          {chunks.length > 0 ? (
            chunks.map((c, i) => (
              <div
                key={i}
                className="vn-text whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-4 py-3 text-[13px] leading-relaxed text-ink"
              >
                <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-widest text-accent">
                  chunk {i + 1}
                </div>
                {c}
              </div>
            ))
          ) : (
            <pre className="vn-text whitespace-pre-wrap break-words font-sans text-[13px] leading-relaxed text-ink">
              {fallbackText}
            </pre>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
