import { useEffect, useState } from "react";
import { ShieldCheck, Play, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { Textarea } from "@/components/ui/textarea";

const STORAGE_KEY = "nom:tool:compliance";

type Sector = "health" | "education" | "finance" | "public-services" | "other";
type AutomationLevel = "advisory" | "semi-autonomous" | "autonomous";
type UserScope = "individual" | "org" | "public-mass";

interface Spec {
  purpose: string;
  sector: Sector;
  automation_level: AutomationLevel;
  user_scope: UserScope;
  handles_personal_data: boolean;
  affects_vulnerable_groups: boolean;
  can_generate_synthetic_content: boolean;
  interacts_directly_with_users: boolean;
}

interface Result {
  tier: "high" | "medium" | "low";
  applicable_articles: string[];
  reasoning: string[];
  fired_rule_ids: string[];
  law_id: string;
  law_version: string;
}

const DEFAULT_SPEC: Spec = {
  purpose: "",
  sector: "other",
  automation_level: "advisory",
  user_scope: "individual",
  handles_personal_data: false,
  affects_vulnerable_groups: false,
  can_generate_synthetic_content: false,
  interacts_directly_with_users: true,
};

function load(): Spec {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SPEC;
    return { ...DEFAULT_SPEC, ...(JSON.parse(raw) as Partial<Spec>) };
  } catch {
    return DEFAULT_SPEC;
  }
}

const SECTOR_OPTIONS: { value: Sector; label: string }[] = [
  { value: "health", label: "Y tế" },
  { value: "education", label: "Giáo dục" },
  { value: "finance", label: "Tài chính / ngân hàng" },
  { value: "public-services", label: "Dịch vụ công" },
  { value: "other", label: "Khác" },
];

const AUTOMATION_OPTIONS: { value: AutomationLevel; label: string }[] = [
  { value: "advisory", label: "Gợi ý — người vận hành quyết định" },
  { value: "semi-autonomous", label: "Bán tự động — người trong vòng lặp" },
  { value: "autonomous", label: "Tự động — không có người duyệt" },
];

const SCOPE_OPTIONS: { value: UserScope; label: string }[] = [
  { value: "individual", label: "Cá nhân" },
  { value: "org", label: "Trong tổ chức" },
  { value: "public-mass", label: "Công khai đại chúng" },
];

