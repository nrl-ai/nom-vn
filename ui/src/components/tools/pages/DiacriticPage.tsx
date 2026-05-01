import { useCallback, useEffect, useState } from "react";
import { Type, Play, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select, Segmented } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { DiffView } from "../DiffView";
import { VN_SAMPLES } from "../samples";
import { useToolRunner } from "../useToolRunner";
import { useDiacriticModels, useDiacriticRestore } from "@/api/queries";
import type { DiacriticBackend } from "@/api/types";

const STORAGE_KEY = "nom:tool:diacritic";

interface Persisted {
  text: string;
  backend: DiacriticBackend;
  modelId: string;
}

const DEFAULTS: Persisted = {
  text: "",
  backend: "rule",
  modelId: "nrl-ai/vn-diacritic-vit5-base",
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

export function DiacriticPage() {
  const [{ text, backend, modelId }, setState] = useState<Persisted>(load);
  const restore = useDiacriticRestore();
  const modelsQ = useDiacriticModels();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, backend, modelId }));
  }, [text, backend, modelId]);

  const setText = (t: string) => setState((s) => ({ ...s, text: t }));
  const setBackend = (b: DiacriticBackend) => setState((s) => ({ ...s, backend: b }));
  const setModelId = (m: string) => setState((s) => ({ ...s, modelId: m }));

  const onRun = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || restore.isPending) return;
    restore.mutate({
      text: trimmed,
      backend,
      modelId: backend === "hf" ? modelId : undefined,
    });
  }, [text, backend, modelId, restore]);

  useToolRunner(onRun, !!text.trim() && !restore.isPending);

  const result = restore.data;
  const errMsg = restore.error ? (restore.error as Error).message : null;
  useEffect(() => {
    if (errMsg) toast.error(`Diacritic restore failed: ${errMsg}`);
  }, [errMsg]);

  return (
    <ToolShell
      icon={Type}
      title="Khôi phục dấu tiếng Việt"
      subtitle="diacritic restore"
      pending={restore.isPending}
      options={
        <>
          <OptionRow
            label="Backend"
            hint={
              backend === "rule"
                ? "Bảng tra cứu, ~5 ms · không cần model"
                : backend === "hf"
                  ? "HF seq2seq, lần đầu mất 10–30s tải model"
                  : "Dùng LLM (qwen3:8b…) cấu hình trên server"
            }
          >
            <Segmented<DiacriticBackend>
              value={backend}
              onChange={setBackend}
              options={[
                { value: "rule", label: "Rule" },
                { value: "hf", label: "HF" },
                { value: "llm", label: "LLM" },
              ]}
            />
          </OptionRow>
          {backend === "hf" && (
            <OptionRow label="HF model" hint="safetensors · Apache 2.0">
              <Select
                value={modelId}
                onChange={setModelId}
                options={
                  (modelsQ.data?.models ?? []).map((m) => ({
                    value: m.id,
                    label: m.label,
                  })) as ReadonlyArray<{ value: string; label: string }>
                }
              />
            </OptionRow>
          )}
          <OptionRow label="Note">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Chỉ truyền văn bản đã bị mất dấu (hoặc một phần). Các từ đã có dấu sẽ giữ nguyên.
            </p>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {result
              ? `Backend: ${result.backend}${result.model_id ? ` · ${result.model_id}` : ""}`
              : "Cmd/Ctrl + Enter to run"}
          </span>
          <Button
            variant="accent"
            size="md"
            onClick={onRun}
            disabled={!text.trim() || restore.isPending}
          >
            {restore.isPending ? <Spinner /> : <Play size={14} />}
            Chạy
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={6}
        placeholder="Hop dong nay duoc lap ngay 14 thang 3 nam 2025…"
        samples={VN_SAMPLES.map((s) => ({
          label: s.label,
          text: s.asciiText ?? s.text,
        }))}
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? (
        <Panel
          label="restored"
          hint={`${result.restored.length} chars`}
          rightSlot={<CopyButton text={result.restored} label="restored" />}
        >
          <DiffView before={result.input} after={result.restored} />
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Nhập văn bản (đã mất dấu hoặc bị mất một phần), rồi bấm
            <span className="mx-1 font-mono text-ink">Chạy</span>
            hoặc
            <span className="mx-1 font-mono text-ink">⌘/Ctrl + Enter</span>
            để khôi phục dấu.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
