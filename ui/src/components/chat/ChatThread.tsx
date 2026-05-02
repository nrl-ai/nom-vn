import { useEffect, useRef, useState } from "react";
import { Sparkles, Trash2, SlidersHorizontal, X } from "lucide-react";
import { Message } from "./Message";
import { Composer } from "./Composer";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAsk } from "@/api/queries";
import { useChatHistory } from "@/lib/storage";
import type { ChatMessage } from "@/api/types";

const TOP_K_KEY = "nom:chat:top-k";

function loadTopK(): number {
  try {
    const raw = localStorage.getItem(TOP_K_KEY);
    if (!raw) return 5;
    const n = Number(raw);
    return Number.isFinite(n) && n >= 1 && n <= 20 ? n : 5;
  } catch {
    return 5;
  }
}

interface Props {
  spaceId: string | null;
  spaceName: string | null;
  hasMaterials: boolean;
}

const SUGGESTED_VN = [
  "Tóm tắt nội dung chính của các tài liệu",
  "Liệt kê các điều khoản quan trọng",
  "Có những con số / mốc thời gian nào đáng chú ý?",
];

export function ChatThread({ spaceId, spaceName, hasMaterials }: Props) {
  const { messages, append, update, clear } = useChatHistory(spaceId);
  const ask = useAsk(spaceId);
  const [draft, setDraft] = useState("");
  const [topK, setTopK] = useState<number>(loadTopK);
  const [showOptions, setShowOptions] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem(TOP_K_KEY, String(topK));
    } catch {
      /* localStorage may be unavailable — best-effort */
    }
  }, [topK]);

  // Esc closes the options panel — common UX expectation for inline popovers.
  useEffect(() => {
    if (!showOptions) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowOptions(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [showOptions]);

  // Always scroll to bottom on new messages.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  if (!spaceId) {
    return <NoSpaceState />;
  }

  const send = async (text?: string) => {
    const q = (text ?? draft).trim();
    if (!q || ask.isPending) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: q,
      ts: Date.now() / 1000,
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: "",
      ts: Date.now() / 1000,
      pending: true,
    };
    append(userMsg);
    append(assistantMsg);
    setDraft("");

    try {
      const ans = await ask.mutateAsync({ question: q, topK });
      update(assistantMsg.id, {
        text: ans.text,
        citations: ans.citations,
        n_retrieved: ans.n_retrieved,
        pending: false,
      });
    } catch (err) {
      update(assistantMsg.id, {
        text: (err as Error).message,
        pending: false,
        error: true,
      });
    }
  };

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-4 py-3 lg:px-6">
        <div className="min-w-0 flex-1">
          <h2 className="vn-text truncate font-display text-base font-semibold tracking-tight text-ink">
            {spaceName ?? "—"}
          </h2>
          <span className="section-mark">§ chat · top_k={topK}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowOptions((v) => !v)}
            aria-label="Tuỳ chọn chat"
            className="text-ink-mute hover:text-ink"
          >
            {showOptions ? <X size={12} /> : <SlidersHorizontal size={12} />}
            <span className="hidden sm:inline">Tuỳ chọn</span>
          </Button>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm("Xoá toàn bộ lịch sử chat của không gian này?")) clear();
              }}
              className="text-ink-mute hover:text-danger"
            >
              <Trash2 size={12} /> Xoá
            </Button>
          )}
        </div>
      </div>
      {showOptions && (
        <div className="shrink-0 border-b border-line bg-bg-soft px-4 py-3 lg:px-6">
          <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-ink-mute">
            top_k truy hồi
          </label>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={20}
              step={1}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="flex-1 accent-[#c46a37]"
              aria-label="top_k"
            />
            <span className="w-8 text-right font-mono text-sm text-ink">{topK}</span>
          </div>
          <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
            Số chunk được truy hồi đưa vào prompt. Tăng → bao quát hơn nhưng chậm hơn, giảm → nhanh
            hơn nhưng có thể thiếu ngữ cảnh.
          </p>
        </div>
      )}

      <div className="min-h-0 flex-1">
        <ScrollArea className="h-full">
          <div ref={scrollRef} className="mx-auto max-w-3xl space-y-5 px-4 py-6 lg:px-6">
            {messages.length === 0 && (
              <EmptyChatState hasMaterials={hasMaterials} onSuggest={(q) => send(q)} />
            )}
            {messages.map((m) => (
              <Message key={m.id} message={m} />
            ))}
          </div>
        </ScrollArea>
      </div>

      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={() => send()}
        disabled={!hasMaterials}
        pending={ask.isPending}
        placeholder={
          hasMaterials
            ? "Đặt câu hỏi… (Enter để gửi, Shift+Enter để xuống dòng)"
            : "Tải tài liệu lên để bắt đầu hỏi đáp…"
        }
      />
    </div>
  );
}

function NoSpaceState() {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-sm text-center">
        <div className="mb-4 font-serif text-6xl text-accent">喃</div>
        <h2 className="mb-2 font-display text-2xl font-semibold tracking-tight">
          Chào mừng đến với Nôm
        </h2>
        <p className="mb-1 text-sm text-ink-soft">
          Tạo một <strong>không gian</strong> ở cột trái, tải tài liệu tiếng Việt lên, rồi đặt câu
          hỏi.
        </p>
        <p className="mt-4 font-mono text-xs text-ink-mute">
          chạy cục bộ · mã nguồn mở · dữ liệu không rời máy của bạn
        </p>
      </div>
    </div>
  );
}

function EmptyChatState({
  hasMaterials,
  onSuggest,
}: {
  hasMaterials: boolean;
  onSuggest: (q: string) => void;
}) {
  if (!hasMaterials) {
    return (
      <div className="py-16 text-center">
        <Sparkles size={28} className="mx-auto mb-4 text-accent" />
        <h3 className="mb-1 font-display text-lg font-semibold">Chưa có tài liệu</h3>
        <p className="text-sm text-ink-soft">
          Tải lên file PDF, ảnh, hoặc văn bản ở cột phải. Sau đó quay lại đây để hỏi.
        </p>
      </div>
    );
  }
  return (
    <div className="py-12">
      <div className="mb-6 text-center">
        <Sparkles size={24} className="mx-auto mb-3 text-accent" />
        <h3 className="mb-1 font-display text-lg font-semibold tracking-tight">
          Bạn muốn biết điều gì?
        </h3>
        <p className="font-mono text-xs uppercase tracking-widest text-ink-mute">câu hỏi gợi ý</p>
      </div>
      <div className="mx-auto flex max-w-md flex-col gap-2">
        {SUGGESTED_VN.map((q) => (
          <button
            key={q}
            onClick={() => onSuggest(q)}
            className="vn-text border border-line bg-paper px-4 py-2.5 text-left text-sm transition-all hover:border-ink hover:shadow-editorial-soft"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
