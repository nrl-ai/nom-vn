import * as React from "react";
import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "vn-text flex w-full resize-none border border-ink bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:opacity-40",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
