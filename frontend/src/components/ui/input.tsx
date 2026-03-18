import * as React from "react";
import { cn }      from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm",
        "placeholder:text-zinc-400",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-700",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
