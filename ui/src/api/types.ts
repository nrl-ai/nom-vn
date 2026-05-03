// Mirrors the FastAPI response shapes from src/nom/chat/server.py.
// Keep this file in lockstep with that module — there's no codegen
// because the surface is small and changes rarely.

export interface Space {
  id: string;
  name: string;
  created_at: number;
  n_materials: number;
}

export interface Material {
  id: string;
  space_id: string;
  name: string;
  n_bytes: number;
  n_chunks: number;
  uploaded_at: number;
}

export interface Citation {
  doc_idx: number;
  chunk_idx: number;
  score: number;
  text: string;
}

export interface Answer {
  text: string;
  citations: Citation[];
  n_retrieved: number;
}

/** Local-only message log entry — not persisted server-side in v0.2.x.
 *  Lives in localStorage keyed by space id. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  n_retrieved?: number;
  ts: number; // epoch seconds
  /** True while an assistant message is being awaited. */
  pending?: boolean;
  /** Set if the request errored — text holds the error message. */
  error?: boolean;
}

// ---------------------------------------------------------------------------
// Playground tools — stateless endpoints under /api/tools/*. Each request
// is pure (text in, derived text out). The UI types here mirror the
// FastAPI response shapes in src/nom/chat/tools_api.py. Kept lightweight
// — no codegen, no envelopes; the surface is small.
// ---------------------------------------------------------------------------

export type DiacriticBackend = "rule" | "hf" | "llm";

export interface DiacriticRestoreReq {
  text: string;
  backend?: DiacriticBackend;
  model_id?: string;
}

export interface DiacriticRestoreRes {
  input: string;
  restored: string;
  backend: DiacriticBackend;
  model_id: string | null;
}

export interface DiacriticModelInfo {
  id: string;
  label: string;
  tier: "accuracy" | "fast" | "robust" | "baseline";
  params_m: number;
  license: string;
}

export interface DiacriticModelsRes {
  default: string;
  models: DiacriticModelInfo[];
  presets: DiacriticBackend[];
}

export interface StripRes {
  input: string;
  stripped: string;
}

export type WordFmt = "list" | "text";

export interface WordTokenizeRes {
  input: string;
  tokens?: string[];
  text?: string;
  n_tokens?: number;
  n_compounds?: number;
}

export interface SentenceTokenizeRes {
  input: string;
  sentences: string[];
  n_sentences: number;
}

export interface NormalizeRes {
  input: string;
  nfc: string;
  full_normalized: string;
  is_nfc: boolean;
  n_input_codepoints: number;
  n_nfc_codepoints: number;
}

export interface DetectRes {
  input: string;
  is_vietnamese: boolean;
  has_diacritics: boolean;
  reason: string;
}

// NLP analysis (NER / sentiment / language detection)
export interface NERSpan {
  start: number;
  end: number;
  label: string;
  text: string;
  confidence: number;
}

export interface NERRes {
  input: string;
  spans: NERSpan[];
}

export interface SentimentRes {
  input: string;
  label: "negative" | "neutral" | "positive";
  score: number;
}

export interface LanguageRes {
  input: string;
  language: string;
  confidence: number;
}

// Translation — single string + file upload. Mirrors
// /api/tools/translate and /api/tools/translate/file in
// src/nom/chat/tools_api.py.
export type TranslateLang = "en" | "vi" | "zh" | "ko" | "ja";
export type TranslateBackend = "llm" | "hf";

export interface TranslateReq {
  text: string;
  source: TranslateLang;
  target: TranslateLang;
  backend?: TranslateBackend;
  model_id?: string;
}

export interface TranslateRes {
  input: string;
  translation: string;
  source: TranslateLang;
  target: TranslateLang;
  backend: TranslateBackend;
  model_id: string | null;
}

export interface TranslateModelInfo {
  id: string;
  label: string;
  tier: "accuracy" | "fast" | "specialist" | "general";
  params_m?: number;
  license: string;
  notes?: string;
}

export interface TranslateModelsRes {
  default_backend: TranslateBackend;
  directions: string[];
  backends: TranslateModelInfo[];
  hf_models: TranslateModelInfo[];
}

export interface TranslateFileStats {
  paragraphs_translated: number;
  paragraphs_skipped: number;
  paragraphs_failed: number;
  chars_in: number;
  chars_out: number;
  source: TranslateLang;
  target: TranslateLang;
  backend: TranslateBackend;
  model_id: string | null;
}

export interface TranslateFileRes {
  blob: Blob;
  filename: string;
  stats: TranslateFileStats;
}

// Models tab — Ollama tag listing + HF cache + async pulls.
export interface OllamaModelInfo {
  name: string;
  size_bytes: number;
  modified_at: string | null;
  digest: string | null;
}

export interface HFCacheEntry {
  repo_id: string;
  repo_type: string;
  size_bytes: number;
  last_accessed: number;
  n_revisions: number;
}

export interface CuratedModel {
  id: string;
  label: string;
  tier: "light" | "standard" | "power";
  size_gb: number;
  needs_ram_gb: number;
  use_cases: string[];
  license: string;
}

export interface ModelsListRes {
  ollama: {
    url: string;
    reachable: boolean;
    models: OllamaModelInfo[];
  };
  hf_cache: HFCacheEntry[];
  catalog: CuratedModel[];
}

export interface PullState {
  pull_id: string;
  source: string;
  model: string;
  status: "pending" | "downloading" | "success" | "error" | "cancelled";
  downloaded_bytes: number;
  total_bytes: number;
  progress: number;
  error: string | null;
  started_at: number;
  completed_at: number | null;
}

export interface PullsListRes {
  pulls: PullState[];
}
