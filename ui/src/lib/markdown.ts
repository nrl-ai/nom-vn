// Tiny safe-by-default markdown renderer for assistant answers.
//
// Why hand-rolled, not `marked` / `remark`?
// - The LLM answers we render are short and use a small subset
//   (bold, italic, lists, code, links, paragraphs, tables).
// - Pulling in a full markdown lib costs ~30 KB gz and an XSS audit.
// - We always escape input first, then transform — no innerHTML on
//   user / model input.
// - Citation chips `[N]` are NOT rendered here; they're parsed by
//   <Message /> after this returns the safe-HTML string so chips
//   stay interactive.
//
// Supported syntax:
// - **bold**, __bold__
// - *italic*, _italic_
// - `inline code`
// - ```fenced``` (treated as a single <pre><code> block)
// - bullet lists (-, *, +) + ordered lists (1.)
// - paragraph breaks (blank line)
// - autolinks: bare http(s)://… URLs
// - GFM tables: `| col | col |\n|---|---|\n| val | val |`
// - headings: `# H1` through `###### H6`
// - inline charts: ```chart {"type":"bar","data":[{"label":"...","value":N},...]}```
//   renders inline SVG bar / line chart (no chart.js dependency).
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
  // 1. Pull fenced blocks out so their contents don't get inline-formatted.
  //    We special-case `chart` blocks → inline SVG; everything else stays
  //    as <pre><code>.
  const codeBlocks: string[] = [];
  let s = src.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_m, lang, body) => {
    const i = codeBlocks.length;
    if (lang === "chart") {
      codeBlocks.push(renderChart(body));
    } else {
      codeBlocks.push(`<pre class="md-pre"><code>${escapeHtml(body)}</code></pre>`);
    }
    return `NOMCODEBLOCK${i}`;
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
    return `NOMINLINECODE${i}`;
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

  // 7. Headings + lists + tables. Walk lines and group block constructs.
  const lines = s.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    // GFM table — header line followed by `|---|---|` separator, then rows.
    // Both lines start with `|`. Light heuristic; LLM tables follow this shape.
    if (line.match(/^\s*\|.+\|\s*$/) && i + 1 < lines.length) {
      const sep = lines[i + 1]!;
      if (sep.match(/^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/)) {
        const headers = splitRow(line);
        const aligns = splitRow(sep).map(parseAlign);
        i += 2;
        const rows: string[][] = [];
        while (i < lines.length && lines[i]!.match(/^\s*\|.+\|\s*$/)) {
          rows.push(splitRow(lines[i]!));
          i++;
        }
        out.push(renderTable(headers, aligns, rows));
        continue;
      }
    }
    // Headings (# H1 .. ###### H6).
    const headingMatch = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (headingMatch) {
      const level = headingMatch[1]!.length;
      out.push(`<h${level} class="md-h${level}">${headingMatch[2]}</h${level}>`);
      i++;
      continue;
    }
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
      if (/^<(ul|ol|pre|h\d|blockquote|table|figure)/.test(t)) return t;
      // Standalone fenced-code or chart placeholder — don't wrap in <p>
      // because step 9 will replace it with a block-level element.
      if (/^NOMCODEBLOCK\d+$/.test(t)) return t;
      // Single newlines inside a paragraph become <br />.
      return `<p>${t.replace(/\n/g, "<br />")}</p>`;
    })
    .join("\n");

  // 9. Restore inline code and code blocks (placeholder tokens are
  //    underscore-fenced so they can't accidentally appear in source).
  //    Code blocks are already wrapped (or rendered as charts) at step 1
  //    so we just splice them back in.
  // Order matters: replace NOMCODEBLOCK before NOMINLINECODE — neither name
  // is a substring of the other, but NOMCODEBLOCK will be wrapped in <p>
  // since it's a block-level swap, while NOMINLINECODE stays inline.
  s = s.replace(/NOMCODEBLOCK(\d+)/g, (_m, i) => codeBlocks[+i]!);
  s = s.replace(
    /NOMINLINECODE(\d+)/g,
    (_m, i) => `<code class="md-code">${inlineCodes[+i]}</code>`,
  );

  return s;
}

// --------------------------------------------------------------------------
// Table helpers

function splitRow(line: string): string[] {
  // Strip leading / trailing pipes, then split on `|`. Trim each cell.
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((c) => c.trim());
}

function parseAlign(sep: string): "left" | "right" | "center" | undefined {
  const left = sep.startsWith(":");
  const right = sep.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return undefined;
}

