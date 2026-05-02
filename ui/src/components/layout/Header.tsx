import { Cpu, Settings as SettingsIcon, BookOpen } from "lucide-react";

// Top bar — brand mark, tagline, runtime context (model name), top-right
// shortcuts (settings + API docs). The chữ Nôm 喃 is the project's
// character; keep it visible.

interface HeaderProps {
  modelName?: string;
  onHome?: () => void;
  /** Open the Settings task. */
  onSettings?: () => void;
  /** Open the API & Setup task. */
  onApi?: () => void;
}

export function Header({ modelName, onHome, onSettings, onApi }: HeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-ink bg-bg px-6">
      <button
        onClick={onHome}
        className="group flex items-baseline gap-3"
        title="Về trang chủ"
        aria-label="Trang chủ"
      >
        <h1 className="font-display text-2xl font-bold leading-none tracking-tight text-ink transition-colors group-hover:text-accent">
          Nôm <span className="font-serif font-normal text-accent">喃</span>
        </h1>
        <span className="section-mark hidden transition-colors group-hover:text-ink sm:inline">
          công cụ ai tiếng việt
        </span>
      </button>
      <div className="flex items-center gap-3 text-xs text-ink-soft">
        {modelName && (
          <span className="hidden items-center gap-1.5 font-mono sm:inline-flex">
            <Cpu size={12} className="text-accent" />
            {modelName}
          </span>
        )}
        <span className="hidden font-mono opacity-60 sm:inline">v0.2.31</span>
        {onApi && (
          <button
            type="button"
            onClick={onApi}
            aria-label="API và cài đặt"
            title="API và cài đặt"
            className="grid h-9 w-9 place-items-center border border-line bg-paper text-ink-soft transition-colors hover:border-ink hover:text-ink"
          >
            <BookOpen size={14} />
          </button>
        )}
        {onSettings && (
          <button
            type="button"
            onClick={onSettings}
            aria-label="Cài đặt"
            title="Cài đặt"
            className="grid h-9 w-9 place-items-center border border-line bg-paper text-ink-soft transition-colors hover:border-ink hover:text-ink"
          >
            <SettingsIcon size={14} />
          </button>
        )}
      </div>
    </header>
  );
}
