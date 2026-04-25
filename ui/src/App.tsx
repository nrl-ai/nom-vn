import { useEffect, useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster, toast } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { SpacesSidebar } from "@/components/spaces/SpacesSidebar";
import { ChatThread } from "@/components/chat/ChatThread";
import { MaterialsDrawer } from "@/components/materials/MaterialsDrawer";
import { useHealth, useSpaces } from "@/api/queries";

const ACTIVE_SPACE_KEY = "nom:active-space";

export default function App() {
  // Raw localStorage value — may point at a deleted space.
  const [storedSpaceId, setStoredSpaceId] = useState<string | null>(() => {
    return localStorage.getItem(ACTIVE_SPACE_KEY);
  });
  const spacesQ = useSpaces();
  const healthQ = useHealth();

  // Persist active space across reloads.
  useEffect(() => {
    if (storedSpaceId) localStorage.setItem(ACTIVE_SPACE_KEY, storedSpaceId);
    else localStorage.removeItem(ACTIVE_SPACE_KEY);
  }, [storedSpaceId]);

  // Validated active space — null until spacesQ confirms the stored id
  // still exists. Children receive null during the brief window before
  // spaces load, so they don't fire requests against a stale id and
  // generate a 404 in the console. (Real bug from session — happened
  // when /tmp/nom-demo got wiped between restarts.)
  const activeSpaceId = useMemo(() => {
    if (!storedSpaceId) return null;
    if (!spacesQ.data) return null; // waiting for confirmation
    return spacesQ.data.some((s) => s.id === storedSpaceId) ? storedSpaceId : null;
  }, [storedSpaceId, spacesQ.data]);

  // If validation says the stored id is dead, clear localStorage too so
  // we don't keep re-checking it on every render.
  useEffect(() => {
    if (storedSpaceId && spacesQ.data && activeSpaceId === null) {
      setStoredSpaceId(null);
    }
  }, [storedSpaceId, spacesQ.data, activeSpaceId]);

  // Surface query errors as toasts (sparingly — one per unique message).
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

  return (
    <TooltipProvider delayDuration={120}>
      <AppShell
        modelName={healthQ.data?.llm ?? undefined}
        onHome={() => setStoredSpaceId(null)}
        sources={
          <SpacesSidebar
            activeSpaceId={activeSpaceId}
            onSelect={(id) => setStoredSpaceId(id || null)}
          />
        }
        studio={<MaterialsDrawer spaceId={activeSpaceId} />}
      >
        <ChatThread
          spaceId={activeSpaceId}
          spaceName={activeSpace?.name ?? null}
          hasMaterials={hasMaterials}
        />
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
