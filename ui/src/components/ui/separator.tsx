import * as React from "react";
import * as SP from "@radix-ui/react-separator";
import { cn } from "@/lib/utils";

export const Separator = React.forwardRef<
  React.ElementRef<typeof SP.Root>,
  React.ComponentPropsWithoutRef<typeof SP.Root>
>(({ className, orientation = "horizontal", decorative = true, ...props }, ref) => (
  <SP.Root
    ref={ref}
    decorative={decorative}
    orientation={orientation}
    className={cn(
      "bg-line",
      orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
      className,
    )}
    {...props}
  />
));
Separator.displayName = "Separator";
