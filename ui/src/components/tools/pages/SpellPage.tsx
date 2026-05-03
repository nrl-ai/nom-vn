import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileSearch, Play, SpellCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { DiffView } from "../DiffView";
import { useToolRunner } from "../useToolRunner";
import { useDiacriticRestore } from "@/api/queries";

const STORAGE_KEY = "nom:tool:spell";

interface Persisted {
  text: string;
  modelId: string;
}

// The published spell-correction checkpoints — strict supersets of
// diacritic. Picked tier is per `docs/recipes.md` (OOD numbers measured).
const MODEL_OPTIONS: ReadonlyArray<{
  value: string;
  label: string;
  hint: string;
}> = [
  {
    value: "nrl-ai/vn-spell-correction-base",
    label: "Base PyTorch (mặc định, OOD 79.62 %)",
    hint: "BARTpho-syllable-base · 900 MB · cần GPU + transformers",
  },
  {
    value: "nrl-ai/vn-spell-correction-small",
    label: "Small PyTorch (OOD 77.55 %)",
    hint: "115M · 530 MB · 3× nhanh hơn base",
  },
  {
    value: "nrl-ai/vn-spell-correction-base-onnx-int8",
    label: "Base ONNX int8 (CPU server, OOD 78.76 %)",
    hint: "438 MB · không phụ thuộc PyTorch",
  },
  {
    value: "nrl-ai/vn-spell-correction-small-onnx-int8",
    label: "Small ONNX int8 (edge, OOD 77.30 %)",
    hint: "307 MB · vừa cho mobile / browser",
  },
];

const DEFAULTS: Persisted = {
  text: "",
  modelId: "nrl-ai/vn-spell-correction-base",
};

const SAMPLES: ReadonlyArray<{ label: string; text: string }> = [
  {
    label: "Telex / mất dấu",
    text: "Toi yu Vit Nam, dat nuoc tuyet voi.",
  },
  {
    label: "OCR nhiễu",
    text: "Hop dong nay duoc lap ngya l4 thang 3 nam 2025.",
  },
  {
    label: "Mạng xã hội",
    text: "Mjnh thik nhac cua bn vai cha. Ko ngo lai hay vay.",
  },
  {
    label: "Mix dấu / không dấu",
    text: "Toi đa hoàn thanh bao cao quy 2 va gui cho quan ly.",
  },
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

export function SpellPage() {
  const initial = useMemo(load, []);
  const [text, setText] = useState(initial.text);
  const [modelId, setModelId] = useState(initial.modelId);
  const correct = useDiacriticRestore();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, modelId }));
    } catch {
      /* localStorage may be unavailable */
    }
  }, [text, modelId]);

  const onRun = useCallback(() => {
    const t = text.trim();
    if (!t || correct.isPending) return;
    correct.mutate(
      { text: t, backend: "hf", modelId },
      {
        onError: (err) => toast.error(`Sửa chính tả thất bại: ${(err as Error).message}`),
      },
    );
  }, [text, modelId, correct]);

  const canRun = !!text.trim() && !correct.isPending;
  useToolRunner(onRun, canRun);

  const result = correct.data;
  const errMsg = correct.error ? (correct.error as Error).message : null;
  const corrected = result?.restored ?? "";
  const inputChars = text.length;
  const outputChars = corrected.length;

  return (
    <ToolShell
      icon={SpellCheck}
      title="Kiểm tra chính tả"
      subtitle="telex · dấu · phương ngữ · teencode — xử lý cục bộ"
      pending={correct.isPending}
      options={
        <>
          <OptionRow label="Mô hình">
            <Select<string>
              value={modelId}
              onChange={setModelId}
              options={MODEL_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
            {(() => {
              const opt = MODEL_OPTIONS.find((o) => o.value === modelId);
              return opt ? (
                <p className="meta mt-1.5 normal-case tracking-normal">{opt.hint}</p>
              ) : null;
            })()}
          </OptionRow>

          <OptionRow label="Câu hỏi gợi ý" hint="bấm để thử">
            <ul className="space-y-1.5">
              {SAMPLES.map((s) => (
                <li key={s.label}>
                  <button
                    type="button"
                    onClick={() => setText(s.text)}
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
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-spell-grammar-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              So sánh ứng viên
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${inputChars} → ${outputChars} ký tự · ${result.model_id ?? modelId}`
              : !text.trim()
                ? "Nhập đoạn văn bản tiếng Việt rồi bấm Sửa"
                : "Sẵn sàng — bấm Sửa để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {correct.isPending ? <Spinner /> : <Play size={14} />}
            Sửa
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={5}
        placeholder="Dán đoạn văn bản tiếng Việt cần sửa chính tả vào đây…"
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
          hint={`${result.model_id ?? modelId}`}
          rightSlot={<CopyButton text={corrected} label="Sao chép" />}
        >
          <div className="space-y-3">
            <pre className="whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-sans text-sm text-ink">
              {corrected || "(không thay đổi)"}
            </pre>
            {text !== corrected && (
              <details>
                <summary className="cursor-pointer text-[12px] text-ink-soft hover:text-ink">
                  Xem khác biệt từng từ
                </summary>
                <div className="mt-2">
                  <DiffView before={text} after={corrected} />
                </div>
              </details>
            )}
          </div>
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Nhập đoạn văn bản, sau đó bấm <strong>Sửa</strong> (Cmd/Ctrl+Enter). Mô hình xử lý cả
            khôi phục dấu, lỗi telex, OCR và teencode trong cùng một bước.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
