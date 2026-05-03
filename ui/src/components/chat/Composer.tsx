import { useEffect, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  pending?: boolean;
  placeholder?: string;
}

// Fixed-position composer at the bottom of the chat pane.
// - Shift+Enter inserts newline; Enter or Cmd/Ctrl+Enter sends.
// - Auto-grows up to ~6 lines, then scrolls.
// - Esc clears the draft.
export function Composer({ value, onChange, onSubmit, disabled, pending, placeholder }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [value]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    } else if (e.key === "Escape") {
      onChange("");
    }
  };

  return (
    <div className="shrink-0 border-t border-line bg-bg px-4 py-2.5 lg:px-5">
      <div className="flex items-end gap-2">
        <Textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          disabled={disabled}
          placeholder={placeholder ?? "Đặt câu hỏi… (Enter để gửi, Shift+Enter xuống dòng)"}
          className="max-h-[180px] min-h-[36px] flex-1"
        />
        <Button
          variant="accent"
          size="md"
          onClick={onSubmit}
          disabled={disabled || !value.trim() || pending}
          className="h-9 shrink-0"
          aria-label="Gửi"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          <span className="hidden sm:inline">Gửi</span>
        </Button>
      </div>
      <div className="meta mt-1 flex items-center gap-1.5 uppercase tracking-widest">
        <span className="kbd normal-case tracking-normal">Enter</span>
        <span>gửi</span>
        <span className="text-ink-mute/50">·</span>
        <span className="kbd normal-case tracking-normal">⇧ Enter</span>
        <span>xuống dòng</span>
        <span className="text-ink-mute/50">·</span>
        <span className="kbd normal-case tracking-normal">Esc</span>
        <span>xoá</span>
      </div>
    </div>
  );
}
