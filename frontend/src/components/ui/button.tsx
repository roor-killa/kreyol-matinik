import * as React from "react";
import { Slot }   from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-2xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-700 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:  "bg-cyan-700 text-white shadow-sm hover:bg-cyan-600",
        outline:  "border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-800",
        ghost:    "hover:bg-zinc-100 text-zinc-700",
        destructive: "bg-red-500 text-white hover:bg-red-600",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm:      "h-8 px-3 text-xs",
        lg:      "h-12 px-6",
        icon:    "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size:    "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
