import { useCallback, useEffect, useMemo, useState } from "react";
import { Sigma, Play, AlertTriangle, Check, X as XIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { VN_SAMPLES } from "../samples";
import { useToolRunner } from "../useToolRunner";
import { useDetect, useNormalize } from "@/api/queries";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "nom:tool:normalize";

interface Persisted {
  text: string;
}

const DEFAULTS: Persisted = { text: "" };

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    return DEFAULTS;
  }
}

interface CodepointRow {
  index: number;
  ch: string;
  hex: string;
  name: string;
  changed: boolean;
}

function describe(s: string, comparedTo: string): CodepointRow[] {
  const arr = Array.from(s);
  const cmp = Array.from(comparedTo);
  return arr.map((ch, i) => ({
    index: i,
    ch,
    hex: ch.codePointAt(0)?.toString(16).toUpperCase().padStart(4, "0") ?? "",
    name: ch === " " ? "SPACE" : ch === "\n" ? "LF" : ch,
    changed: cmp[i] !== ch,
  }));
}

export function NormalizePage() {
  const [{ text }, setState] = useState<Persisted>(load);
  const normalize = useNormalize();
  const detect = useDetect();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ text }));
  }, [text]);

  const setText = (t: string) => setState({ text: t });

  const pending = normalize.isPending || detect.isPending;
  const onRun = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    normalize.mutate(trimmed);
    detect.mutate(trimmed);
  }, [text, pending, normalize, detect]);

  useToolRunner(onRun, !!text.trim() && !pending);

  const normRes = normalize.data;
  const detRes = detect.data;
  const errMsg =
    normalize.error || detect.error ? ((normalize.error ?? detect.error) as Error).message : null;
  useEffect(() => {
    if (errMsg) toast.error(`Normalize/detect failed: ${errMsg}`);
  }, [errMsg]);

  const rows = useMemo(() => {
    if (!normRes) return [] as CodepointRow[];
    return describe(normRes.input, normRes.nfc).slice(0, 200);
  }, [normRes]);

  return (
    <ToolShell
      icon={Sigma}
      title="Chuẩn hoá Unicode + nhận diện"
      subtitle="NFC normalize · detect VN"
      pending={pending}
      options={
        <>
          <OptionRow
            label="Vì sao cần NFC?"
            hint="Khác biệt NFD/NFC vô hình bằng mắt nhưng làm hỏng tokenizer."
          >
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Chuỗi <code className="bg-bg-soft px-1">cỏ</code> có thể là{" "}
              <code className="bg-bg-soft px-1">U+1ECF</code> đã hợp (NFC) hoặc hai codepoint{" "}
              <code className="bg-bg-soft px-1">o + U+0309</code> (NFD).
            </p>
          </OptionRow>
          <OptionRow label="Các phép chạy">
            <ul className="space-y-1 text-[11.5px] leading-snug text-ink-soft">
              <li>
                <strong>NFC normalize</strong> — chuẩn hoá Unicode về dạng đã hợp.
              </li>
              <li>
                <strong>text_normalize</strong> — NFC + chuẩn hoá dấu câu Latin.
              </li>
              <li>
                <strong>is_vietnamese</strong> — nhận diện đoạn văn tiếng Việt.
              </li>
              <li>
                <strong>has_diacritics</strong> — có ký tự dấu hay không.
              </li>
            </ul>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {normRes
              ? `${normRes.n_input_codepoints} → ${normRes.n_nfc_codepoints} codepoint`
              : "Bấm ⌘/Ctrl + Enter để chạy"}
          </span>
          <Button variant="accent" size="md" onClick={onRun} disabled={!text.trim() || pending}>
            {pending ? <Spinner /> : <Play size={14} />}
            Chạy
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={4}
        placeholder="Tôi yêu Việt Nam …"
        samples={VN_SAMPLES.map((s) => ({ label: s.label, text: s.text }))}
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {detRes && (
        <Panel label="nhận diện" hint={detRes.reason}>
          <div className="grid grid-cols-2 gap-3">
            <Flag label="is_vietnamese" value={detRes.is_vietnamese} />
            <Flag label="has_diacritics" value={detRes.has_diacritics} />
          </div>
        </Panel>
      )}

      {normRes && (
        <Panel
          label="chuẩn hoá"
          hint={
            normRes.is_nfc ? "Đầu vào đã ở dạng NFC" : "Đầu vào ở dạng NFD — đã chuyển sang NFC"
          }
          rightSlot={<CopyButton text={normRes.full_normalized} label="văn bản chuẩn hoá" />}
        >
          <div className="grid gap-3 lg:grid-cols-2">
            <div>
              <div className="section-mark mb-1">§ đầu vào</div>
              <pre className="vn-text whitespace-pre-wrap break-words border border-line bg-bg-soft p-2 font-mono text-xs text-ink">
                {normRes.input}
              </pre>
            </div>
            <div>
              <div className="section-mark mb-1">§ nfc</div>
              <pre className="vn-text whitespace-pre-wrap break-words border border-line bg-bg-soft p-2 font-mono text-xs text-ink">
                {normRes.nfc}
              </pre>
            </div>
          </div>
          {!normRes.is_nfc && rows.length > 0 && (
            <div className="mt-3">
              <div className="section-mark mb-1">§ codepoint (200 đầu)</div>
              <div className="flex flex-wrap gap-1 font-mono text-[11px]">
                {rows.map((r) => (
                  <span
                    key={r.index}
                    className={cn(
                      "inline-flex items-center gap-1 border px-1.5 py-0.5",
                      r.changed
                        ? "border-accent bg-accent/10 text-accent-ink"
                        : "border-line bg-paper text-ink-soft",
                    )}
                    title={`U+${r.hex}`}
                  >
                    <span className="text-ink">{r.name}</span>
                    <span className="text-ink-mute">{r.hex}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Panel>
      )}

      {!normRes && !detRes && !errMsg && (
        <EmptyHint>
          Bấm <span className="mx-1 font-mono text-ink">Chạy</span>
          (hoặc <span className="font-mono text-ink">⌘/Ctrl + Enter</span>) để xem kết quả NFC và
          nhận diện ngôn ngữ.
        </EmptyHint>
      )}
    </ToolShell>
  );
}

function Flag({ label, value }: { label: string; value: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border px-3 py-2",
        value ? "border-ok bg-ok/5" : "border-line bg-bg-soft",
      )}
    >
      <span className="font-mono text-[11px] uppercase tracking-widest text-ink-soft">{label}</span>
      <span
        className={cn(
          "inline-flex items-center gap-1 font-mono text-xs font-medium",
          value ? "text-ok" : "text-ink-mute",
        )}
      >
        {value ? <Check size={12} /> : <XIcon size={12} />}
        {value ? "true" : "false"}
      </span>
    </div>
  );
}
