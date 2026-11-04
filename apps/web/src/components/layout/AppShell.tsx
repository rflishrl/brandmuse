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
  ExternalLink,
} from "lucide-react";
import { BrandMuseOrb } from "@/components/BrandMuseOrb";
import { Button } from "@/components/ui/button";

interface AppShellProps {
  children: React.ReactNode;
  currentDocumentName?: string;
  onUseSampleBrand?: () => void;
}

type ThemeMode = "light" | "dark" | "system";

export const AppShell: React.FC<AppShellProps> = ({
  children,
  currentDocumentName = "No brand loaded",
  onUseSampleBrand,
}) => {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem("brandmuse_theme") as ThemeMode;
      return saved || "system";
    } catch {
      return "system";
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
    { label: "Ask", path: "/ask", icon: MessageSquare },
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
    <div className="min-h-screen flex flex-col md:flex-row bg-background text-foreground">
      {/* Accessibility: Skip to Content Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:rounded-md focus:shadow-md focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>

      {/* Mobile Top Bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <BrandMuseOrb size={26} />
          <div>
            <span className="font-semibold text-sm">BrandMuse</span>
            <span className="block text-[11px] text-muted-foreground truncate max-w-[180px]">
              {currentDocumentName}
            </span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </Button>
      </header>

      {/* Desktop Sidebar (280px) & Mobile Drawer */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-40 w-[280px] bg-surface border-r border-border flex flex-col justify-between shrink-0 transition-transform duration-200 ease-in-out
          ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
        aria-label="Sidebar navigation"
      >
        <div className="p-5 flex flex-col gap-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3 group focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg p-1">
              <BrandMuseOrb size={30} />
              <div>
                <h1 className="font-semibold text-base tracking-tight leading-none">BrandMuse</h1>
                <p className="text-[12px] text-muted-foreground mt-1 truncate max-w-[170px]" title={currentDocumentName}>
                  {currentDocumentName}
                </p>
              </div>
            </Link>
          </div>

          {/* Nav Items */}
          <nav className="flex flex-col gap-1.5" aria-label="Main menu">
            {navItems.map((item) => {
              const active = location.pathname === item.path || (item.path === "/ask" && location.pathname === "/");
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`
                    flex items-center gap-3 px-3.5 py-2.5 rounded-nav text-sm font-medium transition-colors
                    ${active ? "bg-nav-active text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground hover:bg-surface-user"}
                  `}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Demo Section */}
          <div className="pt-2 border-t border-border">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3">
              Demo
            </span>
            <button
              type="button"
              onClick={onUseSampleBrand}
              className="mt-2 w-full flex items-center justify-between px-3.5 py-2.5 rounded-nav text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-surface-user transition-colors text-left"
            >
              <span className="flex items-center gap-2">
                <Bookmark className="w-3.5 h-3.5 text-ring shrink-0" aria-hidden="true" />
                Use sample brand
              </span>
              <span className="text-[10px] bg-surface-user px-1.5 py-0.5 rounded border border-border">Free</span>
            </button>
          </div>
        </div>

        {/* Footer info & theme toggle */}
        <div className="p-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
          <button
            type="button"
            onClick={cycleTheme}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-surface-user transition-colors"
            title={`Current theme: ${theme}. Click to change.`}
            aria-label={`Toggle theme, current is ${theme}`}
          >
            <ThemeIcon className="w-4 h-4" aria-hidden="true" />
            <span className="capitalize">{theme}</span>
          </button>

          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-foreground transition-colors p-1.5 rounded-md"
          >
            <span>Feedback</span>
            <ExternalLink className="w-3 h-3" aria-hidden="true" />
          </a>
        </div>
      </aside>

      {/* Backdrop for mobile drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 md:hidden backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Content Column (Centered, Max Width ~760px) */}
      <main id="main-content" className="flex-1 flex flex-col items-center px-4 md:px-8 py-6 md:py-10 overflow-y-auto">
        <div className="w-full max-w-[760px] flex flex-col gap-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default AppShell;
