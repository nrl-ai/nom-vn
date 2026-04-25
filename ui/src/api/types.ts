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
