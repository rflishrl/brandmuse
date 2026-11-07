import React from "react";

interface BrandMuseOrbProps {
  size?: number;
  className?: string;
  animate?: boolean;
  glow?: boolean;
  variant?: "mark" | "orb";
}

/**
 * BrandMuse AI Symbol
 * Geometric infinity-knot AI emblem inspired by modern Behance AI SaaS aesthetics.
 */
export const BrandMuseOrb: React.FC<BrandMuseOrbProps> = ({
  size = 28,
  className = "",
  animate = false,
  glow = false,
  variant = "mark",
}) => {
  if (variant === "orb") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 ${animate ? "animate-pulse" : ""} ${className}`}
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="brandmuse-gradient"
            x1="2"
            y1="2"
            x2="30"
            y2="30"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="100%" stopColor="#8C8CE6" />
          </linearGradient>
          <radialGradient
            id="brandmuse-inner"
            cx="0"
            cy="0"
            r="1"
            gradientUnits="userSpaceOnUse"
            gradientTransform="translate(11 10) rotate(45) scale(14)"
          >
            <stop stopColor="#FFFFFF" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="16" cy="16" r="14" fill="url(#brandmuse-gradient)" />
        <circle cx="16" cy="16" r="14" fill="url(#brandmuse-inner)" />
      </svg>
    );
  }

  return (
    <div className={`relative inline-flex items-center justify-center shrink-0 ${className}`}>
      {glow && (
        <div
          className="absolute inset-0 rounded-full bg-white/25 dark:bg-white/30 blur-xl scale-150 pointer-events-none"
          aria-hidden="true"
        />
      )}
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`shrink-0 transition-transform duration-300 ${animate ? "animate-pulse" : ""}`}
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="bm-gradient"
            x1="4"
            y1="4"
            x2="36"
            y2="36"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="60%" stopColor="#ECECF8" />
            <stop offset="100%" stopColor="#9C9CE8" />
          </linearGradient>
        </defs>
        {/* Geometric Infinite AI Loop - Behance Symbol */}
        <path
          d="M11 13C8.5 13 6.5 15 6.5 17.5C6.5 21 14 26 20 20C26 14 33.5 19 33.5 22.5C33.5 25 31.5 27 29 27C24.5 27 20 20 20 20C20 20 15.5 13 11 13Z"
          stroke="url(#bm-gradient)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="20" cy="20" r="2" fill="#FFFFFF" />
      </svg>
    </div>
  );
};

export default BrandMuseOrb;
