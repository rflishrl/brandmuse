import React from "react";

interface BrandMuseOrbProps {
  size?: number;
  className?: string;
  animate?: boolean;
}

/**
 * BrandMuse mark: A circular gradient orb (linear gradient from #FF8A5B to #7C6CF0).
 * Original SVG artwork complying with anti-slop rules (no generic sparkle/star glyphs).
 */
export const BrandMuseOrb: React.FC<BrandMuseOrbProps> = ({
  size = 28,
  className = "",
  animate = false,
}) => {
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
        <linearGradient id="brandmuse-gradient" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FF8A5B" />
          <stop offset="100%" stopColor="#7C6CF0" />
        </linearGradient>
        <radialGradient id="brandmuse-inner" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(11 10) rotate(45) scale(14)">
          <stop stopColor="#FFFFFF" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="16" cy="16" r="14" fill="url(#brandmuse-gradient)" />
      <circle cx="16" cy="16" r="14" fill="url(#brandmuse-inner)" />
    </svg>
  );
};

export default BrandMuseOrb;
