import {
  MessageSquare,
  Type,
  Scissors,
  Sigma,
  Beaker,
  Eraser,
  Code2,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TaskKey =
  | "chat"
  | "diacritic"
  | "tokenize"
  | "normalize"
  | "strip"
  | "noise"
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
    key: "noise",
    label: "Sinh nhiễu",
    blurb: "Tạo cặp dữ liệu cho training",
    icon: Beaker,
    category: "text",
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
