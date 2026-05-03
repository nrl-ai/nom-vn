import { Mic } from "lucide-react";
import { ToolPlaceholder, type PlaceholderConfig } from "../ToolPlaceholder";

const CONFIG: PlaceholderConfig = {
  icon: Mic,
  title: "Giọng nói → văn bản",
  subtitle: "PhoWhisper · phân tách người nói · giọng Bắc / Trung / Nam",
  problem:
    "PhoWhisper-large là mô hình STT tiếng Việt mạnh nhất công bố (VIVOS WER 4.67 %, 844 giờ training đa giọng), nhưng *không* công bố WER theo từng vùng miền. ViMD shows giọng Trung khó nhất (WER 18.26 % vs Nam 13.54 % trên PhoWhisper-base) — phải bench ViMD-Trung trước khi production claim. Code-switch VN↔EN tốt nhất bằng Whisper-large-v3 (zero-shot multilingual), không phải fine-tune VN.",
  picks: [
    {
      name: "VinAI/PhoWhisper-large",
      url: "https://huggingface.co/vinai/PhoWhisper-large",
      license: "BSD-3-Clause",
      format: ".bin (VinAI)",
      size: "1.5 B params",
    },
    {
      name: "openai/whisper-large-v3 (cho code-switch)",
      url: "https://huggingface.co/openai/whisper-large-v3",
      license: "MIT",
      format: "safetensors",
      size: "1.5 B params",
    },
    {
      name: "pyannote/speaker-diarization-community-1",
      url: "https://huggingface.co/pyannote/speaker-diarization-community-1",
      license: "CC-BY-4.0 (gated)",
      format: ".bin",
      size: "16 M",
    },
  ],
  benchPlan:
    "Bench PhoWhisper-large trên VIVOS + VLSP T1 (re-verify 4.67 / 13.75 %), rồi trên ViMD splits (Bắc 40.6h / Trung 31.5h / Nam 30.5h) để có per-region WER. Bench Whisper-v3 trên audio business code-switched (tự thu nhỏ 30 phút). Pick router theo content type. Diarization integrate sau khi STT base ổn (Tier 2).",
  surveyPath: "docs/research/2026-05-03-vn-stt-diarization-survey.md",
  eta: "Tier 1 · 3–4 ngày STT, +2–3 ngày diarization",
  traps: [
    "PhoWhisper checkpoint là pickled .bin, không có safetensors — VinAI trusted nhưng phải document SHA256 trong wrapper.",
    "ViMD là CC-BY-NC-ND-4.0 — chỉ dùng cho benchmark, không train. BUD500 (500h, Apache) cho training.",
    "Whisper-v3 zero-shot beat PhoWhisper trên code-switched business audio — không one-size-fits-all.",
  ],
};

export function SttPage() {
  return <ToolPlaceholder config={CONFIG} />;
}
