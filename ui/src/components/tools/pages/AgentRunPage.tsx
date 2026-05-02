import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  Play,
  Square,
  AlertTriangle,
  Cog,
  Wrench,
  CheckCircle2,
  CircleDot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { TextInput } from "../TextInput";
import { useAgents } from "@/api/queries";

const STORAGE_KEY = "nom:tool:agent-run";

interface Persisted {
  agent: string;
  task: string;
}

const DEFAULTS: Persisted = { agent: "", task: "" };

interface TraceEvent {
  ts: number;
  kind: string;
  payload: Record<string, unknown>;
}

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    return DEFAULTS;
  }
}

export function AgentRunPage() {
  const [{ agent, task }, setState] = useState<Persisted>(load);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const agentsQ = useAgents();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ agent, task }));
  }, [agent, task]);

  // Auto-pick the first agent when the list arrives.
  useEffect(() => {
    if (!agent && agentsQ.data && agentsQ.data.agents.length > 0) {
      setState((s) => ({ ...s, agent: agentsQ.data!.agents[0].name }));
    }
  }, [agent, agentsQ.data]);

  const setAgent = (a: string) => setState((s) => ({ ...s, agent: a }));
  const setTask = (t: string) => setState((s) => ({ ...s, task: t }));

  const stop = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setRunning(false);
  }, []);

  const run = useCallback(() => {
    if (!agent) {
      setError("Chưa chọn tác tử.");
      return;
    }
    if (!task.trim()) {
      setError("Yêu cầu không được rỗng.");
      return;
    }
    setError(null);
    setEvents([]);
    setRunning(true);

    const url = `/api/agents/${encodeURIComponent(agent)}/stream?task=${encodeURIComponent(task)}`;
    const src = new EventSource(url);
    sourceRef.current = src;

    src.onmessage = (e: MessageEvent<string>) => {
      try {
        const ev = JSON.parse(e.data) as TraceEvent;
        setEvents((prev) => [...prev, ev]);
        if (ev.kind === "stream_close" || ev.kind === "end") {
          src.close();
          sourceRef.current = null;
          setRunning(false);
        }
      } catch {
        /* ignore parse failures — server should never emit non-JSON */
      }
    };

    src.onerror = () => {
      setError("Mất kết nối với máy chủ. Hãy thử lại.");
      src.close();
      sourceRef.current = null;
      setRunning(false);
    };
  }, [agent, task]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => sourceRef.current?.close();
  }, []);

  const noAgents = agentsQ.data && agentsQ.data.agents.length === 0;

  return (
    <ToolShell
      icon={Bot}
      title="Chạy tác tử"
      subtitle="theo dõi suy luận và gọi công cụ theo thời gian thực"
      pending={running}
      options={
        <>
          <OptionRow label="Tác tử">
            <Select
              value={agent}
              onChange={setAgent}
              options={
                agentsQ.data?.agents.length
                  ? agentsQ.data.agents.map((a: { name: string; type: string }) => ({
                      value: a.name,
                      label: `${a.name} · ${a.type}`,
                    }))
                  : [{ value: "", label: "(chưa có tác tử)" }]
              }
            />
          </OptionRow>
          <div className="text-muted text-xs">
            {agentsQ.isLoading
              ? "Đang tải danh sách…"
              : noAgents
                ? "Chưa có tác tử nào được đăng ký trên máy chủ."
                : "Mỗi tác tử do nhà vận hành cấu hình từ phía máy chủ."}
          </div>
        </>
      }
      footer={
        <div className="flex items-center gap-2">
          {running ? (
            <Button onClick={stop} variant="outline" size="sm">
              <Square size={14} className="mr-1.5" /> Dừng
            </Button>
          ) : (
            <Button onClick={run} disabled={!agent || !task.trim() || agentsQ.isLoading} size="sm">
              <Play size={14} className="mr-1.5" /> Chạy
            </Button>
          )}
          {running && <Spinner />}
          <span className="text-muted text-xs">
            {events.length > 0 ? `${events.length} sự kiện` : ""}
          </span>
        </div>
      }
    >
      <div className="grid h-full min-h-0 gap-4 overflow-auto p-4 lg:grid-cols-2 lg:gap-6 lg:p-6">
        <TextInput
          value={task}
          onChange={setTask}
          placeholder="Ví dụ: 'Tóm tắt hợp đồng và liệt kê các bên liên quan, ngày ký.'"
          rows={6}
        />

        <Panel label="Sự kiện" hint="nhật ký từng bước của tác tử">
          {error && (
            <div className="flex items-center gap-2 border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-900">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          {events.length === 0 && !running && !error && (
            <EmptyHint>
              Nhập yêu cầu rồi bấm <strong>Chạy</strong>. Mỗi bước (suy luận, gọi công cụ, kết quả
              công cụ, trả lời) sẽ hiện ở đây theo thời gian thực.
            </EmptyHint>
          )}
          <ol className="space-y-1.5">
            {events.map((ev, i) => (
              <TraceLine key={i} ev={ev} />
            ))}
          </ol>
        </Panel>
      </div>
    </ToolShell>
  );
}

function TraceLine({ ev }: { ev: TraceEvent }) {
  const Icon = iconForKind(ev.kind);
  const label = labelForKind(ev.kind);
  const summary = summariseEvent(ev);
  return (
    <li className="flex gap-2 border-l-2 border-line py-1 pl-3">
      <Icon size={14} className="mt-0.5 shrink-0 text-accent" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xs font-semibold uppercase tracking-wide text-ink">
            {label}
          </span>
          <span className="text-muted text-[11px]">
            {new Date(ev.ts * 1000).toLocaleTimeString()}
          </span>
        </div>
        {summary && <div className="mt-0.5 break-words text-xs text-ink/80">{summary}</div>}
      </div>
    </li>
  );
}

function iconForKind(kind: string) {
  switch (kind) {
    case "tool_call":
      return Cog;
    case "tool_result":
      return Wrench;
    case "final":
      return CheckCircle2;
    case "error":
      return AlertTriangle;
    default:
      return CircleDot;
  }
}

function labelForKind(kind: string): string {
  switch (kind) {
    case "start":
      return "Bắt đầu";
    case "think":
      return "Suy luận";
    case "tool_call":
      return "Gọi công cụ";
    case "tool_result":
      return "Kết quả";
    case "final":
      return "Trả lời";
    case "end":
      return "Kết thúc";
    case "error":
      return "Lỗi";
    case "stream_open":
      return "Mở luồng";
    case "stream_close":
      return "Đóng luồng";
    case "step_output":
      return "Kết quả bước";
    case "privacy.detect":
      return "Phát hiện thông tin cá nhân";
    case "privacy.redact":
      return "Che thông tin cá nhân";
    case "privacy.block":
      return "Chặn yêu cầu";
    default:
      return kind;
  }
}

function summariseEvent(ev: TraceEvent): string {
  const p = ev.payload ?? {};
  switch (ev.kind) {
    case "start":
      return typeof p.agent === "string" ? `tác tử ${p.agent}` : "";
    case "think": {
      const thought = typeof p.thought === "string" ? p.thought : "";
      return thought.slice(0, 240);
    }
    case "tool_call": {
      const tool = typeof p.tool === "string" ? p.tool : "(không rõ)";
      const args = p.args && typeof p.args === "object" ? JSON.stringify(p.args) : "";
      return `${tool}(${args})`;
    }
    case "tool_result": {
      const ok = p.ok === true;
      const detail = ok
        ? typeof p.output === "string"
          ? p.output
          : JSON.stringify(p.output ?? "")
        : typeof p.error === "string"
          ? p.error
          : "lỗi không rõ";
      return `${ok ? "OK" : "LỖI"} · ${String(detail).slice(0, 200)}`;
    }
    case "final":
      return typeof p.answer === "string" ? p.answer : "";
    case "error":
      return typeof p.message === "string"
        ? p.message
        : typeof p.reason === "string"
          ? p.reason
          : "";
    case "end":
      return p.ok === false ? "thất bại" : "thành công";
    default: {
      const keys = Object.keys(p);
      if (keys.length === 0) return "";
      return keys
        .slice(0, 3)
        .map((k) => `${k}=${truncate(JSON.stringify(p[k]))}`)
        .join(" ");
    }
  }
}

function truncate(s: string): string {
  return s.length > 60 ? s.slice(0, 60) + "…" : s;
}
