import { useCallback, useEffect, useMemo, useState } from "react";
import { AlignLeft, AlertTriangle, FileSearch, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CopyButton } from "../CopyButton";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { TextInput } from "../TextInput";
import { useToolRunner } from "../useToolRunner";
import { useSummarize } from "@/api/queries";
import type { SummarizeRegister } from "@/api/types";

const STORAGE_KEY = "nom:tool:summarize";

interface Persisted {
  text: string;
  register: SummarizeRegister;
  maxLength: number;
}

const DEFAULTS: Persisted = { text: "", register: "news", maxLength: 256 };

const REGISTER_OPTIONS: ReadonlyArray<{ value: SummarizeRegister; label: string }> = [
  { value: "news", label: "Báo / tin tức (vietnews)" },
  { value: "legal", label: "Hợp đồng / pháp luật" },
  { value: "dialogue", label: "Hội thoại / transcript" },
];

const LENGTH_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "96", label: "Ngắn — ~96 token" },
  { value: "160", label: "Trung — ~160 token" },
  { value: "256", label: "Dài — ~256 token (mặc định)" },
  { value: "384", label: "Rất dài — ~384 token" },
];

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    return DEFAULTS;
  }
}

export function SummarizePage() {
  const initial = useMemo(load, []);
  const [text, setText] = useState(initial.text);
  const [register, setRegister] = useState<SummarizeRegister>(initial.register);
  const [maxLength, setMaxLength] = useState<number>(initial.maxLength);
  const summarize = useSummarize();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, register, maxLength }));
    } catch {
      /* localStorage may be unavailable */
    }
  }, [text, register, maxLength]);

  const onRun = useCallback(() => {
    const t = text.trim();
    if (!t || summarize.isPending) return;
    summarize.mutate(
      { text: t, register, maxLength },
      { onError: (err) => toast.error(`Tóm tắt thất bại: ${(err as Error).message}`) },
    );
  }, [text, register, maxLength, summarize]);

  const canRun = !!text.trim() && !summarize.isPending;
  useToolRunner(onRun, canRun);

  const result = summarize.data;
  const errMsg = summarize.error ? (summarize.error as Error).message : null;

  return (
    <ToolShell
      icon={AlignLeft}
      title="Tóm tắt"
      subtitle="ViT5-large · báo / hợp đồng / hội thoại"
      pending={summarize.isPending}
      options={
        <>
          <OptionRow label="Văn phong" hint="prefix prompt theo register">
            <Select<SummarizeRegister>
              value={register}
              onChange={setRegister}
              options={REGISTER_OPTIONS}
            />
          </OptionRow>

          <OptionRow label="Độ dài tóm tắt">
            <Select<string>
              value={String(maxLength)}
              onChange={(v) => setMaxLength(Number(v))}
              options={LENGTH_OPTIONS}
            />
          </OptionRow>

          <OptionRow label="Mô hình">
            <code className="block bg-bg-soft px-2 py-1 font-mono text-[11px] text-ink">
              VietAI/vit5-large-vietnews
            </code>
            <p className="meta mt-1.5 normal-case tracking-normal">
              MIT · 866 M · 1024 ctx · ROUGE-1 63.4 vietnews
            </p>
          </OptionRow>

          <OptionRow label="Khảo cứu">
            <a
              className="inline-flex items-center gap-1 text-[12px] text-accent underline hover:text-ink"
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-summarization-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              So sánh ứng viên + ROUGE
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${result.n_chars_in} → ${result.n_chars_out} ký tự · ${result.model}`
              : !text.trim()
                ? "Dán đoạn văn rồi bấm Tóm tắt"
                : "Sẵn sàng — bấm Tóm tắt để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {summarize.isPending ? <Spinner /> : <Play size={14} />}
            Tóm tắt
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={8}
        placeholder="Dán đoạn văn bản tiếng Việt cần tóm tắt vào đây… (cap input ~1024 token, vượt sẽ tự cắt)"
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? (
        <Panel
          label="Tóm tắt"
          hint={`${result.model}${result.register ? ` · ${result.register}` : ""}`}
          rightSlot={<CopyButton text={result.summary} label="Sao chép" />}
        >
          <pre className="whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-sans text-sm text-ink">
            {result.summary || "(không sinh được tóm tắt)"}
          </pre>
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Dán văn bản tiếng Việt, chọn văn phong + độ dài, sau đó bấm <strong>Tóm tắt</strong>{" "}
            (Cmd/Ctrl+Enter). Lần đầu có thể mất 30-60 giây để tải mô hình.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
