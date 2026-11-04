import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: "var(--surface)",
        "surface-user": "var(--surface-user)",
        quote: "var(--quote)",
        foreground: "var(--foreground)",
        "muted-foreground": "var(--muted-foreground)",
        border: "var(--border)",
        ring: "var(--ring)",
        "success-icon": "var(--success-icon)",
        "success-text": "var(--success-text)",
        danger: "var(--danger)",
        "nav-active": "var(--nav-active)",
      },
      borderRadius: {
        card: "24px",
        message: "20px",
        nav: "12px",
        input: "28px",
        btn: "12px",
      },
      boxShadow: {
        card: "0 8px 30px rgba(0, 0, 0, 0.06)",
        "card-dark": "0 8px 30px rgba(0, 0, 0, 0.4)",
      },
      fontFamily: {
        sans: ["'Inter Variable'", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
