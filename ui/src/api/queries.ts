import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { api } from "./client";
import type { Material, Space } from "./types";

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
