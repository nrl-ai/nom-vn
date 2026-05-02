import {
  Bot,
  Building2,
  Code2,
  Eraser,
  Languages,
  MessageSquare,
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
    blurb: "Việt ↔ Anh, giữ nguyên định dạng .docx",
    icon: Languages,
    category: "text",
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
    key: "agents",
    label: "Chạy tác tử",
    blurb: "Theo dõi suy luận và gọi công cụ",
    icon: Bot,
    category: "rag",
  },
  {
    key: "compliance",
    label: "Phân loại rủi ro",
    blurb: "Luật 134/2025 — phân loại 3 mức",
    icon: ShieldCheck,
    category: "rag",
  },
  {
    key: "admin",
    label: "Quản trị doanh nghiệp",
    blurb: "Giấy phép, người dùng, audit — bản EE",
    icon: Building2,
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
