import React, { useState, useEffect } from "react";
import { Info, X } from "lucide-react";

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
      className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-card bg-surface-user border border-border text-xs text-muted-foreground transition-all duration-200"
    >
      <div className="flex items-center gap-2">
        <Info className="w-4 h-4 text-ring shrink-0" aria-hidden="true" />
        <span>
          <strong className="text-foreground font-medium">Demo limits:</strong> 10 MB PDF max, 5 image generations per hour, daily quotas reset at midnight.
        </span>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface transition-colors shrink-0"
        aria-label="Dismiss demo limits notice"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
