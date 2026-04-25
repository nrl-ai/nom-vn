// Three-dot pulse used while waiting for an answer from the LLM.
export function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 text-ink-mute">
      <span
        className="block h-1.5 w-1.5 animate-pulse-dot rounded-none bg-current"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="block h-1.5 w-1.5 animate-pulse-dot rounded-none bg-current"
        style={{ animationDelay: "160ms" }}
      />
      <span
        className="block h-1.5 w-1.5 animate-pulse-dot rounded-none bg-current"
        style={{ animationDelay: "320ms" }}
      />
      <span className="ml-1 font-mono text-[10.5px] uppercase tracking-widest">thinking</span>
    </span>
  );
}
