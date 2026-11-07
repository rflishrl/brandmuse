import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router";
import {
  FileText,
  MessageSquare,
  Megaphone,
  Image as ImageIcon,
  Menu,
  X,
  Sun,
  Moon,
  Laptop,
  Bookmark,
  ShieldCheck,
  Plus,
  User,
} from "lucide-react";
import { BrandMuseOrb } from "@/components/BrandMuseOrb";
import { Button } from "@/components/ui/button";
import { useBrand } from "@/context/BrandContext";

interface AppShellProps {
  children: React.ReactNode;
  currentDocumentName?: string;
  onUseSampleBrand?: () => void;
}

type ThemeMode = "light" | "dark" | "system";

export const AppShell: React.FC<AppShellProps> = ({
  children,
  currentDocumentName,
  onUseSampleBrand,
}) => {
  const brand = useBrand();
  const effectiveDocumentName =
    currentDocumentName || brand.selectedDocument?.filename || "No brand loaded";
  const handleUseSample = onUseSampleBrand || brand.loadSampleBrand;

  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const [theme, setTheme] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem("brandmuse_theme") as ThemeMode;
      return saved || "dark";
    } catch {
      return "dark";
    }
  });

  // Apply theme class to document element
  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const applyTheme = () => {
      const isDark = theme === "dark" || (theme === "system" && mediaQuery.matches);
      if (isDark) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    };

    applyTheme();
    try {
      localStorage.setItem("brandmuse_theme", theme);
    } catch {
      // Ignore localStorage failure
    }

    mediaQuery.addEventListener("change", applyTheme);
    return () => mediaQuery.removeEventListener("change", applyTheme);
  }, [theme]);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const navItems = [
    { label: "Ask AI", path: "/ask", icon: MessageSquare },
    { label: "Brand Rules", path: "/rules", icon: ShieldCheck },
    { label: "Campaign", path: "/campaign", icon: Megaphone },
    { label: "Gallery", path: "/gallery", icon: ImageIcon },
    { label: "Documents", path: "/documents", icon: FileText },
  ];

  const cycleTheme = () => {
    const nextTheme: Record<ThemeMode, ThemeMode> = {
      light: "dark",
      dark: "system",
      system: "light",
    };
    setTheme(nextTheme[theme]);
  };

  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Laptop;

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[#08080A] text-foreground antialiased selection:bg-white/20">
      {/* Accessibility: Skip to Content Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:rounded-md focus:shadow-md focus:ring-2 focus:ring-white/40"
      >
        Skip to main content
      </a>

      {/* Mobile Top Bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.08] bg-[#09090C]/90 backdrop-blur-md shrink-0 sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <BrandMuseOrb size={28} glow />
          <div>
            <span className="font-bold text-sm tracking-tight text-white">BrandMuse</span>
            <span className="block text-[11px] text-muted-foreground truncate max-w-[180px]">
              {effectiveDocumentName}
            </span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
          className="text-white hover:bg-white/10"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </Button>
      </header>

      {/* Mobile Drawer (Slides out when opened on small screens) */}
      {mobileOpen && (
        <aside
          className="fixed inset-y-0 left-0 z-50 w-[260px] bg-[#09090C] border-r border-white/10 p-5 flex flex-col justify-between md:hidden shadow-2xl animate-in slide-in-from-left duration-200"
          aria-label="Mobile navigation drawer"
        >
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BrandMuseOrb size={32} glow />
                <span className="font-bold text-base text-white tracking-tight">BrandMuse AI</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-white"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <Link
              to="/ask"
              onClick={() => {
                window.dispatchEvent(new CustomEvent("brandmuse:new-chat"));
                setMobileOpen(false);
              }}
              className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/15 text-white text-xs font-medium"
            >
              <Plus className="w-4 h-4" />
              <span>New Chat</span>
            </Link>

            <nav className="flex flex-col gap-1.5">
              {navItems.map((item) => {
                const active =
                  location.pathname === item.path ||
                  (item.path === "/ask" && location.pathname === "/");
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                      active
                        ? "bg-white/[0.12] text-white font-medium border border-white/20 shadow-xs"
                        : "text-muted-foreground hover:text-white hover:bg-white/[0.04]"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex flex-col gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={() => {
                handleUseSample?.();
                setMobileOpen(false);
              }}
              className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs text-muted-foreground hover:text-white hover:bg-white/[0.04]"
            >
              <Bookmark className="w-4 h-4" />
              <span>Load Aura Living Demo</span>
            </button>
            <button
              type="button"
              onClick={cycleTheme}
              className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-muted-foreground hover:text-white hover:bg-white/[0.04]"
            >
              <span className="flex items-center gap-2.5">
                <ThemeIcon className="w-4 h-4" />
                <span className="capitalize">{theme} mode</span>
              </span>
            </button>
          </div>
        </aside>
      )}

      {/* Backdrop for mobile drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/70 z-40 md:hidden backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Desktop Navigation Rail Dock (Behance AI Assistant Standard 72px) */}
      <aside
        className="hidden md:flex sticky top-0 inset-y-0 left-0 z-40 w-[72px] h-screen bg-[#08080A]/95 backdrop-blur-2xl border-r border-white/[0.08] flex-col justify-between items-center py-5 shrink-0 select-none"
        aria-label="Desktop icon rail"
      >
        {/* Top: Brand AI Emblem & New Chat */}
        <div className="flex flex-col items-center gap-4 w-full">
          <Link
            to="/"
            title="BrandMuse AI"
            aria-label="BrandMuse AI Home"
            className="p-1 rounded-2xl hover:scale-105 transition-transform flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          >
            <BrandMuseOrb size={32} glow />
          </Link>

          {/* New Chat Squircle Button */}
          <Link
            to="/ask"
            onClick={() => {
              window.dispatchEvent(new CustomEvent("brandmuse:new-chat"));
            }}
            title="New Chat (⌘K)"
            aria-label="Start new chat session"
            className="w-11 h-11 rounded-2xl flex items-center justify-center bg-white/[0.04] hover:bg-white/[0.12] border border-white/10 text-white transition-all hover:scale-105 active:scale-95 shadow-xs group"
          >
            <Plus className="w-4 h-4 text-muted-foreground group-hover:text-white transition-colors" />
          </Link>

          {/* Center Vertical Nav Rail */}
          <nav className="flex flex-col items-center gap-2 w-full mt-2" aria-label="Main menu">
            {navItems.map((item) => {
              const active =
                location.pathname === item.path ||
                (item.path === "/ask" && location.pathname === "/");
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  title={item.label}
                  aria-label={item.label}
                  className={`
                    relative w-11 h-11 rounded-2xl flex items-center justify-center transition-all duration-200 group
                    ${
                      active
                        ? "bg-white/[0.14] text-white border border-white/20 shadow-[0_0_20px_rgba(255,255,255,0.08)] scale-100"
                        : "text-muted-foreground hover:text-white hover:bg-white/[0.05] border border-transparent hover:scale-105"
                    }
                  `}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 transition-transform ${
                      active ? "text-white" : "text-muted-foreground group-hover:text-white"
                    }`}
                    aria-hidden="true"
                  />
                  {/* Subtle active indicator dot */}
                  {active && (
                    <span className="absolute -left-1 w-1 h-3 rounded-full bg-white shadow-[0_0_8px_#FFF]" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom Section: Sample brand, Theme toggle, Avatar */}
        <div className="flex flex-col items-center gap-3 w-full">
          {/* Sample Brand Shortcut */}
          <button
            type="button"
            onClick={() => handleUseSample?.()}
            title="Load demo brand guideline (Aura Living)"
            aria-label="Load demo brand guideline"
            className="w-11 h-11 rounded-2xl flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/[0.06] border border-transparent hover:border-white/10 transition-all group"
          >
            <Bookmark className="w-4 h-4 text-muted-foreground group-hover:text-white transition-colors" />
          </button>

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={cycleTheme}
            title={`Toggle theme (current: ${theme})`}
            aria-label={`Toggle theme, current is ${theme}`}
            className="w-11 h-11 rounded-2xl flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/[0.06] border border-transparent hover:border-white/10 transition-all group"
          >
            <ThemeIcon className="w-4 h-4 text-muted-foreground group-hover:text-white transition-colors" />
          </button>

          {/* User Profile Avatar with Online Dot */}
          <div
            className="relative w-9 h-9 rounded-full bg-white/10 border border-white/20 flex items-center justify-center text-white mt-1 cursor-pointer hover:border-white/40 transition-colors"
            title={`Active Workspace • ${effectiveDocumentName}`}
          >
            <User className="w-4 h-4 text-white/90" />
            <span
              className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-[#08080A]"
              title="Online / Ready"
            />
          </div>
        </div>
      </aside>

      {/* Main Stage (Dead Center, Cosmic Obsidian Canvas) */}
      <main
        id="main-content"
        className="flex-1 flex flex-col items-center px-4 md:px-8 py-6 md:py-10 overflow-y-auto min-h-screen relative"
      >
        <div className="w-full max-w-5xl flex flex-col gap-6 relative z-10">
          {children}
        </div>
      </main>
    </div>
  );
};

export default AppShell;
