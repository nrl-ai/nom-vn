// Thin fetch client. No swagger/codegen — endpoints are stable and few.
// All errors throw `ApiError` so React Query's onError gets a typed shape.

import type {
  Answer,
  DetectRes,
  DiacriticBackend,
  DiacriticModelsRes,
  DiacriticRestoreRes,
  Material,
  NoiseApplyRes,
  NoisePreset,
  NoisePresetInfo,
  NormalizeRes,
  SentenceTokenizeRes,
  Space,
  StripRes,
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
    noiseApply: (text: string, preset: NoisePreset, seed: number) =>
      request<NoiseApplyRes>("/api/tools/noise/apply", {
        method: "POST",
        body: JSON.stringify({ text, preset, seed }),
      }),
    noisePresets: () => request<{ presets: NoisePresetInfo[] }>("/api/tools/noise/presets"),
  },
};
