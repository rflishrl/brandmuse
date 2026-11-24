import { lazy, memo, Suspense, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router";
import { PageLoadingFallback } from "@/components/layout/PageLoadingFallback";
import { routeImporters } from "@/lib/routePrefetch";

const AskPage = lazy(routeImporters["/ask"]);
const OntologyPage = lazy(routeImporters["/rules"]);
const CampaignPage = lazy(routeImporters["/campaign"]);
const GalleryPage = lazy(routeImporters["/gallery"]);
const DocumentsPage = lazy(routeImporters["/documents"]);

type TabPath = "/ask" | "/rules" | "/campaign" | "/gallery" | "/documents";

const TAB_COMPONENTS: Record<TabPath, React.LazyExoticComponent<React.ComponentType>> = {
  "/ask": AskPage,
  "/rules": OntologyPage,
  "/campaign": CampaignPage,
  "/gallery": GalleryPage,
  "/documents": DocumentsPage,
};

function resolveTabPath(pathname: string): TabPath | null {
  if (pathname === "/" || pathname === "/ask") return "/ask";
  if (pathname === "/rules" || pathname === "/ontology") return "/rules";
  if (pathname === "/campaign") return "/campaign";
  if (pathname === "/gallery") return "/gallery";
  if (pathname === "/documents") return "/documents";
  return null;
}

interface CachedTabPanelProps {
  isActive: boolean;
  label: string;
  children: React.ReactNode;
}

const CachedTabPanel = memo<CachedTabPanelProps>(function CachedTabPanel({
  isActive,
  label,
  children,
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prevActiveRef = useRef<boolean>(isActive);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Sync inert via DOM property to prevent React 18 boolean attribute serialization issues
    el.inert = !isActive;

    // Move focus only when transitioning from hidden -> active and focus is outside this view
    if (!prevActiveRef.current && isActive && !el.contains(document.activeElement)) {
      el.focus({ preventScroll: true });
    }
    prevActiveRef.current = isActive;
  }, [isActive]);

  return (
    <section
      ref={containerRef}
      tabIndex={-1}
      aria-label={label}
      aria-hidden={!isActive}
      className={`spa-view w-full ${isActive ? "" : "inactive"}`}
    >
      {children}
    </section>
  );
});

export const CachedTabStage: React.FC = () => {
  const { pathname } = useLocation();
  const activeTab = resolveTabPath(pathname);

  const [visitedTabs, setVisitedTabs] = useState<TabPath[]>(() => (activeTab ? [activeTab] : []));

  useEffect(() => {
    if (!activeTab) return;
    setVisitedTabs((prev) => (prev.includes(activeTab) ? prev : [...prev, activeTab]));
  }, [activeTab]);

  if (visitedTabs.length === 0) return null;

  return (
    <div className="relative w-full">
      {visitedTabs.map((tab) => {
        const Component = TAB_COMPONENTS[tab];
        const isActive = tab === activeTab;
        return (
          <CachedTabPanel key={tab} isActive={isActive} label={`${tab.slice(1)} view`}>
            <Suspense fallback={<PageLoadingFallback />}>
              <Component />
            </Suspense>
          </CachedTabPanel>
        );
      })}
    </div>
  );
};
