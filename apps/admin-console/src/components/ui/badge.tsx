import { type HTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-amber-600/50 focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-stone-800 text-stone-300 hover:bg-stone-700",
        success:
          "border-transparent bg-emerald-900/60 text-emerald-300 hover:bg-emerald-800/60",
        warning:
          "border-transparent bg-amber-900/60 text-amber-300 hover:bg-amber-800/60",
        error:
          "border-transparent bg-red-900/60 text-red-300 hover:bg-red-800/60",
        info: "border-transparent bg-blue-900/60 text-blue-300 hover:bg-blue-800/60",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(badgeVariants({ variant }), className)}
        {...props}
      />
    );
  }
);
Badge.displayName = "Badge";

export { Badge, badgeVariants };
