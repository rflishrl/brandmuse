import type React from "react";
import { Skeleton } from "@/components/ui/skeleton";

export const PageLoadingFallback: React.FC = () => {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Memuat konten halaman"
      className="w-full flex flex-col gap-6 animate-in fade-in duration-150"
    >
      {/* Header Skeleton */}
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48 max-w-[60%]" />
        <Skeleton className="h-4 w-96 max-w-[85%]" />
      </div>

      {/* Main Content Area Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Skeleton className="h-44 w-full rounded-2xl" />
        <Skeleton className="h-44 w-full rounded-2xl hidden md:block" />
        <Skeleton className="h-44 w-full rounded-2xl hidden lg:block" />
      </div>

      {/* Detail Block Skeleton */}
      <div className="p-6 rounded-2xl bg-surface border border-border flex flex-col gap-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-24 rounded-lg" />
          <Skeleton className="h-8 w-24 rounded-lg" />
        </div>
      </div>
    </div>
  );
};

export default PageLoadingFallback;
