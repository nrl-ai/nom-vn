// Tiny safe-by-default markdown renderer for assistant answers.
//
// Why hand-rolled, not `marked` / `remark`?
// - The LLM answers we render are short and use a small subset
//   (bold, italic, lists, code, links, paragraphs).
// - Pulling in a full markdown lib costs ~30 KB gz and an XSS audit.
// - We always escape input first, then transform — no innerHTML on
//   user / model input.
// - Citation chips `[N]` are NOT rendered here; they're parsed by
//   <Message /> after this returns the safe-HTML string so chips
//   stay interactive.
//
// Supported syntax (intentionally narrow):
// - **bold**, __bold__
// - *italic*, _italic_
// - `inline code`
// - ```fenced``` (treated as a single <pre><code> block)
// - bullet lists (-, *, +) + ordered lists (1.)
// - paragraph breaks (blank line)
// - autolinks: bare http(s)://… URLs
//
// Anything else passes through as escaped text.

const ESC: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (m) => ESC[m]!);
}

/** Returns a safe HTML string. Caller wraps in dangerouslySetInnerHTML. */
export function renderMarkdown(src: string): string {
  // 1. Pull fenced code blocks out so their contents don't get
  //    inline-formatted (e.g. asterisks inside code shouldn't bold).
  const codeBlocks: string[] = [];
  let s = src.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_m, _lang, body) => {
    const i = codeBlocks.length;
    codeBlocks.push(escapeHtml(body));
    return `__NOM_CODEBLOCK_${i}__`;
  });

  // 2. Escape the rest. Now we only insert literal HTML through known-safe
  //    transforms below.
  s = escapeHtml(s);

  // 3. Inline code (after escape, but before bold/italic so backticked
  //    asterisks don't get formatted).
  const inlineCodes: string[] = [];
  s = s.replace(/`([^`\n]+)`/g, (_m, body) => {
    const i = inlineCodes.length;
    inlineCodes.push(body);
    return `__NOM_CODE_${i}__`;
  });

  // 4. Bold (** or __). Process before italic to avoid `*foo*` inside `**`.
  s = s.replace(/\*\*([^\s*][\s\S]*?[^\s*]|\S)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__([^\s_][\s\S]*?[^\s_]|\S)__/g, "<strong>$1</strong>");

  // 5. Italic (* or _). Single-char ones; require non-space neighbors.
  s = s.replace(/(^|[\s(])\*([^\s*][^*]*?[^\s*]|\S)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
  s = s.replace(/(^|[\s(])_([^\s_][^_]*?[^\s_]|\S)_(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");

  // 6. Autolinks (escaped & is &amp; in source after step 2).
  s = s.replace(
    /(^|[\s(])(https?:\/\/[^\s<>()[\]"]+[^\s<>()[\]".,;:!?])/g,
    '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>',
  );

  // 7. Lists. Walk lines and group consecutive list items.
  const lines = s.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    const ulMatch = line.match(/^\s*[-*+]\s+(.*)$/);
    const olMatch = line.match(/^\s*(\d+)\.\s+(.*)$/);
    if (ulMatch) {
      const items: string[] = [];
      while (i < lines.length) {
        const m = lines[i]!.match(/^\s*[-*+]\s+(.*)$/);
        if (!m) break;
        items.push(`<li>${m[1]}</li>`);
        i++;
      }
      out.push(`<ul class="md-ul">${items.join("")}</ul>`);
    } else if (olMatch) {
      const items: string[] = [];
      while (i < lines.length) {
        const m = lines[i]!.match(/^\s*\d+\.\s+(.*)$/);
        if (!m) break;
        items.push(`<li>${m[1]}</li>`);
        i++;
      }
      out.push(`<ol class="md-ol">${items.join("")}</ol>`);
    } else {
      out.push(line);
      i++;
    }
  }
  s = out.join("\n");

  // 8. Paragraphs — split on blank lines, but DON'T wrap lines that already
  //    start with a block tag (<ul>, <ol>, <pre>, <h…>).
  const blocks = s.split(/\n{2,}/);
  s = blocks
    .map((b) => {
      const t = b.trim();
      if (!t) return "";
      if (/^<(ul|ol|pre|h\d|blockquote|table)/.test(t)) return t;
      // Single newlines inside a paragraph become <br />.
      return `<p>${t.replace(/\n/g, "<br />")}</p>`;
    })
    .join("\n");

  // 9. Restore inline code and code blocks (placeholder tokens are
  //    underscore-fenced so they can't accidentally appear in source).
  s = s.replace(
    /__NOM_CODE_(\d+)__/g,
    (_m, i) => `<code class="md-code">${inlineCodes[+i]}</code>`,
  );
  s = s.replace(
    /__NOM_CODEBLOCK_(\d+)__/g,
    (_m, i) => `<pre class="md-pre"><code>${codeBlocks[+i]}</code></pre>`,
  );

  return s;
}
