import { PenLine } from "lucide-react";
import { ToolPlaceholder, type PlaceholderConfig } from "../ToolPlaceholder";

const CONFIG: PlaceholderConfig = {
  icon: PenLine,
  title: "OCR chữ viết tay",
  subtitle: "biểu mẫu · ghi chú · CMND · chữ tay tiếng Việt",
  problem:
    "Tesseract đạt CER 0.00 % trên chữ in nhưng 69 % trên chữ tay tiếng Việt — thua xa cả ngưỡng tối thiểu để dùng. VietOCR vgg_transformer giảm xuống 31.82 % nhưng vẫn quá cao cho biểu mẫu doanh nghiệp. Vintern-1B-v3_5 (5CD-AI) là mô hình mở duy nhất sub-1B được train riêng cho chữ tay tiếng Việt — chưa có CER public, cần bench trước.",
  picks: [
    {
      name: "5CD-AI/Vintern-1B-v3_5 (zero-shot)",
      url: "https://huggingface.co/5CD-AI/Vintern-1B-v3_5",
      license: "MIT",
      format: "safetensors",
      size: "0.9 B params",
    },
    {
      name: "microsoft/trocr-large-handwritten + VN fine-tune",
      url: "https://huggingface.co/microsoft/trocr-large-handwritten",
      license: "MIT",
      format: ".bin",
      size: "558 M params",
    },
  ],
  benchPlan:
    "Bench Vintern-1B zero-shot trên brianhuster/VietnameseOCRdataset (Apache 2.0, 7 296 ảnh). Nếu CER ≤ 15 % → ship trực tiếp. Nếu gap > 10 pp với baseline → fine-tune TrOCR-large trên 5CD-AI/Viet-Handwriting-OCR (sau khi confirm license với 5CD-AI). Pair với trang Chuyển định dạng (ảnh chữ tay → DOCX).",
  surveyPath: "docs/research/2026-05-03-vn-handwriting-ocr-survey.md",
  eta: "Tier 1 · 3–7 ngày",
  traps: [
    "VLM ảo trên line crops hẹp — luôn truyền ảnh nguyên trang + JSON-schema constraint, không cắt dòng.",
    "5CD-AI/Viet-Handwriting-OCR (23 k ảnh) chưa rõ license — phải confirm với 5CD-AI trước khi train.",
  ],
};

export function HandwritingPage() {
  return <ToolPlaceholder config={CONFIG} />;
}
