import { useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Menu, FolderOpen, X } from "lucide-react";
import { Header } from "./Header";
import { Button } from "@/components/ui/button";

// Layout modes:
// - "chat" → four-pane (task-nav | spaces | chat | studio). Spaces is a
//   second left rail so the task switcher stays a slim icon-list while
//   spaces gets its own breathing room.
// - "tool" → two-pane (task-nav | tool page). Stateless tools have no
//   side concept of materials, so spaces + studio are hidden.
//
// On narrow viewports (<xl, < 1280 px) the side panes collapse into floating sheets
// toggled from the header. The center pane (work area) is the only
// always-visible region — that's the room you're "in" in this app.
// On mobile the spaces drawer rides along with the main sidebar drawer
// (stacked) so users get one toggle, not two.

interface AppShellProps {
  modelName?: string;
  /** Slim left rail — TaskNav. Always shown. */
  sidebar: React.ReactNode;
  /** Second left rail — spaces list. Only used in chat mode. */
  spacesSidebar?: React.ReactNode;
  /** Right pane (only used in chat mode). */
  studio?: React.ReactNode;
  /** Center pane — chat thread or active tool page. */
  children: React.ReactNode;
  /** Layout topology to apply. */
  mode?: "chat" | "tool";
  onHome?: () => void;
  onSettings?: () => void;
  onApi?: () => void;
}

export function AppShell({
  modelName,
  sidebar,
  spacesSidebar,
  studio,
  children,
  mode = "chat",
  onHome,
  onSettings,
  onApi,
}: AppShellProps) {
  const [showSidebar, setShowSidebar] = useState(false);
  const [showStudio, setShowStudio] = useState(false);

  const showSpacesPane = mode === "chat" && !!spacesSidebar;
  const showStudioPane = mode === "chat" && !!studio;

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="absolute left-2 top-2 z-30 flex gap-1 xl:hidden">
        <Button
          variant="outline"
          size="icon"
          onClick={() => setShowSidebar((v) => !v)}
          aria-label="Toggle sidebar"
          className="h-8 w-8 bg-bg"
        >
          {showSidebar ? <X size={14} /> : <Menu size={14} />}
        </Button>
      </div>
      {showStudioPane && (
        <div className="absolute right-2 top-2 z-30 flex gap-1 xl:hidden">
          <Button
            variant="outline"
            size="icon"
            onClick={() => setShowStudio((v) => !v)}
            aria-label="Toggle studio"
            className="h-8 w-8 bg-bg"
          >
            {showStudio ? <X size={14} /> : <FolderOpen size={14} />}
          </Button>
        </div>
      )}

      <Header
        modelName={modelName}
        onHome={onHome}
        onSettings={onSettings}
        onApi={onApi}
        reserveRightOnMobile={showStudioPane}
      />

      {/* Desktop layout: resizable panels.
       *
       * Stable Panel `id`s are *required* — react-resizable-panels uses
       * them to track sizes when the spaces / studio panels conditionally
       * mount. Without IDs the library can't reconcile sizes on remount
       * and the resize handles act erratic.
       *
       * `autoSaveId` persists the user's chosen split per layout key
       * across reloads. Three keys keep state separate by topology so
       * tool-mode sizes don't bleed into chat mode and vice-versa.
       *
       * `hitAreaMargins` widens the grab zone to ~6 px each side without
       * widening the visible 1 px line — the visible line stays editorial
       * thin, but the cursor target is finger-friendly. */}
      <div className="hidden min-h-0 flex-1 xl:block">
        <PanelGroup
          direction="horizontal"
          autoSaveId={
            mode === "chat"
              ? showStudioPane
                ? "nom:layout:chat"
                : "nom:layout:chat-no-studio"
              : "nom:layout:tool"
          }
        >
          <Panel
            id="nav"
            order={1}
            defaultSize={showSpacesPane ? 14 : 18}
            minSize={12}
            maxSize={24}
          >
            <aside className="h-full overflow-hidden border-r border-line bg-bg">{sidebar}</aside>
          </Panel>
          {showSpacesPane && (
            <>
              <PanelResizeHandle className="w-px bg-line" hitAreaMargins={{ coarse: 8, fine: 6 }} />
              <Panel id="spaces" order={2} defaultSize={18} minSize={14} maxSize={28}>
                <aside className="h-full overflow-hidden border-r border-line bg-bg">
                  {spacesSidebar}
                </aside>
              </Panel>
            </>
          )}
          <PanelResizeHandle className="w-px bg-line" hitAreaMargins={{ coarse: 8, fine: 6 }} />
          <Panel
            id="main"
            order={3}
            defaultSize={
              showSpacesPane && showStudioPane ? 43 : showSpacesPane ? 68 : showStudioPane ? 57 : 82
            }
            minSize={30}
          >
            <main className="h-full overflow-hidden">{children}</main>
          </Panel>
          {showStudioPane && (
            <>
              <PanelResizeHandle className="w-px bg-line" hitAreaMargins={{ coarse: 8, fine: 6 }} />
              <Panel id="studio" order={4} defaultSize={25} minSize={18} maxSize={36}>
                <aside className="h-full overflow-hidden border-l border-line bg-bg">
                  {studio}
                </aside>
              </Panel>
            </>
          )}
        </PanelGroup>
      </div>

      {/* Mobile layout: center full-bleed, drawers slide in.
       * The main sidebar drawer stacks TaskNav + SpacesSidebar so a
       * single toggle exposes both. */}
      <div className="relative min-h-0 flex-1 xl:hidden">
        <main className="h-full overflow-hidden">{children}</main>
        {showSidebar && (
          <aside className="absolute inset-y-0 left-0 z-20 flex w-80 max-w-[88vw] animate-fade-in flex-col overflow-hidden border-r border-ink bg-bg shadow-editorial-soft">
            <div className={showSpacesPane ? "max-h-[42%] shrink-0 overflow-hidden" : "flex-1"}>
              {sidebar}
            </div>
            {showSpacesPane && (
              <div className="min-h-0 flex-1 border-t border-line">{spacesSidebar}</div>
            )}
          </aside>
        )}
        {showStudioPane && showStudio && (
          <aside className="absolute inset-y-0 right-0 z-20 w-80 max-w-[88vw] animate-fade-in overflow-hidden border-l border-ink bg-bg shadow-editorial-soft">
            {studio}
          </aside>
        )}
      </div>
    </div>
  );
}
