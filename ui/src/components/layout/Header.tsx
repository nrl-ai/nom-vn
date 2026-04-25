import { Cpu } from "lucide-react";

// Top bar — brand mark, tagline, runtime context (model name).
// The chữ Nôm 喃 is the project's character; keep it visible.

interface HeaderProps {
  modelName?: string;
  onHome?: () => void;
}

export function Header({ modelName, onHome }: HeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-ink bg-bg px-6">
      <button
        onClick={onHome}
        className="group flex items-baseline gap-3"
        title="Back to welcome"
        aria-label="Home"
      >
        <h1 className="font-display text-2xl font-bold leading-none tracking-tight text-ink transition-colors group-hover:text-accent">
          Nôm <span className="font-serif font-normal text-accent">喃</span>
        </h1>
        <span className="section-mark hidden transition-colors group-hover:text-ink sm:inline">
          công cụ ai tiếng việt
        </span>
      </button>
      <div className="flex items-center gap-4 text-xs text-ink-soft">
        {modelName && (
          <span className="hidden items-center gap-1.5 font-mono sm:inline-flex">
            <Cpu size={12} className="text-accent" />
            {modelName}
          </span>
        )}
        <span className="font-mono opacity-60">v0.2.2</span>
      </div>
    </header>
  );
}