function renderTable(
  headers: string[],
  aligns: ("left" | "right" | "center" | undefined)[],
  rows: string[][],
): string {
  const styled = (i: number) => (aligns[i] ? ` style="text-align:${aligns[i]}"` : "");
  const head =
    "<thead><tr>" + headers.map((h, i) => `<th${styled(i)}>${h}</th>`).join("") + "</tr></thead>";
  const body =
    "<tbody>" +
    rows
      .map((r) => "<tr>" + r.map((c, i) => `<td${styled(i)}>${c}</td>`).join("") + "</tr>")
      .join("") +
    "</tbody>";
  return `<table class="md-table">${head}${body}</table>`;
}

// --------------------------------------------------------------------------
// Chart helper — inline SVG bar / line, no external deps.
//
// Accepts a JSON body inside ```chart``` like:
//   {"type": "bar", "title": "Doanh thu", "data": [{"label":"T1","value":850}, ...]}
// type: "bar" (default) | "line"
// data: list of {label, value}
// Anything else falls back to escaped JSON inside <pre>.

interface ChartPoint {
  label: string;
  value: number;
}
interface ChartSpec {
  type?: "bar" | "line";
  title?: string;
  data: ChartPoint[];
}

function renderChart(body: string): string {
  let spec: ChartSpec;
  try {
    spec = JSON.parse(body) as ChartSpec;
  } catch {
    return `<pre class="md-pre"><code>${escapeHtml(body)}</code></pre>`;
  }
  if (!Array.isArray(spec.data) || spec.data.length === 0) {
    return `<pre class="md-pre"><code>${escapeHtml(body)}</code></pre>`;
  }
  const w = 480;
  const h = 220;
  const padL = 36;
  const padB = 28;
  const padT = spec.title ? 28 : 8;
  const padR = 8;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const max = Math.max(...spec.data.map((d) => d.value));
  const min = Math.min(0, ...spec.data.map((d) => d.value));
  const span = max - min || 1;
  const x = (i: number): number => padL + (innerW * (i + 0.5)) / spec.data.length;
  const y = (v: number): number => padT + innerH - ((v - min) / span) * innerH;

  const title = spec.title
    ? `<text x="${w / 2}" y="18" text-anchor="middle" class="md-chart-title">${escapeHtml(spec.title)}</text>`
    : "";
  const axis =
    `<line x1="${padL}" y1="${padT + innerH}" x2="${w - padR}" y2="${padT + innerH}" class="md-chart-axis" />` +
    `<line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" class="md-chart-axis" />`;
  const xLabels = spec.data
    .map(
      (d, i) =>
        `<text x="${x(i)}" y="${padT + innerH + 16}" text-anchor="middle" class="md-chart-label">${escapeHtml(d.label)}</text>`,
    )
    .join("");
  const yMaxLabel = `<text x="${padL - 6}" y="${padT + 4}" text-anchor="end" class="md-chart-label">${formatNum(max)}</text>`;
  const yMinLabel =
    min < 0
      ? `<text x="${padL - 6}" y="${padT + innerH + 4}" text-anchor="end" class="md-chart-label">${formatNum(min)}</text>`
      : `<text x="${padL - 6}" y="${padT + innerH + 4}" text-anchor="end" class="md-chart-label">0</text>`;

  let body_svg: string;
  if (spec.type === "line") {
    const pts = spec.data.map((d, i) => `${x(i)},${y(d.value)}`).join(" ");
    body_svg =
      `<polyline points="${pts}" class="md-chart-line" />` +
      spec.data
        .map(
          (d, i) =>
            `<circle cx="${x(i)}" cy="${y(d.value)}" r="2.5" class="md-chart-dot"><title>${escapeHtml(d.label)}: ${formatNum(d.value)}</title></circle>`,
        )
        .join("");
  } else {
    const barW = (innerW / spec.data.length) * 0.7;
    body_svg = spec.data
      .map((d, i) => {
        const yy = y(d.value);
        const baseline = y(0);
        const top = Math.min(yy, baseline);
        const height = Math.abs(baseline - yy);
        return `<rect x="${x(i) - barW / 2}" y="${top}" width="${barW}" height="${height}" class="md-chart-bar"><title>${escapeHtml(d.label)}: ${formatNum(d.value)}</title></rect>`;
      })
      .join("");
  }

  return `<figure class="md-chart"><svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(spec.title ?? "chart")}">${title}${axis}${body_svg}${xLabels}${yMaxLabel}${yMinLabel}</svg></figure>`;
}

function formatNum(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
}
