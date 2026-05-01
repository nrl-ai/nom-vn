import { useCallback, useEffect, useState } from "react";
import { Scissors, Play, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Segmented } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { VN_SAMPLES } from "../samples";
import { useToolRunner } from "../useToolRunner";
import { useSentenceTokenize, useWordTokenize } from "@/api/queries";
import type { WordFmt } from "@/api/types";

type Mode = "word" | "sentence";

const STORAGE_KEY = "nom:tool:tokenize";

interface Persisted {
  text: string;
  mode: Mode;
  fmt: WordFmt;
}

const DEFAULTS: Persisted = {
  text: "",
  mode: "word",
  fmt: "list",
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

export function TokenizePage() {
  const [{ text, mode, fmt }, setState] = useState<Persisted>(load);
  const word = useWordTokenize();
  const sent = useSentenceTokenize();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, mode, fmt }));
  }, [text, mode, fmt]);

  const setText = (t: string) => setState((s) => ({ ...s, text: t }));
  const setMode = (m: Mode) => setState((s) => ({ ...s, mode: m }));
  const setFmt = (f: WordFmt) => setState((s) => ({ ...s, fmt: f }));

  const pending = word.isPending || sent.isPending;
  const onRun = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    if (mode === "word") word.mutate({ text: trimmed, fmt });
    else sent.mutate(trimmed);
  }, [text, pending, mode, fmt, word, sent]);

  useToolRunner(onRun, !!text.trim() && !pending);

  const wordRes = word.data;
  const sentRes = sent.data;
  const errMsg = (mode === "word" ? word.error : sent.error)
    ? ((mode === "word" ? word.error : sent.error) as Error).message
    : null;
  useEffect(() => {
    if (errMsg) toast.error(`Tokenize failed: ${errMsg}`);
  }, [errMsg]);

  return (
    <ToolShell
      icon={Scissors}
      title="Tách từ / câu"
      subtitle="word + sentence segmentation"
      pending={pending}
      options={
        <>
          <OptionRow label="Mode">
            <Segmented<Mode>
              value={mode}
              onChange={setMode}
              options={[
                { value: "word", label: "Words" },
                { value: "sentence", label: "Sentences" },
              ]}
            />
          </OptionRow>
          {mode === "word" && (
            <OptionRow
              label="Format"
              hint={
                fmt === "list"
                  ? "Chips theo từ ghép (compound joined by space)"
                  : "Một chuỗi với gạch dưới giữa các âm tiết"
              }
            >
              <Segmented<WordFmt>
                value={fmt}
                onChange={setFmt}
                options={[
                  { value: "list", label: "List" },
                  { value: "text", label: "Underscored" },
                ]}
              />
            </OptionRow>
          )}
          <OptionRow label="Engine">
            <p className="font-mono text-[11px] text-ink-mute">
              nom.text.segment · pure stdlib · ~734k tok/s
            </p>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {mode === "word" && wordRes
              ? `${wordRes.n_tokens ?? 0} tokens · ${wordRes.n_compounds ?? 0} compounds`
              : mode === "sentence" && sentRes
                ? `${sentRes.n_sentences} sentences`
                : "Cmd/Ctrl + Enter to run"}
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
        rows={5}
        placeholder="Hợp đồng số 02 được lập tại Hà Nội. Bạn có khoẻ không?"
        samples={VN_SAMPLES.map((s) => ({ label: s.label, text: s.text }))}
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {mode === "word" && wordRes && (
        <Panel
          label="tokens"
          hint={wordRes.tokens ? `${wordRes.n_tokens ?? 0} tokens` : "underscored"}
          rightSlot={
            <CopyButton
              text={wordRes.tokens ? wordRes.tokens.join(" | ") : (wordRes.text ?? "")}
              label="tokens"
            />
          }
        >
          {wordRes.tokens ? (
            <div className="vn-text flex flex-wrap gap-1.5">
              {wordRes.tokens.map((t, i) => {
                const isCompound = t.includes(" ");
                return (
                  <span
                    key={i}
                    className={
                      "border px-2 py-0.5 font-mono text-xs " +
                      (isCompound
                        ? "border-accent bg-accent/10 text-accent-ink"
                        : "border-line bg-bg-soft text-ink")
                    }
                    title={isCompound ? "compound (multi-syllable)" : undefined}
                  >
                    {t}
                  </span>
                );
              })}
            </div>
          ) : (
            <pre className="vn-text whitespace-pre-wrap break-words font-mono text-sm text-ink">
              {wordRes.text}
            </pre>
          )}
        </Panel>
      )}

      {mode === "sentence" && sentRes && (
        <Panel
          label="sentences"
          hint={`${sentRes.n_sentences}`}
          rightSlot={<CopyButton text={sentRes.sentences.join("\n")} label="sentences" />}
        >
          <ol className="vn-text space-y-1.5 text-sm">
            {sentRes.sentences.map((s, i) => (
              <li key={i} className="flex gap-3">
                <span className="shrink-0 select-none font-mono text-[11px] text-ink-mute">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-ink">{s}</span>
              </li>
            ))}
          </ol>
        </Panel>
      )}

      {!wordRes && !sentRes && !errMsg && (
        <EmptyHint>
          Chọn chế độ <span className="font-mono text-ink">Words</span> hoặc
          <span className="mx-1 font-mono text-ink">Sentences</span>ở phải, rồi
          <span className="mx-1 font-mono text-ink">⌘/Ctrl + Enter</span>
          để chạy.
        </EmptyHint>
      )}
    </ToolShell>
  );
}
