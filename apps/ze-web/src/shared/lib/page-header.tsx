import type { LucideIcon } from "lucide-react";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface PageHeader {
  title: string;
  icon: LucideIcon;
}

interface PageHeaderCtx {
  pageHeader: PageHeader | null;
  setPageHeader: (header: PageHeader | null) => void;
}

const PageHeaderContext = createContext<PageHeaderCtx>({
  pageHeader: null,
  setPageHeader: () => {},
});

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [pageHeader, setPageHeader] = useState<PageHeader | null>(null);
  return (
    <PageHeaderContext.Provider value={{ pageHeader, setPageHeader }}>
      {children}
    </PageHeaderContext.Provider>
  );
}

export function usePageHeader() {
  return useContext(PageHeaderContext);
}

/** Register a title/icon override for the top bar. Cleared on unmount. Used by routes not in the static nav table (e.g. plugin pages). */
export function useSetPageHeader(header: PageHeader | null) {
  const { setPageHeader } = usePageHeader();
  const title = header?.title;
  const icon = header?.icon;
  useEffect(() => {
    setPageHeader(title !== undefined && icon ? { title, icon } : null);
    return () => setPageHeader(null);
  }, [title, icon, setPageHeader]);
}
