import { ExternalLink, FileSearch, type LucideIcon } from "lucide-react";
import { ToolShell, Panel } from "./ToolShell";

// Roadmap-stage tool page. The picked model + license + dataset + bench
// plan come from `docs/sota_vn_2026q2_expansion.md`. This shell renders
// them in a way that signals "research-validated, build pending" — not
// "broken stub."
//
// Backend wiring lands per-tool when the bench number is verified;
// until then, users see the plan they'll get, with a link to the survey.

export interface ResearchPick {
  /** Display name as it'll appear in production (e.g. "PhoBERT-base"). */
  name: string;
  /** Fully-qualified HF / GitHub URL. */
  url: string;
  /** SPDX-style license name (e.g. "MIT", "Apache 2.0", "BSD-3"). */
  license: string;
  /** File format word: "safetensors", ".bin", ".onnx", "CSV", "—". */
  format: string;
  /** Param count, dataset size, etc. — short tag like "135 M" or "978 k pairs". */
  size: string;
}

export interface PlaceholderConfig {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  /** One-paragraph problem framing in VN. */
  problem: string;
  /** Top picks from the survey, primary first. */
  picks: ResearchPick[];
  /** Bench plan / training corpus / what we'll measure (VN). */
  benchPlan: string;
  /** Path to the per-tool research survey. */
  surveyPath: string;
  /** ISO date the bench is targeted to land. */
  eta?: string;
  /** Quick traps from the survey — copied verbatim short bullets. */
  traps?: string[];
}

export function ToolPlaceholder({ config }: { config: PlaceholderConfig }) {
  const { icon, title, subtitle, problem, picks, benchPlan, surveyPath, eta, traps } = config;
  return (
    <ToolShell
      icon={icon}
      title={title}
      subtitle={subtitle}
      options={
        <div className="space-y-3 text-xs leading-relaxed text-ink-soft">
          <div>
            <div className="meta uppercase tracking-widest">Trạng thái</div>
            <div className="mt-1 inline-flex items-center gap-1.5 border border-accent bg-accent-wash px-2 py-1 text-[11.5px] font-medium text-ink">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Đã nghiên cứu — đang chờ benchmark
            </div>
          </div>
          {eta && (
            <div>
              <div className="meta uppercase tracking-widest">Dự kiến</div>
              <div className="meta-strong mt-0.5">{eta}</div>
            </div>
          )}
          <div className="border-t border-line pt-3">
            <a
              className="inline-flex items-center gap-1 text-accent underline hover:text-ink"
              href={`https://github.com/nrl-ai/nom-vn/blob/main/${surveyPath}`}
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              Đọc khảo cứu chi tiết
            </a>
          </div>
        </div>
      }
    >
      <Panel label="Vấn đề" hint="vì sao tool này có trên roadmap">
        <p className="vn-text text-sm leading-relaxed text-ink/85">{problem}</p>
      </Panel>

      <Panel label="Mô hình đã chọn" hint={`${picks.length} ứng viên hàng đầu`}>
        <ul className="space-y-2">
          {picks.map((p, i) => (
            <li
              key={p.url}
              className="flex items-start gap-2 border border-line bg-paper px-3 py-2"
            >
              <span className="meta-strong mt-0.5 shrink-0 text-accent">
                {i === 0 ? "★" : `${i + 1}.`}
              </span>
              <div className="min-w-0 flex-1">
                <a
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-semibold text-ink hover:text-accent"
                >
                  {p.name}
                  <ExternalLink size={11} className="shrink-0 opacity-60" />
                </a>
                <div className="meta mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
                  <span>{p.license}</span>
                  <span className="text-ink-mute/40">·</span>
                  <span>{p.format}</span>
                  <span className="text-ink-mute/40">·</span>
                  <span>{p.size}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel label="Kế hoạch benchmark" hint="bench thật trước khi ship">
        <p className="vn-text text-sm leading-relaxed text-ink/85">{benchPlan}</p>
      </Panel>

      {traps && traps.length > 0 && (
        <Panel label="Cạm bẫy đã biết" hint="từ khảo cứu">
          <ul className="space-y-1.5">
            {traps.map((t, i) => (
              <li
                key={i}
                className="vn-text border-l-2 border-accent bg-paper px-3 py-1.5 text-[13px] leading-relaxed text-ink/85"
              >
                {t}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </ToolShell>
  );
}
