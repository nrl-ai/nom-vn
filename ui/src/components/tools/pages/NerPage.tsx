import { Tags } from "lucide-react";
import { ToolPlaceholder, type PlaceholderConfig } from "../ToolPlaceholder";

const CONFIG: PlaceholderConfig = {
  icon: Tags,
  title: "Trích xuất thực thể",
  subtitle: "người · tổ chức · nơi chốn · điều luật · bên hợp đồng",
  problem:
    'PhoBERT-base fine-tune đạt F1 94.7 trên VLSP 2016 (PER/ORG/LOC/MISC) — base đủ mạnh. Nhưng 4 kiểu chuẩn không đủ cho compliance: cần thêm LAW_REF (vd "Điều 5 Luật 134/2025"), CONTRACT_PARTY, CURRENCY_VND, ID_NUMBER_VN. Bổ trợ trang Phân loại rủi ro: classify + extract entities tạo lock-in cho enterprise tier.',
  picks: [
    {
      name: "vinai/phobert-base (token-classification)",
      url: "https://huggingface.co/vinai/phobert-base",
      license: "MIT",
      format: ".bin (VinAI)",
      size: "135 M params",
    },
    {
      name: "NlpHUST/ner-vietnamese-electra-base",
      url: "https://huggingface.co/NlpHUST/ner-vietnamese-electra-base",
      license: "MIT",
      format: "safetensors",
      size: "110 M params",
    },
    {
      name: "th1nhng0/vietnamese-legal-documents (corpus)",
      url: "https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents",
      license: "CC-BY-4.0",
      format: "JSONL",
      size: "153 k docs",
    },
  ],
  benchPlan:
    "v0.1: bench PhoBERT-base + NlpHUST trên VLSP 2018 để verify base F1. Tier 3 work: dataset prep cho LAW_REF + CONTRACT_PARTY — regex pre-label trên corpus pháp luật + manual refinement 2 000 sample LAW_REF + 500 sample CONTRACT_PARTY (tổng ~70–90 annotator-hours). Train head riêng, IAA ≥ 0.85 trước khi ship.",
  surveyPath: "docs/research/2026-05-03-vn-ner-legal-survey.md",
  eta: "Tier 3 · annotation chiếm 70–90 giờ",
  traps: [
    "PhoBERT BẮT BUỘC input đã word-segment qua VnCoreNLP — bypass = rớt 15–20 pp. Wrapper không cho skip.",
    "LLM zero-shot loses 5–30 pp F1 vs fine-tune trên domain — chỉ dùng LLM offline cho pre-labeling.",
  ],
};

export function NerPage() {
  return <ToolPlaceholder config={CONFIG} />;
}
