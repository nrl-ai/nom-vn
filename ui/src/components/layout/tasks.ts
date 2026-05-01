import { MessageSquare, Type, Scissors, Sigma, Beaker, Eraser } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TaskKey = "chat" | "diacritic" | "tokenize" | "normalize" | "strip" | "noise";

export interface TaskMeta {
  key: TaskKey;
  label: string;
  blurb: string;
  icon: LucideIcon;
  category: "rag" | "text";
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
    blurb: "Diacritic restore",
    icon: Type,
    category: "text",
  },
  {
    key: "tokenize",
    label: "Tách từ / câu",
    blurb: "Word + sentence segment",
    icon: Scissors,
    category: "text",
  },
  {
    key: "normalize",
    label: "Chuẩn hoá",
    blurb: "NFC + VN detect",
    icon: Sigma,
    category: "text",
  },
  {
    key: "strip",
    label: "Bỏ dấu",
    blurb: "Strip diacritics",
    icon: Eraser,
    category: "text",
  },
  {
    key: "noise",
    label: "Sinh nhiễu",
    blurb: "Noise / typo generator",
    icon: Beaker,
    category: "text",
  },
];
