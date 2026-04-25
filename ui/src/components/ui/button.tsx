// ShadCN Button — adapted to our editorial design tokens.
// Variants follow the cream/ink/orange palette; sharp corners (no
// border-radius); editorial hard shadow on the primary action.

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2",
  {
    variants: {
      variant: {
        primary:
          "bg-ink text-bg hover:bg-ink-soft active:translate-x-[1px] active:translate-y-[1px]",
        accent:
          "bg-accent text-accent-ink hover:bg-accent-soft hover:text-accent-ink active:translate-x-[1px] active:translate-y-[1px]",
        ghost: "bg-transparent text-ink hover:bg-bg-soft",
        outline: "bg-paper text-ink border border-ink hover:bg-bg-soft",
        danger: "bg-paper text-danger border border-danger hover:bg-danger hover:text-paper",
      },
      size: {
        sm: "h-7 px-2.5 text-xs",
        md: "h-9 px-4 text-sm",
        lg: "h-11 px-5 text-sm",
        icon: "h-9 w-9 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
