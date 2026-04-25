import { useState } from "react";
import { Plus, Trash2, Folder, Loader2 } from "lucide-react";
import { useSpaces, useCreateSpace, useDeleteSpace } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { Space } from "@/api/types";

interface Props {
  activeSpaceId: string | null;
  onSelect: (id: string) => void;
}

export function SpacesSidebar({ activeSpaceId, onSelect }: Props) {
  const spacesQ = useSpaces();
  const create = useCreateSpace();
  const del = useDeleteSpace();
  const [openCreate, setOpenCreate] = useState(false);
  const [draft, setDraft] = useState("");

  const handleCreate = async () => {
    const name = draft.trim();
    if (!name) return;
    try {
      const space = await create.mutateAsync(name);
      setDraft("");
      setOpenCreate(false);
      onSelect(space.id);
    } catch {
      // The mutation's error state surfaces below.
    }
  };

  const handleDelete = async (e: React.MouseEvent, space: Space) => {
    e.stopPropagation();
    if (!confirm(`Delete space “${space.name}”? This removes all materials.`)) return;
    await del.mutateAsync(space.id);
    if (activeSpaceId === space.id) onSelect("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between px-4 pb-2 pt-4">
        <h2 className="section-mark">§ spaces</h2>
        <Dialog open={openCreate} onOpenChange={setOpenCreate}>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Create space">
              <Plus size={14} />
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New space</DialogTitle>
              <DialogDescription>
                A space groups related materials. You ask questions across one space at a time.
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              placeholder="e.g. Hợp đồng 2026"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
              className="vn-text"
            />
            {create.isError && (
              <div className="mt-2 text-xs text-danger">{(create.error as Error).message}</div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <DialogClose asChild>
                <Button variant="ghost" size="sm">
                  Cancel
                </Button>
              </DialogClose>
              <Button
                variant="accent"
                size="sm"
                onClick={handleCreate}
                disabled={!draft.trim() || create.isPending}
              >
                {create.isPending && <Loader2 size={12} className="animate-spin" />}
                Create
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-2 pb-4">
          {spacesQ.isLoading && (
            <div className="px-3 py-6 text-xs italic text-ink-mute">Loading…</div>
          )}
          {spacesQ.isError && (
            <div className="px-3 py-3 text-xs text-danger">Failed to load spaces.</div>
          )}
          {spacesQ.data && spacesQ.data.length === 0 && (
            <EmptySpaces onClickCreate={() => setOpenCreate(true)} />
          )}
          {spacesQ.data?.map((s) => (
            <SpaceItem
              key={s.id}
              space={s}
              active={s.id === activeSpaceId}
              onSelect={() => onSelect(s.id)}
              onDelete={(e) => handleDelete(e, s)}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

function SpaceItem({
  space,
  active,
  onSelect,
  onDelete,
}: {
  space: Space;
  active: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "group mb-1 flex w-full items-center gap-2 border px-3 py-2 text-left transition-colors",
        active
          ? "border-ink bg-paper shadow-editorial-soft"
          : "border-transparent hover:bg-bg-soft",
      )}
    >
      <Folder size={14} className={cn("shrink-0", active ? "text-accent" : "text-ink-mute")} />
      <div className="min-w-0 flex-1">
        <div className="vn-text truncate text-sm font-medium text-ink">{space.name}</div>
        <div className="mt-0.5 font-mono text-[10px] text-ink-mute">
          {space.n_materials} {space.n_materials === 1 ? "material" : "materials"}
        </div>
      </div>
      <button
        onClick={onDelete}
        className="p-1 text-ink-mute opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
        aria-label="Delete space"
      >
        <Trash2 size={12} />
      </button>
    </button>
  );
}

function EmptySpaces({ onClickCreate }: { onClickCreate: () => void }) {
  return (
    <div className="px-3 py-8 text-center">
      <p className="mb-3 text-xs italic text-ink-mute">
        No spaces yet. A space holds documents you ask questions of.
      </p>
      <Button variant="outline" size="sm" onClick={onClickCreate}>
        <Plus size={12} /> Create one
      </Button>
    </div>
  );
}
