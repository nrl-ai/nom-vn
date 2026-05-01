import { TaskNav } from "./TaskNav";
import type { TaskKey } from "./tasks";
import { SpacesSidebar } from "@/components/spaces/SpacesSidebar";

interface Props {
  activeTask: TaskKey;
  onTaskChange: (k: TaskKey) => void;
  activeSpaceId: string | null;
  onSpaceSelect: (id: string) => void;
}

// Combined left rail: task switcher always on top, spaces list visible only
// when the chat task is active. Spaces are scoped to the chat task — the
// stateless tool tasks don't reference them, so showing them under another
// task would be visual noise.
export function Sidebar({ activeTask, onTaskChange, activeSpaceId, onSpaceSelect }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className={activeTask === "chat" ? "max-h-[42%] shrink-0 overflow-hidden" : "flex-1"}>
        <TaskNav active={activeTask} onSelect={onTaskChange} />
      </div>
      {activeTask === "chat" && (
        <div className="min-h-0 flex-1 border-t border-line">
          <SpacesSidebar activeSpaceId={activeSpaceId} onSelect={onSpaceSelect} />
        </div>
      )}
    </div>
  );
}
