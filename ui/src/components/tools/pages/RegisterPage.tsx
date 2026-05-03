import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileSearch, Layers, Play } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { useToolRunner } from "../useToolRunner";
import { useClassifyRegister } from "@/api/queries";
import type { RegisterBackend, RegisterLabel, RegisterRes } from "@/api/types";

const STORAGE_KEY = "nom:tool:register";

interface PersistedState {
  backend: RegisterBackend;
}

const DEFAULT_STATE: PersistedState = { backend: "lexicon" };

const BACKEND_OPTIONS: ReadonlyArray<{ value: RegisterBackend; label: string }> = [
  { value: "lexicon", label: "Heuristic — chạy ngay (chính xác ~70-80 %)" },
  { value: "phobert", label: "PhoBERT-base — cần model_id (chính xác > 85 %)" },
];

// Display order matches the corpus assembly: formal → business →
// conversational → literary, so users see registers in the same order
// as the survey + training-script README.
const LABEL_ORDER: ReadonlyArray<RegisterLabel> = [
  "formal",
  "business",
  "conversational",
  "literary",
];

const LABEL_VN: Record<RegisterLabel, string> = {
  formal: "Trang trọng",
  business: "Kinh doanh / báo chí",
  conversational: "Hội thoại",
  literary: "Văn học",
};

const LABEL_HINT: Record<RegisterLabel, string> = {
  formal: "UDHR, công văn, văn bản pháp luật",
  business: "Báo cáo, tin tức, bách khoa",
  conversational: "Diễn đàn, mạng xã hội, hội thoại",
  literary: "Truyện cổ, văn chương cổ điển",
};

const SAMPLES: ReadonlyArray<{ label: RegisterLabel; text: string }> = [
  {
    label: "formal",
    text: "Căn cứ Luật ban hành văn bản quy phạm pháp luật, Bộ Tư pháp trân trọng kính gửi quý cơ quan thông tư có hiệu lực từ ngày 01/01/2026.",
  },
  {
    label: "business",
    text: "Doanh thu công ty trong quý 2 năm 2026 đạt 1,2 tỷ đồng, tăng 18% so với cùng kỳ năm trước. Cổ phiếu lên 12% sau báo cáo.",
  },
  {
    label: "conversational",
    text: "Mình thấy chỗ đó ngon lắm nha, bạn ơi đi thử đi vậy nhé!",
  },
  {
    label: "literary",
    text: "Thuở xưa, chàng cùng nàng dạo bước dưới bóng nguyệt, lệ rơi giữa non sông bốn bể.",
  },
];

function loadPersisted(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    return { ...DEFAULT_STATE, ...(JSON.parse(raw) as Partial<PersistedState>) };
  } catch {
    return DEFAULT_STATE;
  }
}

export function RegisterPage() {
  const initial = useMemo(loadPersisted, []);
  const [text, setText] = useState("");
  const [backend, setBackend] = useState<RegisterBackend>(initial.backend);
  const classify = useClassifyRegister();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ backend }));
    } catch {
      /* localStorage may be unavailable */
    }
  }, [backend]);

  const onRun = useCallback(() => {
    const t = text.trim();
    if (!t || classify.isPending) return;
    classify.mutate(
      { text: t, backend },
      {
        onError: (err) => {
          toast.error(`Phân loại thất bại: ${(err as Error).message}`);
        },
      },
    );
  }, [text, backend, classify]);

  const canRun = !!text.trim() && !classify.isPending;
  useToolRunner(onRun, canRun);

  const result = classify.data;
  const errMsg = classify.error ? (classify.error as Error).message : null;

  return (
    <ToolShell
      icon={Layers}
      title="Phân loại văn phong"
      subtitle="router 4 lớp · trang trọng / kinh doanh / hội thoại / văn học"
      pending={classify.isPending}
      options={
        <>
          <OptionRow label="Backend">
            <Select<RegisterBackend>
              value={backend}
              onChange={setBackend}
              options={BACKEND_OPTIONS}
            />
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
                    <span className="meta uppercase tracking-widest text-accent">
                      {LABEL_VN[s.label]}
                    </span>
                    <span className="mt-0.5 block truncate text-ink">{s.text}</span>
                  </button>
                </li>
              ))}
            </ul>
          </OptionRow>

          <OptionRow label="Khảo cứu">
            <a
              className="inline-flex items-center gap-1 text-[12px] text-accent underline hover:text-ink"
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-register-classifier-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              Tổng hợp mô hình + dataset
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${result.model} · ${LABEL_VN[result.label]} (${(result.score * 100).toFixed(1)}%)`
              : !text.trim()
                ? "Nhập một đoạn văn bản tiếng Việt rồi bấm Phân loại"
                : "Sẵn sàng — bấm Phân loại để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {classify.isPending ? <Spinner /> : <Play size={14} />}
            Phân loại
          </Button>
        </div>
      }
    >
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        placeholder="Dán hoặc gõ đoạn văn bản tiếng Việt vào đây…"
      />

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? <ResultPanel result={result} /> : !errMsg && <EmptyHintBlock backend={backend} />}
    </ToolShell>
  );
}

function ResultPanel({ result }: { result: RegisterRes }) {
  return (
    <Panel
      label="Kết quả"
      hint={`${result.backend} · ${result.model}`}
      rightSlot={
        <span className="meta-strong border border-accent bg-accent-wash px-2 py-0.5 text-[11px] text-ink">
          {LABEL_VN[result.label]} · {(result.score * 100).toFixed(1)}%
        </span>
      }
    >
      <ul className="space-y-1.5">
        {LABEL_ORDER.map((lbl) => {
          const p = result.distribution[lbl] ?? 0;
          const pct = p * 100;
          const isTop = lbl === result.label;
          return (
            <li
              key={lbl}
              className={cn(
                "border-l-2 px-3 py-1.5",
                isTop ? "border-accent bg-accent-wash" : "border-line bg-paper",
              )}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={cn(
                    "vn-text text-[13px]",
                    isTop ? "font-semibold text-ink" : "font-medium text-ink-soft",
                  )}
                >
                  {LABEL_VN[lbl]}
                </span>
                <span className="meta-strong">{pct.toFixed(1)}%</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden bg-bg-soft">
                  <div
                    className={cn("h-full transition-all", isTop ? "bg-accent" : "bg-ink/40")}
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
              </div>
              <div className="meta mt-0.5">{LABEL_HINT[lbl]}</div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function EmptyHintBlock({ backend }: { backend: RegisterBackend }) {
  if (backend === "phobert") {
    return (
      <EmptyHint>
        Backend PhoBERT cần <code className="font-mono text-ink">model_id</code> trỏ tới HF repo có
        4-class head. Mặc định OSS chưa publish — chạy{" "}
        <code className="font-mono text-ink">training/register/train.py</code> để tạo, hoặc chuyển
        sang backend Heuristic để dùng ngay.
      </EmptyHint>
    );
  }
  return (
    <EmptyHint>
      Nhập một đoạn văn bản tiếng Việt rồi bấm <strong>Phân loại</strong> (Cmd/Ctrl+Enter).
      Heuristic chạy cục bộ ngay, không cần tải mô hình.
    </EmptyHint>
  );
}
