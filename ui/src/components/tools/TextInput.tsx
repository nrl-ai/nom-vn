import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Eraser, Sparkles } from "lucide-react";
import { Panel } from "./ToolShell";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  /** Quick-insert sample sentences. */
  samples?: ReadonlyArray<{ label: string; text: string }>;
}

export function TextInput({ value, onChange, placeholder, rows = 6, samples }: Props) {
  const charCount = value.length;
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  return (
    <Panel
      label="input"
      hint={`${charCount} chars · ${wordCount} words`}
      rightSlot={
        <>
          {samples && samples.length > 0 && (
            <div className="hidden flex-wrap gap-1 sm:flex">
              {samples.map((s) => (
                <Button
                  key={s.label}
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2"
                  onClick={() => onChange(s.text)}
                  title={s.text.slice(0, 80)}
                >
                  <Sparkles size={11} className="text-accent" />
                  {s.label}
                </Button>
              ))}
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            disabled={!value}
            onClick={() => onChange("")}
            aria-label="Clear input"
          >
            <Eraser size={12} />
          </Button>
        </>
      }
    >
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder ?? "Nhập văn bản tiếng Việt…"}
        className="min-h-[120px]"
      />
    </Panel>
  );
}
