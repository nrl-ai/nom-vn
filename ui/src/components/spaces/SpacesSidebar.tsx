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
    if (!confirm(`Xoá không gian “${space.name}”? Toàn bộ tài liệu đi kèm sẽ bị xoá.`)) return;
    await del.mutateAsync(space.id);
    if (activeSpaceId === space.id) onSelect("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between px-3 pb-1.5 pt-3">
        <h2 className="section-mark">§ không gian</h2>
        <Dialog open={openCreate} onOpenChange={setOpenCreate}>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Tạo không gian">
              <Plus size={14} />
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Không gian mới</DialogTitle>
              <DialogDescription>
                Một không gian gom những tài liệu liên quan. Mỗi câu hỏi chỉ truy hồi trong phạm vi
                một không gian.
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              placeholder="VD: Hợp đồng 2026"
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
                  Huỷ
                </Button>
              </DialogClose>
              <Button
                variant="accent"
                size="sm"
                onClick={handleCreate}
                disabled={!draft.trim() || create.isPending}
              >
                {create.isPending && <Loader2 size={12} className="animate-spin" />}
                Tạo
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-1.5 pb-3">
          {spacesQ.isLoading && (
            <div className="px-3 py-5 text-xs italic text-ink-mute">Đang tải…</div>
          )}
          {spacesQ.isError && (
            <div className="px-3 py-3 text-xs text-danger">
              Không tải được danh sách không gian.
            </div>
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
        "group flex w-full items-center gap-2 border-l-2 py-1.5 pl-2.5 pr-2 text-left transition-colors",
        active ? "border-l-accent bg-accent-wash" : "border-l-transparent hover:bg-bg-soft",
      )}
    >
      <Folder size={13} className={cn("shrink-0", active ? "text-accent" : "text-ink-mute")} />
      <div className="min-w-0 flex-1">
        <div
          className={cn(
            "vn-text truncate text-[13px] leading-tight",
            active ? "font-semibold text-ink" : "font-medium text-ink-soft",
          )}
        >
          {space.name}
        </div>
        <div className="meta truncate">{space.n_materials} tài liệu</div>
      </div>
      <button
        onClick={onDelete}
        className="p-1 text-ink-mute opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
        aria-label="Xoá không gian"
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
        Chưa có không gian nào. Một không gian giữ các tài liệu mà bạn muốn hỏi đáp.
      </p>
      <Button variant="outline" size="sm" onClick={onClickCreate}>
        <Plus size={12} /> Tạo không gian
      </Button>
    </div>
  );
}
