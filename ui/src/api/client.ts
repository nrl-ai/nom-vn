// Thin fetch client. No swagger/codegen — endpoints are stable and few.
// All errors throw `ApiError` so React Query's onError gets a typed shape.

import type {
  Answer,
  BgJob,
  BgJobListRes,
  ConvertFileStats,
  DetectRes,
  DiacriticBackend,
  DiacriticModelsRes,
  DiacriticRestoreRes,
  HandwritingOcrRes,
  LanguageRes,
  Material,
  ModelsListRes,
  NERRes,
  NormalizeRes,
  PullsListRes,
  PullState,
  RegisterBackend,
  RegisterRes,
  SentenceTokenizeRes,
  SentimentRes,
  SttBackend,
  SttRes,
  Space,
  StripRes,
  TranslateBackend,
  TranslateFileRes,
  TranslateFileStats,
  TranslateLang,
  TranslateModelsRes,
  TranslateRes,
  WordFmt,
  WordTokenizeRes,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/** Local key holding the bearer token used when the server sets
 *  NOM_AUTH_TOKEN. Plain localStorage is sufficient — auth here is a
 *  protect-against-LAN-snoops measure, not a hardened authn scheme. */
const AUTH_TOKEN_KEY = "nom:auth-token";

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* localStorage may be unavailable — token won't survive reload */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // raw text it is
    }
    throw new ApiError(res.status, detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listSpaces: () => request<Space[]>("/api/spaces"),
  createSpace: (name: string) =>
    request<Space>("/api/spaces", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  deleteSpace: (id: string) => request<undefined>(`/api/spaces/${id}`, { method: "DELETE" }),
  listMaterials: (spaceId: string) => request<Material[]>(`/api/spaces/${spaceId}/materials`),
  uploadMaterial: (spaceId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", file.name);
    return request<Material>(`/api/spaces/${spaceId}/materials`, {
      method: "POST",
      body: fd,
    });
  },
  ask: (spaceId: string, question: string, topK = 5) =>
    request<Answer>(`/api/spaces/${spaceId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, top_k: topK }),
    }),
  materialRawUrl: (spaceId: string, materialId: string) =>
    `/api/spaces/${spaceId}/materials/${materialId}/raw`,
  materialText: (spaceId: string, materialId: string) =>
    request<{
      name: string;
      text: string;
      pages: string[];
      chunks: string[];
      n_pages: number;
      n_chunks: number;
      n_chars: number;
    }>(`/api/spaces/${spaceId}/materials/${materialId}/text`),
  indexSpace: (spaceId: string) =>
    request<{ n_indexed: number; n_total: number }>(`/api/spaces/${spaceId}/index`, {
      method: "POST",
    }),
  health: () =>
    request<{
      status: string;
      version: string;
      store: string;
      llm: string | null;
      llm_class: string | null;
      embedder: string | null;
      ocr_available: boolean;
      auth_required: boolean;
    }>(`/api/health`),
  llmBackends: () =>
    request<{
      active: { name: string | null; class: string | null; model: string | null };
      available: Array<{
        id: string;
        label: string;
        kind: "local-http" | "local-inproc" | "cloud";
        available: boolean;
        model_hint: string;
        needs: string[];
      }>;
    }>(`/api/llm/backends`),
  // -- Agents ------------------------------------------------------------
  agents: {
    list: () => request<{ agents: { name: string; type: string }[] }>("/api/agents"),
    run: (name: string, task: string) =>
      request<{
        output: string;
        trace: { ts: number; kind: string; payload: Record<string, unknown> }[];
        n_tool_calls: number;
        n_llm_calls: number;
        run_id: string;
      }>(`/api/agents/${encodeURIComponent(name)}/run`, {
        method: "POST",
        body: JSON.stringify({ task }),
      }),
  },
  // -- Playground tools --------------------------------------------------
  tools: {
    diacriticRestore: (text: string, backend: DiacriticBackend, modelId?: string) =>
      request<DiacriticRestoreRes>("/api/tools/diacritic/restore", {
        method: "POST",
        body: JSON.stringify({ text, backend, ...(modelId ? { model_id: modelId } : {}) }),
      }),
    diacriticStrip: (text: string) =>
      request<StripRes>("/api/tools/diacritic/strip", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    diacriticModels: () => request<DiacriticModelsRes>("/api/tools/diacritic/models"),
    tokenizeWord: (text: string, fmt: WordFmt = "list") =>
      request<WordTokenizeRes>("/api/tools/tokenize/word", {
        method: "POST",
        body: JSON.stringify({ text, fmt }),
      }),
    tokenizeSentence: (text: string) =>
      request<SentenceTokenizeRes>("/api/tools/tokenize/sentence", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    normalize: (text: string) =>
      request<NormalizeRes>("/api/tools/text/normalize", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    detect: (text: string) =>
      request<DetectRes>("/api/tools/text/detect", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    nerTag: (text: string) =>
      request<NERRes>("/api/tools/nlp/ner", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    sentiment: (text: string) =>
      request<SentimentRes>("/api/tools/nlp/sentiment", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    detectLanguage: (text: string) =>
      request<LanguageRes>("/api/tools/nlp/language", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    classifyRegister: (text: string, backend: RegisterBackend = "lexicon", modelId?: string) =>
      request<RegisterRes>("/api/tools/classify/register", {
        method: "POST",
        body: JSON.stringify({
          text,
          backend,
          ...(modelId ? { model_id: modelId } : {}),
        }),
      }),
    ocrHandwriting: (file: File, modelId?: string) => {
      const fd = new FormData();
      fd.append("file", file);
      if (modelId) fd.append("model_id", modelId);
      return request<HandwritingOcrRes>("/api/tools/ocr/handwriting", {
        method: "POST",
        body: fd,
      });
    },
    sttTranscribe: (
      file: File,
      backend: SttBackend = "phowhisper",
      opts: { language?: string; returnTimestamps?: boolean } = {},
    ) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("backend", backend);
      if (opts.language) fd.append("language", opts.language);
      if (opts.returnTimestamps) fd.append("return_timestamps", "true");
      return request<SttRes>("/api/tools/stt/transcribe", {
        method: "POST",
        body: fd,
      });
    },
    translate: (
      text: string,
      source: TranslateLang,
      target: TranslateLang,
      backend: TranslateBackend = "llm",
      modelId?: string,
    ) =>
      request<TranslateRes>("/api/tools/translate", {
        method: "POST",
        body: JSON.stringify({
          text,
          source,
          target,
          backend,
          ...(modelId ? { model_id: modelId } : {}),
        }),
      }),
    translateModels: () => request<TranslateModelsRes>("/api/tools/translate/models"),
    translateFile: async (
      file: File,
      source: TranslateLang,
      target: TranslateLang,
      backend: TranslateBackend = "llm",
      modelId?: string,
    ): Promise<TranslateFileRes> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("source", source);
      fd.append("target", target);
      fd.append("backend", backend);
      if (modelId) fd.append("model_id", modelId);
      const token = getAuthToken();
      const res = await fetch("/api/tools/translate/file", {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          const parsed = JSON.parse(text);
          if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
        } catch {
          // raw text
        }
        throw new ApiError(res.status, detail);
      }
      const blob = await res.blob();
      const stats = JSON.parse(
        res.headers.get("X-Translation-Stats") ?? "{}",
      ) as TranslateFileStats;
      // Pull filename from Content-Disposition: attachment; filename="..."
      const cd = res.headers.get("Content-Disposition") ?? "";
      const match = /filename="?([^";]+)"?/i.exec(cd);
      const filename = match ? match[1] : `translated.${target}.docx`;
      return { blob, filename, stats };
    },
  },
  models: {
    list: () => request<ModelsListRes>("/api/models"),
    pulls: () => request<PullsListRes>("/api/models/pulls"),
    pull: (model: string) =>
      request<{ pull_id: string; model: string; status: string }>("/api/models/pull", {
        method: "POST",
        body: JSON.stringify({ source: "ollama", model }),
      }),
    pullBatch: (models: string[]) =>
      request<{
        results: Array<{ model: string; status: string; pull_id?: string; error?: string }>;
      }>("/api/models/pull/batch", {
        method: "POST",
        body: JSON.stringify({ models }),
      }),
    cancelPull: (pullId: string) =>
      request<PullState>(`/api/models/pull/${encodeURIComponent(pullId)}/cancel`, {
        method: "POST",
      }),
    deleteOllama: (model: string) =>
      request<{ deleted: string }>(`/api/models/ollama/${encodeURIComponent(model)}`, {
        method: "DELETE",
      }),
  },
  // -- Background jobs ---------------------------------------------------
  jobs: {
    list: () => request<BgJobListRes>("/api/jobs"),
    get: (id: string) => request<BgJob>(`/api/jobs/${id}`),
    cancel: (id: string) => request<BgJob>(`/api/jobs/${id}/cancel`, { method: "POST" }),
    delete: (id: string) => request<undefined>(`/api/jobs/${id}`, { method: "DELETE" }),
    downloadUrl: (id: string) => `/api/jobs/${id}/download`,
    startTranslate: async (
      file: File,
      source: TranslateLang,
      target: TranslateLang,
      backend: TranslateBackend = "llm",
      modelId?: string,
    ): Promise<BgJob> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("source", source);
      fd.append("target", target);
      fd.append("backend", backend);
      if (modelId) fd.append("model_id", modelId);
      return request<BgJob>("/api/jobs/translate-file", { method: "POST", body: fd });
    },
    startConvert: async (file: File, ocrLanguage: string = "vie+eng"): Promise<BgJob> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("ocr_language", ocrLanguage);
      return request<BgJob>("/api/jobs/convert-file", { method: "POST", body: fd });
    },
  },
  convert: {
    file: async (
      file: File,
      ocrLanguage: string = "vie+eng",
    ): Promise<{ blob: Blob; filename: string; stats: ConvertFileStats }> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("ocr_language", ocrLanguage);
      const token = getAuthToken();
      const res = await fetch("/api/tools/convert/file", {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          const parsed = JSON.parse(text);
          if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
        } catch {
          // raw text
        }
        throw new ApiError(res.status, detail);
      }
      const blob = await res.blob();
      const stats = JSON.parse(res.headers.get("X-Convert-Stats") ?? "{}") as ConvertFileStats;
      const cd = res.headers.get("Content-Disposition") ?? "";
      const match = /filename="?([^";]+)"?/i.exec(cd);
      const filename = match ? match[1] : "converted.docx";
      return { blob, filename, stats };
    },
  },
};
