import { useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Menu, FolderOpen, X } from "lucide-react";
import { Header } from "./Header";
import { Button } from "@/components/ui/button";

// Layout modes:
// - "chat" → three-pane (sources | chat | studio), the legacy NotebookLM-ish layout.
// - "tool" → two-pane (task-nav | tool page); studio pane is hidden because
//   stateless tools don't have a side concept of materials.
//
// On mobile (<lg) the side panes always collapse into floating sheets toggled
// from the header. The center pane (work area) is the only always-visible
// region — that's the room you're "in" in this app.

interface AppShellProps {
  modelName?: string;
  /** Always-shown sidebar — TaskNav or, for chat mode, the spaces list. */
  sidebar: React.ReactNode;
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
  studio,
  children,
  mode = "chat",
  onHome,
  onSettings,
  onApi,
}: AppShellProps) {
  const [showSidebar, setShowSidebar] = useState(false);
  const [showStudio, setShowStudio] = useState(false);

  const showStudioPane = mode === "chat" && !!studio;

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="absolute left-2 top-2 z-30 flex gap-1 lg:hidden">
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
        <div className="absolute right-2 top-2 z-30 flex gap-1 lg:hidden">
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

      <Header modelName={modelName} onHome={onHome} onSettings={onSettings} onApi={onApi} />

      {/* Desktop layout: resizable panels */}
      <div className="hidden min-h-0 flex-1 lg:block">
        <PanelGroup direction="horizontal">
          <Panel defaultSize={mode === "tool" ? 18 : 20} minSize={14} maxSize={32}>
            <aside className="h-full overflow-hidden border-r border-line bg-bg">{sidebar}</aside>
          </Panel>
          <PanelResizeHandle className="w-px bg-line" />
          <Panel defaultSize={showStudioPane ? 55 : 82} minSize={30}>
            <main className="h-full overflow-hidden">{children}</main>
          </Panel>
          {showStudioPane && (
            <>
              <PanelResizeHandle className="w-px bg-line" />
              <Panel defaultSize={25} minSize={18} maxSize={36}>
                <aside className="h-full overflow-hidden border-l border-line bg-bg">
                  {studio}
                </aside>
              </Panel>
            </>
          )}
        </PanelGroup>
      </div>

      {/* Mobile layout: center full-bleed, drawers slide in */}
      <div className="relative min-h-0 flex-1 lg:hidden">
        <main className="h-full overflow-hidden">{children}</main>
        {showSidebar && (
          <aside className="absolute inset-y-0 left-0 z-20 w-80 max-w-[88vw] animate-fade-in overflow-hidden border-r border-ink bg-bg shadow-editorial-soft">
            {sidebar}
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
