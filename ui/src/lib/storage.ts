import { useCallback, useEffect, useState } from "react";
import type { ChatMessage } from "@/api/types";

// Per-space chat history in localStorage. v0.2.x has no server-side
// message persistence — that's the next architecture delta. When it
// lands, swap this hook's body for a useQuery against /api/messages
// and the rest of the UI doesn't change.

const STORAGE_PREFIX = "nom:chat:";

export function useChatHistory(spaceId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    if (!spaceId) {
      setMessages([]);
      return;
    }
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + spaceId);
      setMessages(raw ? (JSON.parse(raw) as ChatMessage[]) : []);
    } catch {
      setMessages([]);
    }
  }, [spaceId]);

  const persist = useCallback(
    (next: ChatMessage[]) => {
      if (!spaceId) return;
      try {
        localStorage.setItem(STORAGE_PREFIX + spaceId, JSON.stringify(next));
      } catch {
        // localStorage may be full or disabled — silently degrade.
      }
    },
    [spaceId],
  );

  const append = useCallback(
    (msg: ChatMessage) => {
      setMessages((prev) => {
        const next = [...prev, msg];
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const update = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) => {
        const next = prev.map((m) => (m.id === id ? { ...m, ...patch } : m));
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const clear = useCallback(() => {
    setMessages([]);
    if (spaceId) localStorage.removeItem(STORAGE_PREFIX + spaceId);
  }, [spaceId]);

  return { messages, append, update, clear };
}
