import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileSearch, Play, Tags } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { TextInput } from "../TextInput";
import { useToolRunner } from "../useToolRunner";
import { useNERTag } from "@/api/queries";
import type { NERPreset } from "@/api/types";

const STORAGE_KEY = "nom:tool:ner";

interface Persisted {
  text: string;
  preset: NERPreset;
}

const DEFAULTS: Persisted = { text: "", preset: "standard" };

const PRESET_OPTIONS: ReadonlyArray<{ value: NERPreset; label: string }> = [
  { value: "standard", label: "Chuẩn — PER / ORG / LOC / DATE / MONEY" },
  { value: "legal", label: "Pháp lý — + LAW_REF / ID_VN / PHONE_VN" },
];

const SAMPLES: ReadonlyArray<{ label: string; text: string; preset: NERPreset }> = [
  {
    label: "Hoá đơn",
    preset: "standard",
    text: "Vietcombank chuyển 1.500.000 VND vào ngày 14/3/2025 cho FPT.",
  },
  {
    label: "Hợp đồng pháp lý",
    preset: "legal",
    text: "Theo Nghị định 13/2023/NĐ-CP và Điều 5 Luật An ninh mạng, ông Nguyễn Văn A (CMND 012345678, điện thoại 0912 345 678) cam kết thanh toán 1.500.000 VND vào 14/3/2025.",
  },
  {
    label: "Hợp đồng + Luật số",
    preset: "legal",
    text: "Căn cứ Luật số 50/2024/QH15 ban hành năm 2024, các bên thực hiện theo Khoản 2 Điều 5.",
  },
];

const LABEL_COLOR: Record<string, string> = {
  PER: "bg-blue-100 text-blue-900 border-blue-300",
  ORG: "bg-purple-100 text-purple-900 border-purple-300",
  LOC: "bg-green-100 text-green-900 border-green-300",
  MISC: "bg-gray-100 text-gray-900 border-gray-300",
  DATE: "bg-amber-100 text-amber-900 border-amber-300",
  MONEY: "bg-emerald-100 text-emerald-900 border-emerald-300",
  LAW_REF: "bg-accent-wash text-accent-ink border-accent",
  ID_VN: "bg-rose-100 text-rose-900 border-rose-300",
  PHONE_VN: "bg-sky-100 text-sky-900 border-sky-300",
};

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    return DEFAULTS;
  }
}

export function NerPage() {
  const initial = useMemo(load, []);
  const [text, setText] = useState(initial.text);
  const [preset, setPreset] = useState<NERPreset>(initial.preset);
  const ner = useNERTag();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, preset }));
    } catch {
      /* localStorage may be unavailable */
    }
  }, [text, preset]);

  const onRun = useCallback(() => {
    const t = text.trim();
    if (!t || ner.isPending) return;
    ner.mutate(
      { text: t, preset },
      { onError: (err) => toast.error(`Trích xuất thất bại: ${(err as Error).message}`) },
    );
  }, [text, preset, ner]);

  const canRun = !!text.trim() && !ner.isPending;
  useToolRunner(onRun, canRun);

  const result = ner.data;
  const errMsg = ner.error ? (ner.error as Error).message : null;

  return (
    <ToolShell
      icon={Tags}
      title="Trích xuất thực thể"
      subtitle="người · tổ chức · nơi chốn · điều luật · bên hợp đồng"
      pending={ner.isPending}
      options={
        <>
          <OptionRow label="Bộ thực thể">
            <Select<NERPreset> value={preset} onChange={setPreset} options={PRESET_OPTIONS} />
          </OptionRow>

          <OptionRow label="Câu hỏi gợi ý" hint="bấm để thử">
            <ul className="space-y-1.5">
              {SAMPLES.map((s) => (
                <li key={s.label}>
                  <button
                    type="button"
                    onClick={() => {
                      setText(s.text);
                      setPreset(s.preset);
                    }}
                    className="block w-full border border-line bg-paper px-2.5 py-1.5 text-left text-[12px] leading-snug text-ink-soft transition-colors hover:border-ink hover:text-ink"
                  >
                    <span className="meta uppercase tracking-widest text-accent">{s.label}</span>
                    <span className="mt-0.5 block truncate text-ink">{s.text}</span>
                  </button>
                </li>
              ))}
            </ul>
          </OptionRow>

          <OptionRow label="Khảo cứu">
            <a
              className="inline-flex items-center gap-1 text-[12px] text-accent underline hover:text-ink"
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-ner-legal-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              VN NER + LAW_REF khảo cứu
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${result.spans.length} thực thể · preset ${result.preset ?? preset}`
              : !text.trim()
                ? "Dán đoạn văn rồi bấm Trích"
                : "Sẵn sàng — bấm Trích để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {ner.isPending ? <Spinner /> : <Play size={14} />}
            Trích
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={5}
        placeholder="Dán đoạn văn bản tiếng Việt vào đây…"
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? (
        <Panel
          label="Kết quả"
          hint={`${result.spans.length} thực thể${result.preset ? ` · preset ${result.preset}` : ""}`}
        >
          {result.spans.length === 0 ? (
            <EmptyHint>Không tìm thấy thực thể nào trong đoạn văn này.</EmptyHint>
          ) : (
            <>
              <HighlightedText text={text} spans={result.spans} />
              <ul className="mt-3 space-y-1">
                {result.spans.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-2 border-l-2 border-line bg-paper px-3 py-1.5 text-[13px]"
                  >
                    <span
                      className={cn(
                        "shrink-0 border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest",
                        LABEL_COLOR[s.label] ?? "border-line bg-bg-soft text-ink-mute",
                      )}
                    >
                      {s.label}
                    </span>
                    <span className="vn-text text-ink">{s.text}</span>
                    <span className="meta ml-auto shrink-0 normal-case tracking-normal">
                      [{s.start}–{s.end}]
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Dán đoạn văn bản tiếng Việt, chọn bộ thực thể (Chuẩn / Pháp lý), sau đó bấm{" "}
            <strong>Trích</strong> (Cmd/Ctrl+Enter). Bộ "Pháp lý" mở rộng thêm LAW_REF (luật, điều,
            khoản), ID_VN (CMND/CCCD), PHONE_VN.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}

interface SpanLite {
  start: number;
  end: number;
  label: string;
}

function HighlightedText({ text, spans }: { text: string; spans: SpanLite[] }) {
  // Render text with spans highlighted inline. Spans come back sorted +
  // non-overlapping from the API, so a single pass slicing works.
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  const out: React.ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((s, i) => {
    if (cursor < s.start) out.push(<span key={`t-${i}`}>{text.slice(cursor, s.start)}</span>);
    out.push(
      <mark
        key={`s-${i}`}
        className={cn(
          "border px-0.5 py-px",
          LABEL_COLOR[s.label] ?? "border-line bg-bg-soft text-ink-mute",
        )}
        title={s.label}
      >
        {text.slice(s.start, s.end)}
      </mark>,
    );
    cursor = s.end;
  });
  if (cursor < text.length) out.push(<span key="tail">{text.slice(cursor)}</span>);
  return (
    <pre className="whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-sans text-sm leading-relaxed text-ink">
      {out}
    </pre>
  );
}
