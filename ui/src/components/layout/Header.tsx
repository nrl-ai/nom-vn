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
  /** When true (chat mode on mobile), reserve room on the right for
   *  the studio drawer toggle floated by AppShell. */
  reserveRightOnMobile?: boolean;
}

export function Header({
  modelName,
  onHome,
  onSettings,
  onApi,
  reserveRightOnMobile,
}: HeaderProps) {
  // Reserve 40px on the right whenever AppShell floats the studio toggle
  // there (chat mode below xl), so it doesn't cover the settings button.
  // The toggle disappears at xl, where right-pad collapses back to 5.
  const rightPad = reserveRightOnMobile ? "pr-12 xl:pr-5" : "pr-3 xl:pr-5";
  return (
    <header
      className={`flex h-12 shrink-0 items-center justify-between border-b border-ink bg-bg pl-12 ${rightPad} xl:pl-5 xl:pr-5`}
    >
      <button
        onClick={onHome}
        className="group flex items-baseline gap-3"
        title="Về trang chủ"
        aria-label="Trang chủ"
      >
        <h1 className="font-display text-xl font-bold leading-none tracking-tight text-ink transition-colors group-hover:text-accent">
          Nôm <span className="font-serif font-normal text-accent">喃</span>
        </h1>
        <span className="section-mark hidden transition-colors group-hover:text-ink sm:inline">
          công cụ ai tiếng việt
        </span>
      </button>
      <div className="flex items-center gap-2 text-xs">
        {modelName && (
          <span className="meta-strong hidden items-center gap-1.5 border border-line bg-paper px-2 py-1 sm:inline-flex">
            <Cpu size={11} className="text-accent" />
            {modelName}
          </span>
        )}
        <span className="meta hidden sm:inline">v0.2.31</span>
        {onApi && (
          <button
            type="button"
            onClick={onApi}
            aria-label="API và cài đặt"
            title="API và cài đặt"
            className="grid h-8 w-8 place-items-center border border-line bg-paper text-ink-soft transition-colors hover:border-ink hover:text-ink"
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
            className="grid h-8 w-8 place-items-center border border-line bg-paper text-ink-soft transition-colors hover:border-ink hover:text-ink"
          >
            <SettingsIcon size={14} />
          </button>
        )}
      </div>
    </header>
  );
}
