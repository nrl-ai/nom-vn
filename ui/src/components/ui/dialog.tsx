import * as React from "react";
import * as RD from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = RD.Root;
export const DialogTrigger = RD.Trigger;
export const DialogClose = RD.Close;

const DialogPortal = RD.Portal;

export const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof RD.Overlay>,
  React.ComponentPropsWithoutRef<typeof RD.Overlay>
>(({ className, ...props }, ref) => (
  <RD.Overlay
    ref={ref}
    className={cn("fixed inset-0 z-40 animate-dialog-in bg-ink/40 backdrop-blur-[2px]", className)}
    {...props}
  />
));
DialogOverlay.displayName = "DialogOverlay";

export const DialogContent = React.forwardRef<
  React.ElementRef<typeof RD.Content>,
  React.ComponentPropsWithoutRef<typeof RD.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <RD.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 animate-dialog-in border border-ink bg-paper p-6 shadow-editorial",
        className,
      )}
      {...props}
    >
      {children}
      <RD.Close className="absolute right-3 top-3 p-1 text-ink-mute hover:text-ink">
        <X size={16} />
        <span className="sr-only">Close</span>
      </RD.Close>
    </RD.Content>
  </DialogPortal>
));
DialogContent.displayName = "DialogContent";

export const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("mb-4 flex flex-col gap-1", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof RD.Title>,
  React.ComponentPropsWithoutRef<typeof RD.Title>
>(({ className, ...props }, ref) => (
  <RD.Title
    ref={ref}
    className={cn("font-display text-lg font-semibold tracking-tight", className)}
    {...props}
  />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = React.forwardRef<
  React.ElementRef<typeof RD.Description>,
  React.ComponentPropsWithoutRef<typeof RD.Description>
>(({ className, ...props }, ref) => (
  <RD.Description ref={ref} className={cn("text-sm text-ink-soft", className)} {...props} />
));
DialogDescription.displayName = "DialogDescription";
