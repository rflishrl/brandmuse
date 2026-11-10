import {
  AlertTriangle,
  Bookmark,
  FileText,
  Image as ImageIcon,
  Laptop,
  Megaphone,
  Menu,
  MessageSquare,
  Moon,
  PanelLeft,
  PanelLeftClose,
  Plus,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
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

  // Desktop sidebar expand / collapse state
  const [isExpanded, setIsExpanded] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem("brandmuse_sidebar_expanded");
      // Default to expanded so user can see menu names and understand features
      return saved !== null ? saved === "true" : true;
    } catch {
      return true;
    }
  });

  const [theme, setTheme] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem("brandmuse_theme") as ThemeMode;
      return saved || "dark";
    } catch {
      return "dark";
    }
  });

  const toggleSidebar = useCallback(() => {
    setIsExpanded((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("brandmuse_sidebar_expanded", String(next));
      } catch {
        // Ignore localStorage error
      }
      return next;
    });
  }, []);

  // Keyboard shortcut: Cmd+B / Ctrl+B to toggle sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleSidebar]);

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
  }, []);

  const navItems = [
    {
      label: "Ask",
      path: "/ask",
      icon: MessageSquare,
    },
    {
      label: "Brand Rules",
      path: "/rules",
      icon: ShieldCheck,
    },
    {
      label: "Campaign",
      path: "/campaign",
      icon: Megaphone,
    },
    {
      label: "Gallery",
      path: "/gallery",
      icon: ImageIcon,
    },
    {
      label: "Documents",
      path: "/documents",
      icon: FileText,
    },
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
    <div className="min-h-screen flex flex-col md:flex-row bg-background text-foreground antialiased selection:bg-foreground/20">
      {/* Accessibility: Skip to Content Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:rounded-md focus:shadow-md focus:ring-2 focus:ring-foreground/40"
      >
        Skip to main content
      </a>

      {/* Mobile Top Bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-surface/85 dark:bg-[#08080A]/85 backdrop-blur-md shrink-0 sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <BrandMuseOrb size={28} glow />
          <div>
            <span className="font-bold text-sm tracking-tight text-foreground">BrandMuse</span>
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
          className="text-foreground hover:bg-foreground/10"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </Button>
      </header>

      {/* Mobile Drawer (Slides out when opened on small screens) */}
      {mobileOpen && (
        <aside
          className="fixed inset-y-0 left-0 z-50 w-[270px] bg-surface border-r border-border p-5 flex flex-col justify-between md:hidden shadow-2xl animate-in slide-in-from-left duration-200"
          aria-label="Mobile navigation drawer"
        >
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BrandMuseOrb size={32} />
                <div>
                  <span className="font-bold text-base text-foreground tracking-tight block">
                    BrandMuse AI
                  </span>
                  <span className="text-[11px] text-muted-foreground truncate max-w-[160px] block">
                    {effectiveDocumentName}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors"
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
              className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-foreground/10 hover:bg-foreground/15 border border-foreground/15 text-foreground text-xs font-semibold shadow-xs transition-all"
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
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm transition-all ${
                      active
                        ? "bg-foreground/10 text-foreground font-semibold border border-foreground/20 shadow-xs"
                        : "text-muted-foreground hover:text-foreground hover:bg-foreground/5"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex flex-col gap-3 pt-4 border-t border-border">
            <button
              type="button"
              onClick={() => {
                handleUseSample?.();
                setMobileOpen(false);
              }}
              className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors"
            >
              <span className="flex items-center gap-2.5">
                <Bookmark className="w-4 h-4" />
                <span>Load Aura Living Demo</span>
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-foreground/5 text-muted-foreground">
                Demo
              </span>
            </button>
            <button
              type="button"
              onClick={cycleTheme}
              className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors"
            >
              <span className="flex items-center gap-2.5">
                <ThemeIcon className="w-4 h-4" />
                <span className="capitalize">{theme} Mode</span>
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-foreground/5 text-muted-foreground">
                Toggle
              </span>
            </button>
          </div>
        </aside>
      )}

      {/* Backdrop for mobile drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 dark:bg-black/70 z-40 md:hidden backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Desktop Navigation Rail / Expandable Sidebar */}
      <aside
        className={`
          hidden md:flex sticky top-0 inset-y-0 left-0 z-40 h-screen
          bg-surface/85 dark:bg-[#08080A]/80 backdrop-blur-xl border-r border-border dark:border-white/[0.08]
          flex-col justify-between shrink-0 select-none overflow-x-hidden
          transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] will-change-[width] px-3 py-4
          ${isExpanded ? "w-[240px]" : "w-[68px]"}
        `}
        aria-label="Desktop navigation sidebar"
      >
        {/* Top: Header, Logo, and Expand/Collapse Toggle */}
        <div className="flex flex-col gap-4 w-full">
          {/* Top Bar with Logo */}
          <div className="flex items-center w-full">
            <Link
              to="/"
              title="BrandMuse AI"
              aria-label="BrandMuse AI Home"
              className="flex items-center h-11 w-full rounded-2xl hover:scale-[1.02] transition-transform focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40 group overflow-hidden"
            >
              <div className="w-11 h-11 shrink-0 flex items-center justify-center">
                <BrandMuseOrb size={28} glow />
              </div>
              <div
                className={`flex flex-col transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                  isExpanded
                    ? "opacity-100 max-w-[150px] translate-x-0"
                    : "opacity-0 max-w-0 -translate-x-2 pointer-events-none"
                }`}
              >
                <span className="font-bold text-sm tracking-tight text-foreground flex items-center gap-1.5">
                  BrandMuse
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-foreground/10 text-foreground font-semibold">
                    AI
                  </span>
                </span>
                <span
                  className="text-[10px] text-muted-foreground truncate max-w-[140px]"
                  title={effectiveDocumentName}
                >
                  {effectiveDocumentName}
                </span>
              </div>
            </Link>
          </div>

          {/* New Chat Button */}
          <Link
            to="/ask"
            onClick={() => {
              window.dispatchEvent(new CustomEvent("brandmuse:new-chat"));
            }}
            title="New Chat"
            aria-label="Start new chat session"
            className="w-full h-11 rounded-2xl flex items-center overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] shadow-xs group bg-foreground/5 hover:bg-foreground/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.12] border border-border dark:border-white/10 text-foreground hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className="w-11 h-11 shrink-0 flex items-center justify-center">
              <span className="p-1 rounded-lg bg-foreground/10 text-foreground group-hover:scale-105 transition-transform">
                <Plus className="w-3.5 h-3.5" />
              </span>
            </div>
            <span
              className={`text-xs font-semibold tracking-tight transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                isExpanded
                  ? "opacity-100 max-w-[120px] translate-x-0"
                  : "opacity-0 max-w-0 -translate-x-2 pointer-events-none"
              }`}
            >
              New Chat
            </span>
          </Link>

          {/* Nav Rail / Menu Items */}
          <nav className="flex flex-col gap-1.5 w-full mt-1" aria-label="Main menu">
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
                    relative rounded-2xl flex items-center overflow-hidden h-11 w-full transition-all duration-200 group
                    ${
                      active
                        ? "bg-foreground/10 text-foreground font-semibold border border-foreground/20 dark:bg-white/[0.14] dark:text-white dark:border-white/20 dark:shadow-[0_0_20px_rgba(255,255,255,0.08)]"
                        : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.05] border border-transparent hover:scale-[1.02]"
                    }
                  `}
                  aria-current={active ? "page" : undefined}
                >
                  <div className="w-11 h-11 shrink-0 flex items-center justify-center">
                    <Icon
                      className={`w-4 h-4 transition-transform ${
                        active
                          ? "text-foreground dark:text-white scale-105"
                          : "text-muted-foreground group-hover:text-foreground"
                      }`}
                      aria-hidden="true"
                    />
                  </div>
                  <span
                    className={`text-xs font-medium tracking-tight truncate transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                      isExpanded
                        ? "opacity-100 max-w-[140px] translate-x-0"
                        : "opacity-0 max-w-0 -translate-x-2 pointer-events-none"
                    }`}
                  >
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom Section: Sample Brand, Theme Toggle, Avatar, and Expand Toggle Button */}
        <div className="flex flex-col gap-2 w-full pt-3 border-t border-border dark:border-white/[0.08]">
          {/* Sample Brand Demo Shortcut */}
          <button
            type="button"
            onClick={() => handleUseSample?.()}
            title="Load demo brand guideline (Aura Living)"
            aria-label="Load demo brand guideline"
            className="w-full h-11 rounded-2xl flex items-center overflow-hidden text-muted-foreground hover:text-foreground hover:bg-foreground/[0.05] border border-transparent hover:border-border dark:hover:border-white/10 transition-all group"
          >
            <div className="w-11 h-11 shrink-0 flex items-center justify-center">
              <Bookmark className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors shrink-0" />
            </div>
            <div
              className={`flex-1 flex items-center justify-between transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                isExpanded
                  ? "opacity-100 max-w-[160px] pr-2.5 translate-x-0"
                  : "opacity-0 max-w-0 pr-0 -translate-x-2 pointer-events-none"
              }`}
            >
              <span className="font-medium text-xs">Sample Brand</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-foreground/5 text-muted-foreground">
                Demo
              </span>
            </div>
          </button>

          {/* Theme Toggle (Light / Dark / System) */}
          <button
            type="button"
            onClick={cycleTheme}
            title={`Toggle theme (current: ${theme}). Click to change.`}
            aria-label={`Toggle theme, current is ${theme}`}
            className="w-full h-11 rounded-2xl flex items-center overflow-hidden text-muted-foreground hover:text-foreground hover:bg-foreground/[0.05] border border-transparent hover:border-border dark:hover:border-white/10 transition-all group"
          >
            <div className="w-11 h-11 shrink-0 flex items-center justify-center">
              <ThemeIcon className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors shrink-0" />
            </div>
            <div
              className={`flex-1 flex items-center justify-between transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                isExpanded
                  ? "opacity-100 max-w-[160px] pr-2.5 translate-x-0"
                  : "opacity-0 max-w-0 pr-0 -translate-x-2 pointer-events-none"
              }`}
            >
              <span className="capitalize font-medium text-xs">{theme} Mode</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-foreground/5 text-muted-foreground">
                Switch
              </span>
            </div>
          </button>

          {/* Active Brand Workspace Status Indicator */}
          <div className="w-full flex items-center overflow-hidden pt-1">
            <div
              className={`w-full flex items-center rounded-xl transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                isExpanded
                  ? "p-1.5 bg-foreground/[0.03] border border-border/60 dark:border-white/5"
                  : "h-11 justify-center bg-transparent border-transparent"
              }`}
            >
              <div
                className="w-8 h-8 rounded-xl bg-foreground/10 border border-border dark:border-white/20 flex items-center justify-center text-foreground shrink-0 shadow-xs"
                title={`Active Guideline • ${effectiveDocumentName}`}
              >
                <FileText className="w-4 h-4 text-muted-foreground" />
              </div>
              <div
                className={`flex flex-col min-w-0 transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                  isExpanded
                    ? "opacity-100 max-w-[140px] pl-2 translate-x-0"
                    : "opacity-0 max-w-0 pl-0 -translate-x-2 pointer-events-none"
                }`}
              >
                <span className="text-xs font-semibold text-foreground truncate">Active Brand</span>
                <span
                  className="text-[10px] text-muted-foreground truncate max-w-[130px]"
                  title={effectiveDocumentName}
                >
                  {effectiveDocumentName}
                </span>
              </div>
            </div>
          </div>

          {/* Bottom Expand / Collapse Sidebar Toggle */}
          <button
            type="button"
            onClick={toggleSidebar}
            title={isExpanded ? "Collapse sidebar" : "Expand sidebar"}
            aria-label={isExpanded ? "Collapse sidebar" : "Expand sidebar"}
            className="w-full h-10 rounded-xl flex items-center overflow-hidden text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-all"
          >
            <div className="w-11 h-10 shrink-0 flex items-center justify-center">
              {isExpanded ? (
                <PanelLeftClose className="w-3.5 h-3.5 transition-transform duration-300" />
              ) : (
                <PanelLeft className="w-3.5 h-3.5 transition-transform duration-300" />
              )}
            </div>
            <span
              className={`text-[11px] font-medium transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] whitespace-nowrap overflow-hidden ${
                isExpanded
                  ? "opacity-100 max-w-[130px] translate-x-0"
                  : "opacity-0 max-w-0 -translate-x-2 pointer-events-none"
              }`}
            >
              Collapse sidebar
            </span>
          </button>
        </div>
      </aside>

      {/* Main Content Stage (Centered, Clean, Light/Dark Responsive) */}
      <main
        id="main-content"
        className="flex-1 flex flex-col items-center px-4 md:px-8 py-6 md:py-10 overflow-y-auto min-h-screen relative"
      >
        <div className="w-full max-w-5xl flex flex-col gap-6 relative z-10">
          {/* Server Spin-Up Notification for Hugging Face Spaces cold start */}
          {brand.isServerWarmingUp && (
            <aside
              role="status"
              aria-live="polite"
              aria-atomic="true"
              className="w-full py-2 px-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200 text-xs flex items-center justify-between gap-3 animate-in fade-in slide-in-from-top-1 duration-200 shrink-0"
            >
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                </span>
                <span>
                  Menghubungkan ke server cloud (kontainer Hugging Face sedang <em>spin-up</em>)...
                </span>
              </div>
              <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                Estimasi 10–15 detik
              </span>
            </aside>
          )}

          {/* Server Offline / Unreachable Notice */}
          {brand.isServerOffline && (
            <aside
              role="alert"
              className="w-full py-2 px-3.5 rounded-xl border border-red-500/30 bg-red-500/10 text-red-800 dark:text-red-200 text-xs flex items-center justify-between gap-3 animate-in fade-in duration-200 shrink-0"
            >
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
                <span>
                  Tidak dapat menghubungi server backend. Kontainer mungkin sedang tidur atau belum
                  aktif.
                </span>
              </div>
              <button
                type="button"
                onClick={() => brand.refetchDocuments()}
                className="underline hover:no-underline font-medium cursor-pointer"
              >
                Coba lagi
              </button>
            </aside>
          )}

          {children}
        </div>
      </main>
    </div>
  );
};

export default AppShell;
