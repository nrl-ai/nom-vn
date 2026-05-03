import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { api } from "./client";
import type {
  BgJob,
  BgJobListRes,
  DiacriticBackend,
  Material,
  ModelsListRes,
  PullsListRes,
  RegisterBackend,
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

export function useClassifyRegister() {
  return useMutation({
    mutationFn: (vars: { text: string; backend?: RegisterBackend; modelId?: string }) =>
      api.tools.classifyRegister(vars.text, vars.backend, vars.modelId),
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

// Placeholder for the in-progress AgentRunPage. Returns an empty list
// Wire to api.agents.list. The endpoint may not be mounted (no
// nom-vn-enterprise installed; no agents registered) so we wrap in
// try/catch and surface an empty list — the UI's "(chưa có tác tử)"
// state covers that case.
export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: async () => {
      try {
        return await api.agents.list();
      } catch {
        return { agents: [] as Array<{ name: string; type: string }> };
      }
    },
    staleTime: 30_000,
    retry: 0,
  });
}

// Models tab — installed list + pull progress.
export function useModelsList(): UseQueryResult<ModelsListRes> {
  return useQuery({
    queryKey: ["models"],
    queryFn: api.models.list,
    staleTime: 30_000,
  });
}

export function useModelPulls(): UseQueryResult<PullsListRes> {
  return useQuery({
    queryKey: ["models", "pulls"],
    queryFn: api.models.pulls,
    // Only poll while a pull is actually in flight. Otherwise idle —
    // the manual "Pull" button calls invalidateQueries on success, which
    // will re-arm this without a permanent 1.5 s heartbeat.
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !data.pulls) return false;
      const inFlight = data.pulls.some((p) => p.status === "pending" || p.status === "downloading");
      return inFlight ? 1500 : false;
    },
  });
}

export function useStartPull() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model: string) => api.models.pull(model),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models", "pulls"] }),
  });
}

export function useStartPullBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (models: string[]) => api.models.pullBatch(models),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models", "pulls"] }),
  });
}

export function useCancelPull() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pullId: string) => api.models.cancelPull(pullId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models", "pulls"] }),
  });
}

export function useDeleteModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model: string) => api.models.deleteOllama(model),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models"] }),
  });
}

// Convert tab — file upload to /api/tools/convert/file.
export function useConvertFile() {
  return useMutation({
    mutationFn: (vars: { file: File; ocrLanguage?: string }) =>
      api.convert.file(vars.file, vars.ocrLanguage),
  });
}

// ---------------------------------------------------------------------------
// Background-job queue — translate + convert run in the server's
// thread pool, the UI polls. Polling cadence: aggressive while jobs are
// in-flight (every 700 ms), idle when nothing's running. The list query
// drives the Jobs sidebar / queue page.
// ---------------------------------------------------------------------------

export function useBgJobs(): UseQueryResult<BgJobListRes> {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs.list,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !data.jobs) return false;
      // Poll fast while any job is queued / running, otherwise stop.
      const inFlight = data.jobs.some((j) => j.status === "queued" || j.status === "running");
      return inFlight ? 700 : false;
    },
    staleTime: 0,
  });
}

export function useBgJob(id: string | null) {
  return useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.jobs.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 700;
      return data.status === "queued" || data.status === "running" ? 700 : false;
    },
    staleTime: 0,
  });
}

export function useStartTranslateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      file: File;
      source: TranslateLang;
      target: TranslateLang;
      backend: TranslateBackend;
      modelId?: string;
    }) => api.jobs.startTranslate(vars.file, vars.source, vars.target, vars.backend, vars.modelId),
    onSuccess: (job: BgJob) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.setQueryData(["jobs", job.id], job);
    },
  });
}

export function useStartConvertJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { file: File; ocrLanguage?: string }) =>
      api.jobs.startConvert(vars.file, vars.ocrLanguage),
    onSuccess: (job: BgJob) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.setQueryData(["jobs", job.id], job);
    },
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.jobs.cancel(id),
    onSuccess: (job: BgJob) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.setQueryData(["jobs", job.id], job);
    },
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.jobs.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
