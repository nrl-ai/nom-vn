import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsPage } from "../pages/SettingsPage";
import { getAuthToken, setAuthToken } from "@/api/client";

function renderWithQuery(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const HEALTH_OPEN = {
  status: "ok",
  version: "0.2.30",
  store: "MemoryStore",
  llm: "ollama",
  llm_class: "Ollama",
  embedder: "FakeEmbedder",
  ocr_available: true,
  auth_required: false,
};

const HEALTH_AUTH = { ...HEALTH_OPEN, auth_required: true };

const BACKENDS_RES = {
  active: { name: "ollama", class: "Ollama", model: "qwen3:8b" },
  available: [
    {
      id: "ollama",
      label: "Ollama (local daemon)",
      kind: "local-http",
      available: true,
      model_hint: "qwen3:8b",
      needs: [],
    },
    {
      id: "huggingface",
      label: "HuggingFace transformers (in-process)",
      kind: "local-inproc",
      available: false,
      model_hint: "<owner>/<repo>",
      needs: ['pip install "nom-vn[llm-hf]"'],
    },
    {
      id: "llamacpp-python",
      label: "llama.cpp via llama-cpp-python",
      kind: "local-inproc",
      available: true,
      model_hint: "GGUF path · or hf:<repo>:<filename>",
      needs: [],
    },
  ],
};

function mockFetch(byPath: Record<string, unknown>) {
  return vi.fn(async (input: string) => {
    const path = typeof input === "string" ? input : input;
    const body = byPath[path] ?? {};
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("SettingsPage", () => {
  beforeEach(() => {
    // jsdom's localStorage may not implement .clear(); enumerate and remove.
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k) localStorage.removeItem(k);
    }
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders server health (LLM, embedder, OCR, auth state)", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_OPEN, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    await waitFor(() => expect(screen.getByText("MemoryStore")).toBeInTheDocument());
    expect(screen.getByText(/đã tắt \(API công khai\)/)).toBeInTheDocument();
    // Embedder name is unique enough to be a precise probe.
    expect(screen.getByText("FakeEmbedder")).toBeInTheDocument();
  });

  it("shows auth=ON badge when server requires authentication", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_AUTH, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByText(/bắt buộc \(NOM_AUTH_TOKEN\)/)).toBeInTheDocument(),
    );
    expect(screen.getByText("ON")).toBeInTheDocument();
  });

  it("save button persists the bearer token to localStorage", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_OPEN, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    const input = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    await userEvent.type(input, "secret-xyz");
    await userEvent.click(screen.getByRole("button", { name: /^lưu$/i }));
    await waitFor(() => expect(getAuthToken()).toBe("secret-xyz"));
  });

  it("clearing the token field removes it from localStorage", async () => {
    setAuthToken("pre-existing");
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_OPEN, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    const input = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe("pre-existing"));
    await userEvent.clear(input);
    await userEvent.click(screen.getByRole("button", { name: /^lưu$/i }));
    await waitFor(() => expect(getAuthToken()).toBeNull());
  });

  it("backend picker buttons reflect availability and update the launch command", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_OPEN, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    // Wait for backend probe to land + render the picker buttons.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Ollama \(local daemon\)/ })).toBeInTheDocument(),
    );
    // HF backend lists `needs` because available=false.
    expect(screen.getByText(/nom-vn\[llm-hf\]/)).toBeInTheDocument();
    // Clicking llama-cpp-python (available) updates the launch command region.
    await userEvent.click(screen.getByRole("button", { name: /llama-cpp-python/ }));
    await waitFor(() =>
      expect(
        screen.getAllByText((_, el) =>
          (el?.textContent ?? "").includes("NOM_LLM_BACKEND=llamacpp-python"),
        ).length,
      ).toBeGreaterThan(0),
    );
  });

  it("top_k slider writes to localStorage on change", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/health": HEALTH_OPEN, "/api/llm/backends": BACKENDS_RES }),
    );
    renderWithQuery(<SettingsPage />);
    const slider = screen.getByLabelText(/default top_k/i) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "12" } });
    expect(localStorage.getItem("nom:chat:top-k")).toBe("12");
  });
});
