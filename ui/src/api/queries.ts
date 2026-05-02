import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { api } from "./client";
import type {
  DiacriticBackend,
  Material,
  Space,
  TranslateBackend,
  TranslateLang,
  WordFmt,
} from "./types";

const keys = {
  spaces: () => ["spaces"] as const,
  materials: (spaceId: string) => ["materials", spaceId] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    staleTime: 60_000,
    retry: 0, // health failing once is enough — we already show the toast
  });
}

export function useLlmBackends() {
  return useQuery({
    queryKey: ["llm-backends"],
    queryFn: api.llmBackends,
    staleTime: Infinity, // probe result is import-time only
    retry: 0,
  });
}

export function useSpaces(): UseQueryResult<Space[]> {
  return useQuery({
    queryKey: keys.spaces(),
    queryFn: api.listSpaces,
    staleTime: 30_000,
  });
}

export function useCreateSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.createSpace(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.spaces() }),
  });
}

export function useDeleteSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSpace(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.spaces() }),
  });
}

export function useMaterials(spaceId: string | null): UseQueryResult<Material[]> {
  return useQuery({
    queryKey: keys.materials(spaceId ?? ""),
    queryFn: () => api.listMaterials(spaceId!),
    enabled: !!spaceId,
    staleTime: 15_000,
  });
}

export function useUploadMaterial(spaceId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      if (!spaceId) throw new Error("no active space");
      return api.uploadMaterial(spaceId, file);
    },
    onSuccess: () => {
      if (spaceId) {
        qc.invalidateQueries({ queryKey: keys.materials(spaceId) });
        qc.invalidateQueries({ queryKey: keys.spaces() });
      }
    },
  });
}

export function useIndexSpace(spaceId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!spaceId) throw new Error("no active space");
      return api.indexSpace(spaceId);
    },
    onSuccess: () => {
      if (spaceId) {
        qc.invalidateQueries({ queryKey: keys.materials(spaceId) });
        qc.invalidateQueries({ queryKey: keys.spaces() });
      }
    },
  });
}

export function useMaterialText(spaceId: string | null, materialId: string | null) {
  return useQuery({
    queryKey: ["material-text", spaceId, materialId],
    queryFn: () => api.materialText(spaceId!, materialId!),
    enabled: !!spaceId && !!materialId,
    staleTime: 60_000,
  });
}

export function useAsk(spaceId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ question, topK }: { question: string; topK?: number }) => {
      if (!spaceId) throw new Error("no active space");
      return api.ask(spaceId, question, topK ?? 5);
    },
    onSuccess: () => {
      // Indexing may have updated material chunk counts (first ask).
      if (spaceId) qc.invalidateQueries({ queryKey: keys.materials(spaceId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Playground tools — one mutation per tool. Mutations (not queries) because
// each is action-driven: user fills the input, hits Run, we POST. Persisting
// last-run results is the responsibility of the page component.
// ---------------------------------------------------------------------------

export function useDiacriticRestore() {
  return useMutation({
    mutationFn: (vars: { text: string; backend: DiacriticBackend; modelId?: string }) =>
      api.tools.diacriticRestore(vars.text, vars.backend, vars.modelId),
  });
}

export function useDiacriticStrip() {
  return useMutation({ mutationFn: (text: string) => api.tools.diacriticStrip(text) });
}

export function useDiacriticModels() {
  return useQuery({
    queryKey: ["tools", "diacritic-models"],
    queryFn: api.tools.diacriticModels,
    staleTime: Infinity,
  });
}

export function useWordTokenize() {
  return useMutation({
    mutationFn: (vars: { text: string; fmt: WordFmt }) =>
      api.tools.tokenizeWord(vars.text, vars.fmt),
  });
}

export function useSentenceTokenize() {
  return useMutation({ mutationFn: (text: string) => api.tools.tokenizeSentence(text) });
}

export function useNormalize() {
  return useMutation({ mutationFn: (text: string) => api.tools.normalize(text) });
}

export function useDetect() {
  return useMutation({ mutationFn: (text: string) => api.tools.detect(text) });
}

export function useNERTag() {
  return useMutation({ mutationFn: (text: string) => api.tools.nerTag(text) });
}

export function useSentiment() {
  return useMutation({ mutationFn: (text: string) => api.tools.sentiment(text) });
}

export function useDetectLanguage() {
  return useMutation({
    mutationFn: (text: string) => api.tools.detectLanguage(text),
  });
}

export function useTranslateText() {
  return useMutation({
    mutationFn: (vars: {
      text: string;
      source: TranslateLang;
      target: TranslateLang;
      backend: TranslateBackend;
      modelId?: string;
    }) => api.tools.translate(vars.text, vars.source, vars.target, vars.backend, vars.modelId),
  });
}

export function useTranslateFile() {
  return useMutation({
    mutationFn: (vars: {
      file: File;
      source: TranslateLang;
      target: TranslateLang;
      backend: TranslateBackend;
      modelId?: string;
    }) => api.tools.translateFile(vars.file, vars.source, vars.target, vars.backend, vars.modelId),
  });
}

export function useTranslateModels() {
  return useQuery({
    queryKey: ["tools", "translate-models"],
    queryFn: api.tools.translateModels,
    staleTime: Infinity,
  });
}
