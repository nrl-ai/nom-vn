import { useEffect } from "react";

/** Bind Cmd/Ctrl+Enter to a run callback, document-wide.
 *
 * Tool pages share a "fill the textarea, hit Run" rhythm. The browser default
 * Enter behavior in a textarea is "newline" — Shift+Enter would conflict — so
 * we use Cmd/Ctrl+Enter which is the universal "submit" shortcut on the web. */
export function useToolRunner(run: () => void, enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        run();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [run, enabled]);
}
