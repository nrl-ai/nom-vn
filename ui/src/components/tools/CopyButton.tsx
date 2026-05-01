import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  text: string;
  label?: string;
}

export function CopyButton({ text, label }: Props) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 1100);
    return () => window.clearTimeout(id);
  }, [copied]);

  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // Browsers without clipboard API or denied permissions: silent fail.
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      disabled={!text}
      className="h-7 px-2"
      aria-label={label ? `Copy ${label}` : "Copy"}
    >
      {copied ? <Check size={12} className="text-ok" /> : <Copy size={12} />}
      <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
    </Button>
  );
}
