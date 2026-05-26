import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-stone-800 bg-stone-950 px-3 py-1 text-sm text-stone-200 shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-stone-400 placeholder:text-stone-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-600/50 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
