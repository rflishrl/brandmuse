import type React from "react";

interface BrandMuseOrbProps {
  size?: number;
  className?: string;
  animate?: boolean;
  glow?: boolean;
}

/**
 * BrandMuse AI Symbol
 * Geometric butterfly/hourglass AI emblem matching the Behance project.
 * Derived from the exact geometric grid construction:
 * Spine: (24, 7) to (24, 41)
 * Right Wing Apex: (37.5, 20.5)
 * Left Wing Apex: (10.5, 27.5)
 */
export const BrandMuseOrb: React.FC<BrandMuseOrbProps> = ({
  size = 28,
  className = "",
  animate = false,
  glow = false,
}) => {
  return (
    <div className={`relative inline-flex items-center justify-center shrink-0 ${className}`}>
      {glow && (
        <div
          className="absolute inset-0 rounded-full bg-foreground/15 dark:bg-white/25 blur-xl scale-150 pointer-events-none"
          aria-hidden="true"
        />
      )}
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 transition-transform duration-300 text-foreground ${animate ? "hover:scale-105" : ""}`}
        aria-hidden="true"
      >
        <path
          d="M 24 41 V 7 L 37.5 20.5 L 10.5 27.5 L 24 41 Z"
          stroke="currentColor"
          strokeWidth="3.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};

export default BrandMuseOrb;
