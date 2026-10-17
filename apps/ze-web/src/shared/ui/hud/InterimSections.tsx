import { createElement, lazy, Suspense, type ComponentType, type LazyExoticComponent, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { SectionTabs } from "./SectionTabs";

export type PageLoader = () => Promise<{ default: ComponentType }>;

export interface InterimSection {
  id: string;
  label: string;
  /** Canonical path of the section. */
  path: string;
  /** Whether `pathname` belongs to this section (the first section also owns the place's index). */
  owns: (pathname: string) => boolean;
  load: PageLoader;
}

const lazyByLoader = new WeakMap<PageLoader, LazyExoticComponent<ComponentType>>();

/** One lazy component per loader, so a section keeps its identity across renders. */
function lazyPage(load: PageLoader): LazyExoticComponent<ComponentType> {
  let page = lazyByLoader.get(load);
  if (!page) {
    page = lazy(load);
    lazyByLoader.set(load, page);
  }
  return page;
}

/**
 * The old pages a place hosts until its own phase replaces them. A section switcher on top, the
 * matching page below. A path no section owns is left to the caller (`fallback`).
 */
export function InterimSections({
  label,
  sections,
  header,
  fallback = null,
}: {
  label: string;
  sections: readonly InterimSection[];
  header?: (sectionId: string) => ReactNode;
  fallback?: ReactNode;
}) {
  const { pathname } = useLocation();
  const current = sections.find((s) => s.owns(pathname));
  if (!current) return <>{fallback}</>;
  return (
    <div className="interim">
      <SectionTabs label={label} sections={sections} currentId={current.id} />
      {header?.(current.id)}
      <div className="interim-page">
        <Suspense fallback={<div className="interim-loading lbl">Loading</div>}>{createElement(lazyPage(current.load))}</Suspense>
      </div>
    </div>
  );
}
