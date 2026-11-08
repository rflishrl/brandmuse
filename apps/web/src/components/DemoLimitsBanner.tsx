import { Info, X } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";

const STORAGE_KEY = "brandmuse:demo_limits_dismissed";

export const DemoLimitsBanner: React.FC = () => {
  const [dismissed, setDismissed] = useState(true); // default true to avoid flash

  useEffect(() => {
    try {
      const isDismissed = localStorage.getItem(STORAGE_KEY) === "true";
      setDismissed(isDismissed);
    } catch {
      setDismissed(false);
    }
  }, []);

  const handleDismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // Ignore localStorage failure
    }
  };

  if (dismissed) return null;

  return (
    <div
      role="region"
      aria-label="Demo limits notice"
      className="flex items-center justify-between gap-3 px-4 py-2 rounded-full bg-foreground/[0.04] border border-border dark:border-white/10 text-[11px] text-muted-foreground backdrop-blur-md max-w-xl mx-auto transition-all duration-200"
    >
      <div className="flex items-center gap-2">
        <Info className="w-3.5 h-3.5 text-foreground/80 shrink-0" aria-hidden="true" />
        <span>
          <strong className="text-foreground font-medium">Demo limits:</strong> 10 MB PDF max, 5
          image generations per hour, quotas reset at midnight.
        </span>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className="p-1 rounded-full text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors shrink-0"
        aria-label="Dismiss demo limits notice"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};
