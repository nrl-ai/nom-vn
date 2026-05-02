import { cn } from "@/lib/utils";
import { TASKS, type TaskKey } from "./tasks";

interface Props {
  active: TaskKey;
  onSelect: (k: TaskKey) => void;
}

export function TaskNav({ active, onSelect }: Props) {
  return (
    <nav className="flex h-full flex-col bg-bg" aria-label="Playground tasks">
      <div className="shrink-0 border-b border-line px-4 py-3">
        <h3 className="font-display text-sm font-semibold tracking-tight text-ink">Playground</h3>
        <span className="section-mark mt-0.5 block">§ tools</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {(["rag", "text", "dev"] as const).map((cat) => (
          <div key={cat} className="mb-4 last:mb-0">
            <div className="px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-ink-mute">
              {cat === "rag" ? "documents" : cat === "text" ? "text tools" : "developer"}
            </div>
            <ul className="space-y-0.5">
              {TASKS.filter((t) => t.category === cat).map((t) => (
                <li key={t.key}>
                  <button
                    type="button"
                    onClick={() => onSelect(t.key)}
                    aria-current={active === t.key ? "page" : undefined}
                    className={cn(
                      "flex w-full items-start gap-2 border border-transparent px-2.5 py-2 text-left transition-colors",
                      active === t.key
                        ? "border-ink bg-paper shadow-editorial-soft"
                        : "hover:border-line hover:bg-paper",
                    )}
                  >
                    <t.icon
                      size={14}
                      className={cn(
                        "mt-0.5 shrink-0",
                        active === t.key ? "text-accent" : "text-ink-soft",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="vn-text block truncate text-sm font-medium text-ink">
                        {t.label}
                      </span>
                      <span className="block truncate font-mono text-[11px] text-ink-mute">
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
      <div className="shrink-0 border-t border-line px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-ink-mute">
        local-first · open-source
      </div>
    </nav>
  );
}
