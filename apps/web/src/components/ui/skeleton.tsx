import type React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-surface-user border border-border/50 dark:bg-white/[0.06]",
        className
      )}
      {...props}
    />
  );
}
