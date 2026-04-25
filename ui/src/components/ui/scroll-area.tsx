import * as React from "react";
import * as SA from "@radix-ui/react-scroll-area";
import { cn } from "@/lib/utils";

export const ScrollArea = React.forwardRef<
  React.ElementRef<typeof SA.Root>,
  React.ComponentPropsWithoutRef<typeof SA.Root>
>(({ className, children, ...props }, ref) => (
  <SA.Root ref={ref} className={cn("relative overflow-hidden", className)} {...props}>
    <SA.Viewport className="h-full w-full">{children}</SA.Viewport>
    <SA.Scrollbar
      orientation="vertical"
      className="flex w-2 touch-none select-none bg-transparent p-0.5 transition-colors"
    >
      <SA.Thumb className="relative flex-1 bg-ink/30 hover:bg-ink/50" />
    </SA.Scrollbar>
    <SA.Corner />
  </SA.Root>
));
ScrollArea.displayName = "ScrollArea";
