import { useEffect, useState } from "react";
import {
  Building2,
  KeyRound,
  Activity,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { ToolShell, Panel, EmptyHint } from "../ToolShell";

interface License {
  customer: string;
  tenant_id: string;
  tier: string;
  issued_at: string;
  expires_at: string;
  features: string[];
  expired: boolean;
}

interface Usage {
  tenant_id: string;
  window: string;
  tokens: { in: number; out: number };
  requests: { total: number; errors: number };
  latency_ms: { p50: number; p95: number; p99: number };
  note?: string;
}

type Status = "loading" | "no-ee" | "no-auth" | "ready" | "error";

export function AdminPage() {
  const [status, setStatus] = useState<Status>("loading");
  const [license, setLicense] = useState<License | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/admin/license");
        if (r.status === 404) {
          if (!cancelled) setStatus("no-ee");
          return;
        }
        if (r.status === 401) {
          if (!cancelled) setStatus("no-auth");
          return;
        }
        if (!r.ok) {
          if (!cancelled) {
            setStatus("error");
            setErrorMsg(`HTTP ${r.status}`);
          }
          return;
        }
        const lic = (await r.json()) as License;

        // Usage requires tenant.admin; gracefully tolerate 403.
        let use: Usage | null = null;
        try {
          const ur = await fetch("/api/admin/usage");
          if (ur.ok) use = (await ur.json()) as Usage;
        } catch {
          /* ignore — admin endpoint may be RBAC-gated */
        }

        if (!cancelled) {
          setLicense(lic);
          setUsage(use);
          setStatus("ready");
        }
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg((e as Error).message);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ToolShell
      icon={Building2}
      title="Bảng quản trị doanh nghiệp"
      subtitle="trạng thái giấy phép, quyền truy cập, và lưu lượng"
      options={
        <>
          <p className="text-xs leading-relaxed text-ink-soft">
            Bảng này yêu cầu cài thêm gói <code>nom-vn-enterprise</code> và
            đăng nhập bằng tài khoản có vai trò <code>tenant.admin</code>.
            Trên bản Cộng đồng (chỉ có lõi mã nguồn mở), trang sẽ gợi ý
            cách nâng cấp.
          </p>
        </>
      }
    >
      <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto p-4 lg:gap-6 lg:p-6">
        {status === "loading" && <EmptyHint>Đang tải trạng thái…</EmptyHint>}

        {status === "no-ee" && (
          <Panel
            label="Bản Cộng đồng"
            hint="bản nâng cấp Doanh nghiệp mở khoá các tính năng dưới đây"
          >
            <div className="space-y-3 text-sm text-ink/80">
              <p>
                Endpoint <code>/api/admin/*</code> chưa được kích hoạt — bạn
                đang chạy bản Cộng đồng (Apache 2.0). Để mở các tính năng
                quản trị doanh nghiệp:
              </p>
              <ol className="list-decimal space-y-1 pl-5">
                <li>
                  Cài gói <code>pip install nom-vn-enterprise[all]</code>
                </li>
                <li>
                  Đặt giấy phép tại <code>~/.nom/license.json</code>
                </li>
                <li>
                  Đăng nhập bằng tài khoản có vai trò
                  <code> tenant.admin</code>
                </li>
              </ol>
              <p className="pt-2 text-xs text-ink-soft">
                Khi đủ ba điều trên, trang này sẽ tự hiện thông tin giấy phép,
                người dùng và lưu lượng. Xem
                <a
                  className="ml-1 underline"
                  href="/doanh-nghiep/so-sanh-oss-ee"
                  target="_blank"
                  rel="noreferrer"
                >
                  bảng so sánh OSS vs Doanh nghiệp
                </a>
                .
              </p>
            </div>
          </Panel>
        )}

        {status === "no-auth" && (
          <Panel
            label="Cần đăng nhập"
            hint="bảng quản trị yêu cầu xác thực"
          >
            <div className="flex items-start gap-2 text-sm text-ink/80">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-700" />
              <div>
                Endpoint <code>/api/admin/license</code> trả về 401 — vui lòng
                cấu hình <code>NOM_AUTH_TOKEN</code> hoặc bật plugin OIDC, rồi
                đăng nhập lại.
              </div>
            </div>
          </Panel>
        )}

        {status === "error" && (
          <Panel label="Lỗi" hint="không tải được trạng thái">
            <div className="flex items-start gap-2 text-sm text-red-900">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div>{errorMsg}</div>
            </div>
          </Panel>
        )}

        {status === "ready" && license && (
          <>
            <LicenseCard license={license} />
            <FeaturesCard features={license.features} />
            {usage && <UsageCard usage={usage} />}
          </>
        )}
      </div>
    </ToolShell>
  );
}

function LicenseCard({ license }: { license: License }) {
  const ok = !license.expired;
  return (
    <Panel
      label="Giấy phép"
      hint={license.expired ? "đã hết hạn" : "đang hoạt động"}
    >
      <div
        className={`flex items-start gap-2 border px-3 py-2 ${
          ok
            ? "border-emerald-300 bg-emerald-50 text-emerald-900"
            : "border-red-300 bg-red-50 text-red-900"
        }`}
      >
        {ok ? (
          <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
        ) : (
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        )}
        <div className="text-sm">
          <div className="font-semibold">{license.customer}</div>
          <div className="mt-0.5 text-xs opacity-80">
            tenant <code>{license.tenant_id}</code> · gói{" "}
            <code>{license.tier}</code>
          </div>
          <div className="mt-1 text-[11px] opacity-70">
            cấp <code>{license.issued_at}</code> · hết hạn{" "}
            <code>{license.expires_at}</code>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function FeaturesCard({ features }: { features: string[] }) {
  const labels: Record<string, string> = {
    oidc: "OIDC",
    saml: "SAML 2.0",
    ldap: "LDAP / AD",
    rbac: "Phân quyền nhiều tổ chức",
    advanced_pii: "PII + tokenize",
    audit_shipper: "Đẩy audit về SOC",
    office: "Microsoft 365",
  };
  return (
    <Panel label="Tính năng đã kích hoạt" hint={`${features.length} tính năng`}>
      <div className="flex flex-wrap gap-1.5">
        {features.map((f) => (
          <span
            key={f}
            className="inline-flex items-center gap-1.5 border border-ink bg-bg-soft px-2 py-0.5 font-mono text-[11px] text-ink"
          >
            <ShieldCheck size={11} className="text-accent" />
            {labels[f] ?? f}
          </span>
        ))}
      </div>
    </Panel>
  );
}

function UsageCard({ usage }: { usage: Usage }) {
  return (
    <Panel
      label="Lưu lượng (cửa sổ 24 giờ)"
      hint="đẩy về Prometheus / OTel để có số thật"
      rightSlot={<Activity size={14} className="text-accent" />}
    >
      <div className="grid grid-cols-3 gap-3">
        <Stat
          icon={KeyRound}
          label="Token"
          value={`${usage.tokens.in.toLocaleString()} → ${usage.tokens.out.toLocaleString()}`}
        />
        <Stat
          icon={Activity}
          label="Yêu cầu"
          value={`${usage.requests.total} (${usage.requests.errors} lỗi)`}
        />
        <Stat
          icon={CheckCircle2}
          label="Độ trễ p95"
          value={`${usage.latency_ms.p95} ms`}
        />
      </div>
      {usage.note && (
        <p className="mt-3 text-[11.5px] leading-snug text-ink-soft">
          {usage.note}
        </p>
      )}
    </Panel>
  );
}

interface StatProps {
  icon: import("lucide-react").LucideIcon;
  label: string;
  value: string;
}

function Stat({ icon: Icon, label, value }: StatProps) {
  return (
    <div className="flex items-start gap-2 border border-line bg-paper p-2">
      <Icon size={14} className="mt-0.5 shrink-0 text-accent" />
      <div className="min-w-0">
        <div className="font-mono text-[10px] uppercase tracking-widest text-ink-mute">
          {label}
        </div>
        <div className="mt-0.5 truncate text-sm font-semibold text-ink">
          {value}
        </div>
      </div>
    </div>
  );
}
