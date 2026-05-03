import { cn } from "@/lib/utils";
import { TASKS, type TaskKey } from "./tasks";

interface Props {
  active: TaskKey;
  onSelect: (k: TaskKey) => void;
}

export function TaskNav({ active, onSelect }: Props) {
  return (
    <nav className="flex h-full flex-col bg-bg" aria-label="Playground tasks">
      <div className="shrink-0 border-b border-line px-3 py-2">
        <h3 className="font-display text-sm font-semibold tracking-tight text-ink">
          Bảng điều khiển
        </h3>
        <span className="section-mark mt-0.5 block">§ công cụ</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 py-1.5">
        {(["rag", "text", "dev"] as const).map((cat) => (
          <div key={cat} className="mb-3 last:mb-0">
            <div className="meta px-2 pb-0.5 pt-1.5 uppercase tracking-widest">
              {cat === "rag" ? "ứng dụng" : cat === "text" ? "công cụ văn bản" : "lập trình"}
            </div>
            <ul>
              {TASKS.filter((t) => t.category === cat).map((t) => (
                <li key={t.key}>
                  <button
                    type="button"
                    onClick={() => onSelect(t.key)}
                    aria-current={active === t.key ? "page" : undefined}
                    className={cn(
                      "relative flex w-full items-center gap-2 border-l-2 px-2.5 py-1.5 text-left transition-colors",
                      active === t.key
                        ? "border-l-accent bg-accent-wash"
                        : "border-l-transparent hover:bg-bg-soft",
                    )}
                  >
                    <t.icon
                      size={13}
                      className={cn("shrink-0", active === t.key ? "text-accent" : "text-ink-mute")}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          "vn-text block truncate text-[13px] leading-tight",
                          active === t.key ? "font-semibold text-ink" : "font-medium text-ink-soft",
                        )}
                      >
                        {t.label}
                      </span>
                      <span className="meta block truncate normal-case tracking-normal">
                        {t.blurb}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="meta shrink-0 border-t border-line px-3 py-2 uppercase tracking-widest">
        chạy cục bộ · mã nguồn mở
      </div>
    </nav>
  );
}
