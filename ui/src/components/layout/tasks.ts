import {
  Building2,
  Code2,
  Eraser,
  FileType,
  Languages,
  ListChecks,
  MessageSquare,
  Package,
  Scissors,
  Settings,
  ShieldCheck,
  Sigma,
  Type,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// NLP analysis (NER / sentiment / language detection) is exposed via
// the API today (`/api/tools/nlp/*`); UI pages for these will land in
// a follow-up — see plan.md Wave 6.
export type TaskKey =
  | "chat"
  | "diacritic"
  | "tokenize"
  | "normalize"
  | "strip"
  | "translate"
  | "convert"
  | "jobs"
  | "register"
  | "handwriting"
  | "spell"
  | "stt"
  | "ner"
  | "summarize"
  | "models"
  | "agents"
  | "compliance"
  | "admin"
  | "api"
  | "settings";

export interface TaskMeta {
  key: TaskKey;
  label: string;
  blurb: string;
  icon: LucideIcon;
  category: "rag" | "text" | "dev";
}

// Per-task URL slug. Each tab gets its own browser URL so deep-links
// (e.g. https://nom-vn.nrl.ai/translate) work, back/forward navigates
// between tabs, and bookmarking lands you on the same screen.
//
// Slugs are kept in English so the same paths work after localization
// (a Spanish or Japanese build of the UI swaps labels, not URLs).
// "api" would collide with the /api/* HTTP namespace, so the docs page
// gets "/api-docs" instead.
export const TASK_SLUGS: Record<TaskKey, string> = {
  chat: "/",
  translate: "/translate",
  convert: "/convert",
  jobs: "/jobs",
  diacritic: "/diacritic",
  tokenize: "/tokenize",
  normalize: "/normalize",
  strip: "/strip",
  register: "/register",
  handwriting: "/handwriting",
  spell: "/spell",
  stt: "/stt",
  ner: "/ner",
  summarize: "/summarize",
  models: "/models",
  agents: "/agents",
  compliance: "/compliance",
  admin: "/admin",
  api: "/api-docs",
  settings: "/settings",
};

export const SLUG_TO_TASK: Record<string, TaskKey> = Object.fromEntries(
  Object.entries(TASK_SLUGS).map(([k, v]) => [v, k as TaskKey]),
) as Record<string, TaskKey>;

export function taskFromPath(pathname: string): TaskKey | null {
  // Normalize trailing slash; only "/" maps to chat.
  const cleaned = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");
  return SLUG_TO_TASK[cleaned] ?? null;
}

// `agents` is currently hidden from the nav (no UI page yet) but the slug,
// TaskKey, and route handling stay so existing deep-links keep working.
export const TASKS: TaskMeta[] = [
  {
    key: "chat",
    label: "Chat & RAG",
    blurb: "Hỏi đáp tài liệu",
    icon: MessageSquare,
    category: "rag",
  },
  {
    key: "translate",
    label: "Dịch thuật",
    blurb: "Việt · Anh · 中 · 한 · 日, giữ định dạng tệp",
    icon: Languages,
    category: "rag",
  },
  {
    key: "convert",
    label: "Chuyển định dạng",
    blurb: "PDF / ảnh / DOCX / TXT / MD — chuyển qua lại",
    icon: FileType,
    category: "rag",
  },
  {
    key: "jobs",
    label: "Hàng đợi xử lý",
    blurb: "Theo dõi tác vụ chạy nền + tiến độ",
    icon: ListChecks,
    category: "rag",
  },
  {
    key: "diacritic",
    label: "Khôi phục dấu",
    blurb: "Bù lại dấu cho văn bản",
    icon: Type,
    category: "text",
  },
  {
    key: "tokenize",
    label: "Tách từ / câu",
    blurb: "Tách theo từ và theo câu",
    icon: Scissors,
    category: "text",
  },
  {
    key: "normalize",
    label: "Chuẩn hoá",
    blurb: "NFC và nhận diện tiếng Việt",
    icon: Sigma,
    category: "text",
  },
  {
    key: "strip",
    label: "Bỏ dấu",
    blurb: "Chuyển sang ASCII",
    icon: Eraser,
    category: "text",
  },
  {
    key: "compliance",
    label: "Phân loại rủi ro",
    blurb: "Luật 134/2025 — 3 mức",
    icon: ShieldCheck,
    category: "rag",
  },
  {
    key: "admin",
    label: "Quản trị doanh nghiệp",
    blurb: "Giấy phép · audit · người dùng",
    icon: Building2,
    category: "dev",
  },
  {
    key: "models",
    label: "Mô hình",
    blurb: "quản lý mô hình AI cài đặt cục bộ",
    icon: Package,
    category: "dev",
  },
  {
    key: "api",
    label: "API và cài đặt",
    blurb: "Hướng dẫn chạy và ví dụ cURL",
    icon: Code2,
    category: "dev",
  },
  {
    key: "settings",
    label: "Cài đặt",
    blurb: "Trạng thái máy chủ và xác thực",
    icon: Settings,
    category: "dev",
  },
];
