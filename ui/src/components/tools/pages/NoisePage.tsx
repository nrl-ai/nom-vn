import { useCallback, useEffect, useState } from "react";
import { Beaker, Play, AlertTriangle, Dice5 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select, NumberField } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { DiffView } from "../DiffView";
import { VN_SAMPLES } from "../samples";
import { useToolRunner } from "../useToolRunner";
import { useNoiseApply, useNoisePresets } from "@/api/queries";
import type { NoisePreset } from "@/api/types";

const STORAGE_KEY = "nom:tool:noise";

interface Persisted {
  text: string;
  preset: NoisePreset;
  seed: number;
}

const DEFAULTS: Persisted = {
  text: "",
  preset: "light",
  seed: 42,
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

export function NoisePage() {
  const [{ text, preset, seed }, setState] = useState<Persisted>(load);
  const noise = useNoiseApply();
  const presetsQ = useNoisePresets();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, preset, seed }));
  }, [text, preset, seed]);

  const setText = (t: string) => setState((s) => ({ ...s, text: t }));
  const setPreset = (p: NoisePreset) => setState((s) => ({ ...s, preset: p }));
  const setSeed = (n: number) => setState((s) => ({ ...s, seed: n }));

  const onRun = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || noise.isPending) return;
    noise.mutate({ text: trimmed, preset, seed });
  }, [text, noise, preset, seed]);

  useToolRunner(onRun, !!text.trim() && !noise.isPending);

  const reroll = () => {
    setSeed(Math.floor(Math.random() * 100000));
  };

  const result = noise.data;
  const errMsg = noise.error ? (noise.error as Error).message : null;
  useEffect(() => {
    if (errMsg) toast.error(`Noise apply failed: ${errMsg}`);
  }, [errMsg]);
  const presetOpts = presetsQ.data?.presets ?? [];

  return (
    <ToolShell
      icon={Beaker}
      title="Sinh nhiễu cho training"
      subtitle="reproducible noise generator"
      pending={noise.isPending}
      options={
        <>
          <OptionRow label="Kiểu nhiễu" hint="Mỗi kiểu là một phân phối lỗi đã được hiệu chỉnh.">
            <Select<NoisePreset>
              value={preset}
              onChange={setPreset}
              options={
                presetOpts.length
                  ? (presetOpts.map((p) => ({
                      value: p.id,
                      label: p.label,
                    })) as ReadonlyArray<{ value: NoisePreset; label: string }>)
                  : ([
                      { value: "light", label: "Light" },
                      { value: "heavy", label: "Heavy" },
                      { value: "ocr_realistic", label: "OCR realistic" },
                    ] as const)
              }
            />
          </OptionRow>
          <OptionRow
            label="Seed"
            hint="Cùng văn bản + cùng kiểu + cùng seed → cùng kết quả. Bảo đảm tái hiện được."
          >
            <div className="flex items-center gap-1">
              <NumberField value={seed} onChange={setSeed} min={0} className="flex-1" />
              <Button
                variant="ghost"
                size="sm"
                onClick={reroll}
                aria-label="Lấy seed ngẫu nhiên"
                className="h-9 w-9 p-0"
                title="Seed ngẫu nhiên"
              >
                <Dice5 size={14} />
              </Button>
            </div>
          </OptionRow>
          <OptionRow label="Mục đích">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Tạo cặp <code className="bg-bg-soft px-1">noisy → clean</code> để fine-tune mô hình
              khôi phục dấu hoặc sửa lỗi chính tả.
            </p>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {result ? `kiểu=${result.preset} · seed=${result.seed}` : "Bấm ⌘/Ctrl + Enter để chạy"}
          </span>
          <Button
            variant="accent"
            size="md"
            onClick={onRun}
            disabled={!text.trim() || noise.isPending}
          >
            {noise.isPending ? <Spinner /> : <Play size={14} />}
            Sinh nhiễu
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={5}
        placeholder="Tôi yêu Việt Nam, đất nước tuyệt vời…"
        samples={VN_SAMPLES.map((s) => ({ label: s.label, text: s.text }))}
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? (
        <Panel
          label="văn bản đã nhiễu"
          hint={`${result.noisy.length} ký tự`}
          rightSlot={<CopyButton text={result.noisy} label="văn bản đã nhiễu" />}
        >
          <DiffView before={result.input} after={result.noisy} />
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Chọn kiểu nhiễu và seed, rồi bấm
            <span className="mx-1 font-mono text-ink">⌘/Ctrl + Enter</span>
            để sinh ra phiên bản nhiễu (dùng cho cặp dữ liệu{" "}
            <code className="bg-bg-soft px-1">noisy → clean</code> khi fine-tune mô hình).
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
