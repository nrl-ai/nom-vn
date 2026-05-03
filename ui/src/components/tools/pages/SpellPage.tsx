import { SpellCheck } from "lucide-react";
import { ToolPlaceholder, type PlaceholderConfig } from "../ToolPlaceholder";

const CONFIG: PlaceholderConfig = {
  icon: SpellCheck,
  title: "Kiểm tra chính tả",
  subtitle: "telex · dấu · phương ngữ · teencode — xử lý cục bộ",
  problem:
    "Word, Google Docs spell-check tiếng Việt yếu; LanguageTool VN coverage mỏng; chưa có công cụ open-source local nào đủ tốt. Đây là gap lớn nhất trong VN local NLP — universal need, dễ viral nếu ship đúng. coung21/vi-spelling-correction (978 k cặp lỗi-đúng, MIT) cover 4 kênh lỗi thật: lỗi telex, mất dấu, phương ngữ, teencode.",
  picks: [
    {
      name: "vinai/bartpho-syllable-base + coung21 fine-tune",
      url: "https://huggingface.co/vinai/bartpho-syllable-base",
      license: "MIT",
      format: ".bin (VinAI)",
      size: "115 M",
    },
    {
      name: "coung21/vi-spelling-correction (dataset)",
      url: "https://huggingface.co/datasets/coung21/vi-spelling-correction",
      license: "MIT",
      format: "CSV",
      size: "978 k cặp",
    },
  ],
  benchPlan:
    "v0.1 (3–5 ngày): fine-tune BARTpho-syllable trên coung21, eval trên Viwiki-spelling slice + Tatoeba-vi conversational để tránh corruption-overfit. v0.2 (+3 ngày): thêm PhoBERT-base token-classifier làm precision guard — chỉ run seq2seq trên syllable bị flag, mục tiêu FPR < 5 % trên UD-VTB clean.",
  surveyPath: "docs/research/2026-05-03-vn-spell-grammar-survey.md",
  eta: "Tier 1 · 3–5 ngày",
  traps: [
    "NFC mọi nơi — train data, inference input, eval target. Wikipedia VN mix NFC/NFD im lặng làm rớt 15 pp.",
    "coung21 có 50 % noise rate — train trên đó được, nhưng eval phải dùng corpus thật để tránh overfit nhiễu.",
    "VN GEC gold corpus (CoNLL-2014 equivalent) chưa tồn tại — grammar correction khó test rigorous.",
  ],
};

export function SpellPage() {
  return <ToolPlaceholder config={CONFIG} />;
}
