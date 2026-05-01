import { useCallback, useEffect, useState } from "react";
import { Eraser, Play, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { VN_SAMPLES } from "../samples";
import { useToolRunner } from "../useToolRunner";
import { useDiacriticStrip } from "@/api/queries";

const STORAGE_KEY = "nom:tool:strip";

export function StripPage() {
  const [text, setText] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const strip = useDiacriticStrip();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, text);
    } catch {
      /* quota exceeded — ignore, the input is ephemeral */
    }
  }, [text]);

  const onRun = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || strip.isPending) return;
    strip.mutate(trimmed);
  }, [text, strip]);

  useToolRunner(onRun, !!text.trim() && !strip.isPending);

  const result = strip.data;
  const errMsg = strip.error ? (strip.error as Error).message : null;
  useEffect(() => {
    if (errMsg) toast.error(`Strip failed: ${errMsg}`);
  }, [errMsg]);

  return (
    <ToolShell
      icon={Eraser}
      title="Bỏ dấu"
      subtitle="strip diacritics → ASCII"
      pending={strip.isPending}
      options={
        <>
          <OptionRow label="Use cases" hint="URL slugs, search keys, hệ thống legacy chỉ ASCII.">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              <strong>đ</strong> → <strong>d</strong>, dấu kết hợp → bỏ.
            </p>
          </OptionRow>
          <OptionRow label="API">
            <code className="block bg-bg-soft px-2 py-1 font-mono text-[11px]">
              nom.text.strip_diacritics
            </code>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {result ? `${result.stripped.length} chars` : "Cmd/Ctrl + Enter to run"}
          </span>
          <Button
            variant="accent"
            size="md"
            onClick={onRun}
            disabled={!text.trim() || strip.isPending}
          >
            {strip.isPending ? <Spinner /> : <Play size={14} />}
            Chạy
          </Button>
        </div>
      }
    >
      <TextInput
        value={text}
        onChange={setText}
        rows={5}
        placeholder="Hợp đồng số 02/HĐ/2025 …"
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
          label="stripped"
          hint="ASCII approximation"
          rightSlot={<CopyButton text={result.stripped} label="stripped" />}
        >
          <pre className="vn-text whitespace-pre-wrap break-words font-mono text-sm text-ink">
            {result.stripped}
          </pre>
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Bấm <span className="mx-1 font-mono text-ink">Chạy</span>
            (hoặc <span className="font-mono text-ink">⌘/Ctrl + Enter</span>) để xem phiên bản
            ASCII.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
