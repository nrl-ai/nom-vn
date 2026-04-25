// File-type metadata used in the materials drawer + upload zone.
// Keep in sync with src/nom/doc/stages.py — every kind here that has
// `supported: true` must have a Parse path in the Python backend.

import type { LucideIcon } from "lucide-react";
import {
  FileText,
  FileImage,
  FileType,
  FileCode,
  FileSpreadsheet,
  Presentation,
  FileJson,
  Globe,
  File as FileIcon,
} from "lucide-react";

export type FileKind =
  | "pdf"
  | "image"
  | "text"
  | "docx"
  | "xlsx"
  | "pptx"
  | "html"
  | "json"
  | "code"
  | "other";

export interface FileTypeMeta {
  kind: FileKind;
  icon: LucideIcon;
  label: string;
  /** Tailwind text-color class for the icon. */
  colorClass: string;
  /** True if nom.doc.Pipeline can parse it today. */
  supported: boolean;
  /** Hint surfaced in the UI (tooltip) — supported caveat or warning. */
  hint?: string;
}

const PDF_RE = /\.pdf$/i;
const IMAGE_RE = /\.(png|jpe?g|gif|tiff?|bmp|webp)$/i;
const DOCX_RE = /\.docx?$/i;
const XLSX_RE = /\.xlsx?$/i;
const PPTX_RE = /\.pptx?$/i;
const HTML_RE = /\.x?html?$/i;
const JSON_RE = /\.(json|jsonl|ndjson)$/i;
const CODE_RE = /\.(ya?ml|toml|xml|sql|py|js|ts|tsx|jsx)$/i;
const TEXT_RE = /\.(txt|md|markdown|rst|log|tsv|csv)$/i;
const UNSUPPORTED_OFFICE_RE = /\.(odt|odp|ods|rtf|epub)$/i;

export function getFileTypeMeta(name: string): FileTypeMeta {
  if (PDF_RE.test(name)) {
    return {
      kind: "pdf",
      icon: FileType,
      label: "PDF",
      colorClass: "text-danger",
      supported: true,
    };
  }
  if (IMAGE_RE.test(name)) {
    return {
      kind: "image",
      icon: FileImage,
      label: "Image",
      colorClass: "text-accent",
      supported: true,
      hint: "OCR'd via Tesseract on first ask",
    };
  }
  if (DOCX_RE.test(name)) {
    return {
      kind: "docx",
      icon: FileText,
      label: "DOCX",
      colorClass: "text-blue-700",
      supported: true,
      hint: "Word document — paragraphs + tables extracted",
    };
  }
  if (XLSX_RE.test(name)) {
    return {
      kind: "xlsx",
      icon: FileSpreadsheet,
      label: "XLSX",
      colorClass: "text-ok",
      supported: true,
      hint: "Excel — one slide per sheet, tab-separated rows",
    };
  }
  if (PPTX_RE.test(name)) {
    return {
      kind: "pptx",
      icon: Presentation,
      label: "PPTX",
      colorClass: "text-accent",
      supported: true,
      hint: "PowerPoint — text frames + speaker notes per slide",
    };
  }
  if (HTML_RE.test(name)) {
    return {
      kind: "html",
      icon: Globe,
      label: "HTML",
      colorClass: "text-ink-soft",
      supported: true,
      hint: "Body text extracted (script/style tags dropped)",
    };
  }
  if (JSON_RE.test(name)) {
    return {
      kind: "json",
      icon: FileJson,
      label: name.toLowerCase().endsWith("l") ? "JSONL" : "JSON",
      colorClass: "text-ink-soft",
      supported: true,
      hint: "Each record indexed as a separate text block",
    };
  }
  if (CODE_RE.test(name)) {
    return {
      kind: "code",
      icon: FileCode,
      label: "Code",
      colorClass: "text-ink-soft",
      supported: true,
      hint: "Treated as plain text",
    };
  }
  if (TEXT_RE.test(name)) {
    return { kind: "text", icon: FileText, label: "TEXT", colorClass: "text-ok", supported: true };
  }
  if (UNSUPPORTED_OFFICE_RE.test(name)) {
    return {
      kind: "other",
      icon: FileSpreadsheet,
      label: name.split(".").pop()?.toUpperCase() ?? "Doc",
      colorClass: "text-ink-mute",
      supported: false,
      hint: "Format not yet supported — save as DOCX/PDF/TXT first.",
    };
  }
  return {
    kind: "other",
    icon: FileIcon,
    label: "Unknown",
    colorClass: "text-ink-mute",
    supported: true,
    hint: "Unknown extension — will be read as plain text. May produce garbage.",
  };
}

/** Comma-separated `accept` attribute for the upload <input>. */
export const ACCEPT_EXTENSIONS = [
  // documents
  ".pdf",
  ".docx",
  ".doc",
  ".xlsx",
  ".xls",
  ".pptx",
  ".ppt",
  // text
  ".txt",
  ".md",
  ".markdown",
  ".rst",
  ".log",
  ".csv",
  ".tsv",
  // structured
  ".json",
  ".jsonl",
  ".ndjson",
  ".html",
  ".htm",
  ".xml",
  ".yaml",
  ".yml",
  // images (OCR)
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".tiff",
  ".tif",
  ".bmp",
  ".webp",
].join(",");
