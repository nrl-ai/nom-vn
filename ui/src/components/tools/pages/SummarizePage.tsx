import { AlignLeft } from "lucide-react";
import { ToolPlaceholder, type PlaceholderConfig } from "../ToolPlaceholder";

const CONFIG: PlaceholderConfig = {
  icon: AlignLeft,
  title: "Tóm tắt",
  subtitle: "theo văn phong · báo / hợp đồng / hội thoại",
  problem:
    "ViT5-large là VN news-summarization SOTA (ROUGE-1 63.4 vietnews). Nhưng VN encoder-decoder cap 1 024 token — hợp đồng pháp luật vượt giới hạn. Hơn nữa news / legal / dialogue cần style summary khác nhau: 3 câu lead cho báo, bullet điều khoản cho hợp đồng, ai-nói-gì cho thoại. Cần LoRA per register trên Qwen3-8B (131 k context) cho long-form, sau khi register classifier (Tier 1) sẵn sàng.",
  picks: [
    {
      name: "VietAI/vit5-large (cho news)",
      url: "https://huggingface.co/VietAI/vit5-large",
      license: "MIT",
      format: ".bin",
      size: "866 M, 1024 ctx",
    },
    {
      name: "Qwen/Qwen3-8B + LoRA per register",
      url: "https://huggingface.co/Qwen/Qwen3-8B",
      license: "Apache 2.0",
      format: "safetensors",
      size: "8 B, 131k ctx",
    },
    {
      name: "nam194/vietnews (corpus)",
      url: "https://huggingface.co/datasets/nam194/vietnews",
      license: "permissive",
      format: "JSONL",
      size: "143 k articles",
    },
  ],
  benchPlan:
    "v0.1 (1–2 ngày, Tier 2): ViT5-large off-the-shelf trên vietnews + VLSP 2022 AbMuSu, eval ROUGE với underthesea.word_tokenize (pin tokenizer trong result JSON). v0.2 (Tier 3, ~15–21 ngày): 3 LoRA × Qwen3-8B base — news / legal / dialogue. Phụ thuộc register classifier để route. Legal LoRA gated trên việc xây corpus hợp đồng VN public-license.",
  surveyPath: "docs/research/2026-05-03-vn-summarization-survey.md",
  eta: "Tier 2 (news off-the-shelf) → Tier 3 (per-register LoRA)",
  traps: [
    "VN ROUGE pin = underthesea.word_tokenize. Default whitespace ROUGE chia syllable, scores cross-paper không comparable.",
    "Encoder-decoder VN cap 1024 token — legal phải dùng Qwen3-8B (131 k context) trực tiếp.",
    "XLSum VN (40 k) là CC-BY-NC-SA, non-commercial — skip cho training, dùng nam194/vietnews thay thế.",
  ],
};

export function SummarizePage() {
  return <ToolPlaceholder config={CONFIG} />;
}
