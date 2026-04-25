import * as React from "react";
import * as RT from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

export const TooltipProvider = RT.Provider;
export const Tooltip = RT.Root;
export const TooltipTrigger = RT.Trigger;

export const TooltipContent = React.forwardRef<
  React.ElementRef<typeof RT.Content>,
  React.ComponentPropsWithoutRef<typeof RT.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <RT.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 max-w-sm animate-fade-in bg-ink px-3 py-2 text-xs text-bg shadow-editorial-soft",
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = "TooltipContent";
