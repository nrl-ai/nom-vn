import { useMemo } from "react";

interface Props {
  before: string;
  after: string;
}

interface Token {
  text: string;
  isWord: boolean;
}

const WORD_RE = /(\p{L}+|\p{N}+|[^\p{L}\p{N}\s]+|\s+)/gu;

function tokenize(s: string): Token[] {
  return Array.from(s.matchAll(WORD_RE), (m) => ({
    text: m[0],
    isWord: /[\p{L}\p{N}]/u.test(m[0]),
  }));
}

/** Strip-diacritics-style canonicalization for change detection.
 *
 * Two tokens are "the same word, different diacritics" iff they share an
 * NFD-stripped, lowercased form. We use that to highlight changed words
 * rather than a full LCS — for diacritic restoration the structure stays
 * the same and only word-level diacritics differ. */
function fold(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Mn}/gu, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

export function DiffView({ before, after }: Props) {
  const segments = useMemo(() => {
    const a = tokenize(before);
    const b = tokenize(after);
    const out: Array<{ before: string; after: string; changed: boolean }> = [];
    const n = Math.max(a.length, b.length);
    for (let i = 0; i < n; i++) {
      const x = a[i]?.text ?? "";
      const y = b[i]?.text ?? "";
      // Same fold-form means it's a diacritic-only change. Different
      // fold-form means a structural change (word added/removed/replaced).
      const changed = x !== y && (a[i]?.isWord || b[i]?.isWord ? true : x !== y);
      const sameFold = fold(x) === fold(y);
      out.push({ before: x, after: y, changed: changed && sameFold });
    }
    return out;
  }, [before, after]);

  return (
    <div className="vn-text whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-ink">
      {segments.map((s, i) => {
        if (!s.changed) return <span key={i}>{s.after}</span>;
        return (
          <span
            key={i}
            title={`was: ${s.before}`}
            className="bg-accent/30 box-decoration-clone px-0.5 font-medium text-accent-ink underline decoration-accent decoration-2 underline-offset-2"
          >
            {s.after}
          </span>
        );
      })}
    </div>
  );
}
