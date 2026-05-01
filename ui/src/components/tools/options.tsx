import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface OptionRowProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
}

export function OptionRow({ label, hint, children }: OptionRowProps) {
  return (
    <div className="mb-3 last:mb-0">
      <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-ink-mute">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">{hint}</p>}
    </div>
  );
}

interface SelectProps<T extends string> {
  value: T;
  onChange: (v: T) => void;
  options: ReadonlyArray<{ value: T; label: string; hint?: string }>;
  className?: string;
}

export function Select<T extends string>({ value, onChange, options, className }: SelectProps<T>) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={cn(
        "vn-text block w-full border border-ink bg-paper px-2.5 py-1.5 text-sm text-ink focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
        className,
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

interface SegmentedProps<T extends string> {
  value: T;
  onChange: (v: T) => void;
  options: ReadonlyArray<{ value: T; label: string }>;
}

export function Segmented<T extends string>({ value, onChange, options }: SegmentedProps<T>) {
  return (
    <div className="inline-flex border border-ink bg-paper" role="tablist">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors",
              active ? "bg-ink text-bg" : "text-ink hover:bg-bg-soft",
              "border-l border-line first:border-l-0",
            )}
          >
            {active && <Check size={11} className="-ml-1 mr-1 inline" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

interface NumberFieldProps {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
}

export function NumberField({ value, onChange, min, max, step, className }: NumberFieldProps) {
  return (
    <input
      type="number"
      value={Number.isFinite(value) ? value : ""}
      min={min}
      max={max}
      step={step}
      onChange={(e) => {
        const n = Number(e.target.value);
        if (Number.isFinite(n)) onChange(n);
      }}
      className={cn(
        "block w-full border border-ink bg-paper px-2.5 py-1.5 font-mono text-sm text-ink focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
        className,
      )}
    />
  );
}
