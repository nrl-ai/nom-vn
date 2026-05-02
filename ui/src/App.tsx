import { useEffect, useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster, toast } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { Sidebar } from "@/components/layout/Sidebar";
import type { TaskKey } from "@/components/layout/tasks";
import { ChatThread } from "@/components/chat/ChatThread";
import { MaterialsDrawer } from "@/components/materials/MaterialsDrawer";
import { DiacriticPage } from "@/components/tools/pages/DiacriticPage";
import { TokenizePage } from "@/components/tools/pages/TokenizePage";
import { NormalizePage } from "@/components/tools/pages/NormalizePage";
import { StripPage } from "@/components/tools/pages/StripPage";
import { ApiPage } from "@/components/tools/pages/ApiPage";
import { SettingsPage } from "@/components/tools/pages/SettingsPage";
import { useHealth, useSpaces } from "@/api/queries";

const ACTIVE_SPACE_KEY = "nom:active-space";
const ACTIVE_TASK_KEY = "nom:active-task";

const TASK_KEYS: ReadonlySet<TaskKey> = new Set([
  "chat",
  "diacritic",
  "tokenize",
  "normalize",
  "strip",
  "api",
  "settings",
]);

function loadTask(): TaskKey {
  try {
    const raw = localStorage.getItem(ACTIVE_TASK_KEY);
    if (raw && TASK_KEYS.has(raw as TaskKey)) return raw as TaskKey;
  } catch {
    /* ignore */
  }
  return "chat";
}

export default function App() {
  const [activeTask, setActiveTask] = useState<TaskKey>(loadTask);
  const [storedSpaceId, setStoredSpaceId] = useState<string | null>(() => {
    return localStorage.getItem(ACTIVE_SPACE_KEY);
  });
  const spacesQ = useSpaces();
  const healthQ = useHealth();

  // Persist active task across reloads.
  useEffect(() => {
    try {
      localStorage.setItem(ACTIVE_TASK_KEY, activeTask);
    } catch {
      /* ignore */
    }
  }, [activeTask]);

  // Persist active space across reloads.
  useEffect(() => {
    if (storedSpaceId) localStorage.setItem(ACTIVE_SPACE_KEY, storedSpaceId);
    else localStorage.removeItem(ACTIVE_SPACE_KEY);
  }, [storedSpaceId]);

  // Validated active space — null until spacesQ confirms the stored id
  // still exists. Children receive null during the brief window before
  // spaces load, so they don't fire requests against a stale id and
  // generate a 404 in the console.
  const activeSpaceId = useMemo(() => {
    if (!storedSpaceId) return null;
    if (!spacesQ.data) return null;
    return spacesQ.data.some((s) => s.id === storedSpaceId) ? storedSpaceId : null;
  }, [storedSpaceId, spacesQ.data]);

  useEffect(() => {
    if (storedSpaceId && spacesQ.data && activeSpaceId === null) {
      setStoredSpaceId(null);
    }
  }, [storedSpaceId, spacesQ.data, activeSpaceId]);

  useEffect(() => {
    if (spacesQ.isError) {
      toast.error(`Could not load spaces: ${(spacesQ.error as Error).message}`);
    }
  }, [spacesQ.isError, spacesQ.error]);

  const activeSpace = useMemo(
    () => spacesQ.data?.find((s) => s.id === activeSpaceId) ?? null,
    [spacesQ.data, activeSpaceId],
  );

  const hasMaterials = (activeSpace?.n_materials ?? 0) > 0;

  // Chat is the only stateful task — its layout adds a right-side
  // materials studio pane. Tools render full-bleed in the center.
  const isChat = activeTask === "chat";

  let centerPane: React.ReactNode;
  switch (activeTask) {
    case "chat":
      centerPane = (
        <ChatThread
          spaceId={activeSpaceId}
          spaceName={activeSpace?.name ?? null}
          hasMaterials={hasMaterials}
        />
      );
      break;
    case "diacritic":
      centerPane = <DiacriticPage />;
      break;
    case "tokenize":
      centerPane = <TokenizePage />;
      break;
    case "normalize":
      centerPane = <NormalizePage />;
      break;
    case "strip":
      centerPane = <StripPage />;
      break;
    case "api":
      centerPane = <ApiPage />;
      break;
    case "settings":
      centerPane = <SettingsPage />;
      break;
  }

  return (
    <TooltipProvider delayDuration={120}>
      <AppShell
        modelName={healthQ.data?.llm ?? undefined}
        mode={isChat ? "chat" : "tool"}
        onHome={() => setActiveTask("chat")}
        onSettings={() => setActiveTask("settings")}
        onApi={() => setActiveTask("api")}
        sidebar={
          <Sidebar
            activeTask={activeTask}
            onTaskChange={setActiveTask}
            activeSpaceId={activeSpaceId}
            onSpaceSelect={(id) => setStoredSpaceId(id || null)}
          />
        }
        studio={isChat ? <MaterialsDrawer spaceId={activeSpaceId} /> : undefined}
      >
        {centerPane}
      </AppShell>
      <Toaster
        position="bottom-right"
        toastOptions={{
          unstyled: false,
          className:
            "!bg-paper !border !border-ink !text-ink !rounded-none !shadow-editorial-soft !font-sans",
        }}
      />
    </TooltipProvider>
  );
}
