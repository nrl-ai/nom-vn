import { useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Menu, FolderOpen, X } from "lucide-react";
import { Header } from "./Header";
import { Button } from "@/components/ui/button";

// Three-pane shell — Sources | Chat | Studio — modeled on NotebookLM.
// On mobile (<lg) the side panes collapse into floating sheets toggled
// from the header. The center pane (chat) is the only always-visible
// region — that's the room you're "in" in this app.

interface AppShellProps {
  modelName?: string;
  sources: React.ReactNode;
  studio: React.ReactNode;
  children: React.ReactNode; // chat thread
  onHome?: () => void;
}

export function AppShell({ modelName, sources, studio, children, onHome }: AppShellProps) {
  const [showSources, setShowSources] = useState(false);
  const [showStudio, setShowStudio] = useState(false);

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="absolute left-2 top-2 z-30 flex gap-1 lg:hidden">
        <Button
          variant="outline"
          size="icon"
          onClick={() => setShowSources((v) => !v)}
          aria-label="Toggle sources"
          className="h-8 w-8 bg-bg"
        >
          {showSources ? <X size={14} /> : <Menu size={14} />}
        </Button>
      </div>
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

      <Header modelName={modelName} onHome={onHome} />

      {/* Desktop layout: 3-pane resizable */}
      <div className="hidden min-h-0 flex-1 lg:block">
        <PanelGroup direction="horizontal">
          <Panel defaultSize={20} minSize={14} maxSize={32}>
            <aside className="h-full overflow-hidden border-r border-line bg-bg">{sources}</aside>
          </Panel>
          <PanelResizeHandle className="w-px bg-line" />
          <Panel defaultSize={55} minSize={30}>
            <main className="h-full overflow-hidden">{children}</main>
          </Panel>
          <PanelResizeHandle className="w-px bg-line" />
          <Panel defaultSize={25} minSize={18} maxSize={36}>
            <aside className="h-full overflow-hidden border-l border-line bg-bg">{studio}</aside>
          </Panel>
        </PanelGroup>
      </div>

      {/* Mobile layout: chat full-bleed, drawers slide in */}
      <div className="relative min-h-0 flex-1 lg:hidden">
        <main className="h-full overflow-hidden">{children}</main>
        {showSources && (
          <aside className="absolute inset-y-0 left-0 z-20 w-80 max-w-[88vw] animate-fade-in overflow-hidden border-r border-ink bg-bg shadow-editorial-soft">
            {sources}
          </aside>
        )}
        {showStudio && (
          <aside className="absolute inset-y-0 right-0 z-20 w-80 max-w-[88vw] animate-fade-in overflow-hidden border-l border-ink bg-bg shadow-editorial-soft">
            {studio}
          </aside>
        )}
      </div>
    </div>
  );
}
