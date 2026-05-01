import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolShellProps {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  /** Right-side options column (sticky on desktop). */
  options?: React.ReactNode;
  /** Main input/output region (textareas, results). */
  children: React.ReactNode;
  /** Optional footer for global actions (Run, Reset, Copy). */
  footer?: React.ReactNode;
  /** Show a thin progress bar at the top while running. */
  pending?: boolean;
}

export function ToolShell({
  icon: Icon,
  title,
  subtitle,
  options,
  children,
  footer,
  pending,
}: ToolShellProps) {
  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="relative shrink-0 border-b border-line px-4 py-3 lg:px-6">
        <div className="flex items-baseline justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="vn-text flex items-center gap-2 truncate font-display text-base font-semibold tracking-tight text-ink">
              <Icon size={16} className="text-accent" />
              {title}
            </h2>
            {subtitle && <span className="section-mark mt-0.5 block">§ {subtitle}</span>}
          </div>
        </div>
        {pending && (
          <div className="absolute inset-x-0 bottom-0 h-px overflow-hidden">
            <div className="h-full w-1/3 animate-[slide-x_1.2s_linear_infinite] bg-accent" />
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-6xl gap-4 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_280px] lg:gap-6 lg:px-6">
          <div className="min-w-0 space-y-4">{children}</div>
          {options && (
            <aside className="lg:sticky lg:top-3 lg:self-start">
              <div className="border border-line bg-paper p-4">
                <div className="section-mark mb-3">§ options</div>
                {options}
              </div>
            </aside>
          )}
        </div>
      </div>

      {footer && (
        <div className="shrink-0 border-t border-line bg-bg px-4 py-3 lg:px-6">{footer}</div>
      )}
    </div>
  );
}

interface EmptyHintProps {
  children: React.ReactNode;
}

/** Hint shown in the result region before the user runs the tool. */
export function EmptyHint({ children }: EmptyHintProps) {
  return (
    <div className="border border-dashed border-line bg-paper/40 px-4 py-6 text-center text-sm text-ink-mute">
      {children}
    </div>
  );
}

interface PanelProps {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
  rightSlot?: React.ReactNode;
}

export function Panel({ label, hint, className, children, rightSlot }: PanelProps) {
  return (
    <section className={cn("border border-line bg-paper", className)}>
      <div className="flex items-center justify-between border-b border-line-soft px-3 py-2">
        <div>
          <span className="section-mark">§ {label}</span>
          {hint && <span className="ml-2 font-mono text-[11px] text-ink-mute">{hint}</span>}
        </div>
        {rightSlot && <div className="flex items-center gap-1">{rightSlot}</div>}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin text-accent" />;
}