export function CompliancePage() {
  const [spec, setSpec] = useState<Spec>(load);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(spec));
  }, [spec]);

  const update = <K extends keyof Spec>(key: K, value: Spec[K]) => {
    setSpec((s) => ({ ...s, [key]: value }));
  };

  const classify = async () => {
    if (!spec.purpose.trim()) {
      setError("Cần điền mô tả mục đích trước khi phân loại.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/compliance/classify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(spec),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setError((detail as { detail?: string }).detail ?? `HTTP ${res.status}`);
        setResult(null);
      } else {
        setResult((await res.json()) as Result);
      }
    } catch (e) {
      setError(`Lỗi kết nối: ${(e as Error).message}`);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ToolShell
      icon={ShieldCheck}
      title="Phân loại rủi ro AI"
      subtitle="theo Luật 134/2025/QH15 — Đ9 / Đ10 / Đ11 / Đ14 / Đ15"
      pending={loading}
      options={
        <>
          <OptionRow label="Lĩnh vực">
            <Select
              value={spec.sector}
              onChange={(v) => update("sector", v as Sector)}
              options={SECTOR_OPTIONS}
            />
          </OptionRow>
          <OptionRow label="Mức tự động">
            <Select
              value={spec.automation_level}
              onChange={(v) => update("automation_level", v as AutomationLevel)}
              options={AUTOMATION_OPTIONS}
            />
          </OptionRow>
          <OptionRow label="Phạm vi người dùng">
            <Select
              value={spec.user_scope}
              onChange={(v) => update("user_scope", v as UserScope)}
              options={SCOPE_OPTIONS}
            />
          </OptionRow>
          <Toggle
            label="Xử lý dữ liệu cá nhân"
            checked={spec.handles_personal_data}
            onChange={(v) => update("handles_personal_data", v)}
            hint="Trigger Đ7.3 và NĐ 13/2023"
          />
          <Toggle
            label="Ảnh hưởng nhóm dễ tổn thương"
            checked={spec.affects_vulnerable_groups}
            onChange={(v) => update("affects_vulnerable_groups", v)}
            hint="Trẻ em, người cao tuổi, người khuyết tật, dân tộc thiểu số (Đ7.2.c)"
          />
          <Toggle
            label="Có sinh nội dung tổng hợp"
            checked={spec.can_generate_synthetic_content}
            onChange={(v) => update("can_generate_synthetic_content", v)}
            hint="Trigger Đ11.2 đánh dấu nội dung và Đ11.4 deepfake"
          />
          <Toggle
            label="Tương tác trực tiếp với người dùng"
            checked={spec.interacts_directly_with_users}
            onChange={(v) => update("interacts_directly_with_users", v)}
            hint="Trigger Đ11.1 thông báo 'đây là AI'"
          />
        </>
      }
      footer={
        <div className="flex items-center gap-2">
          <Button onClick={classify} disabled={loading || !spec.purpose.trim()} size="sm">
            <Play size={14} className="mr-1.5" /> Phân loại
          </Button>
          {loading && <Spinner />}
        </div>
      }
    >
      <div className="grid h-full min-h-0 gap-4 overflow-auto p-4 lg:grid-cols-2 lg:gap-6 lg:p-6">
        <Panel
          label="Mô tả hệ thống"
          hint="một đoạn ngắn về mục đích — Đ10.1 yêu cầu hồ sơ phân loại"
        >
          <Textarea
            value={spec.purpose}
            onChange={(e) => update("purpose", e.target.value)}
            placeholder="Ví dụ: 'Trợ lý hỏi-đáp pháp luật cho công dân, dùng RAG trên kho văn bản pháp luật.'"
            rows={6}
            className="border-line bg-paper text-sm"
          />
        </Panel>

        <Panel label="Kết quả" hint="tier + điều luật áp dụng + lý luận">
          {error && (
            <div className="flex items-center gap-2 border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-900">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          {!result && !error && !loading && (
            <EmptyHint>
              Điền mô tả + tuỳ chọn rồi bấm <strong>Phân loại</strong>. Kết quả sẽ liệt kê mức rủi
              ro, các điều luật áp dụng và lý luận từng quy tắc fire.
            </EmptyHint>
          )}
          {result && <ResultView result={result} />}
        </Panel>
      </div>
    </ToolShell>
  );
}

function ResultView({ result }: { result: Result }) {
  const tierStyle = {
    high: "bg-red-100 border-red-300 text-red-900",
    medium: "bg-amber-100 border-amber-300 text-amber-900",
    low: "bg-emerald-100 border-emerald-300 text-emerald-900",
  }[result.tier];
  const tierLabel = {
    high: "Rủi ro cao (Đ9.1.a)",
    medium: "Rủi ro trung bình (Đ9.1.b)",
    low: "Rủi ro thấp (Đ9.1.c)",
  }[result.tier];

  return (
    <div className="space-y-4">
      <div className={`flex items-start gap-2 border px-3 py-2 text-sm ${tierStyle}`}>
        <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
        <div>
          <div className="font-semibold">{tierLabel}</div>
          <div className="mt-0.5 text-xs opacity-80">
            Theo {result.law_id} {result.law_version}
          </div>
        </div>
      </div>

      <div>
        <h4 className="mb-1 font-mono text-[11px] uppercase tracking-widest text-ink-mute">
          Điều luật áp dụng
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {result.applicable_articles.map((a) => (
            <span
              key={a}
              className="inline-flex items-center border border-ink bg-bg-soft px-2 py-0.5 font-mono text-[11px] text-ink"
            >
              {a}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="mb-1 font-mono text-[11px] uppercase tracking-widest text-ink-mute">
          Lý luận (rule {result.fired_rule_ids.length} fire)
        </h4>
        <ol className="space-y-1 text-xs text-ink/80">
          {result.reasoning.map((r, i) => (
            <li key={i} className="border-l-2 border-line pl-2">
              {r}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}

function Toggle({ label, checked, onChange, hint }: ToggleProps) {
  return (
    <div className="mb-3">
      <label className="flex cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-0.5 accent-accent"
        />
        <span className="flex-1 text-ink">{label}</span>
      </label>
      {hint && <p className="ml-6 mt-0.5 text-[11.5px] leading-snug text-ink-soft">{hint}</p>}
    </div>
  );
}
