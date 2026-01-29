"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

interface BreadcrumbMetadata {
  label: string;
  detail?: string;
}

interface BreadcrumbContextType {
  metadata: BreadcrumbMetadata | null;
  setMetadata: (metadata: BreadcrumbMetadata | null) => void;
}

const BreadcrumbContext = createContext<BreadcrumbContextType | null>(null);

export function BreadcrumbProvider({ children }: { children: ReactNode }) {
  const [metadata, setMetadataState] = useState<BreadcrumbMetadata | null>(null);

  const setMetadata = useCallback((newMetadata: BreadcrumbMetadata | null) => {
    setMetadataState(newMetadata);
  }, []);

  return (
    <BreadcrumbContext.Provider value={{ metadata, setMetadata }}>
      {children}
    </BreadcrumbContext.Provider>
  );
}

export function useBreadcrumb() {
  const context = useContext(BreadcrumbContext);
  if (!context) {
    throw new Error("useBreadcrumb must be used within BreadcrumbProvider");
  }
  return context;
}

/**
 * Hook for pages to set their breadcrumb metadata.
 * Sets on mount/update, clears on unmount.
 */
export function useSetBreadcrumb(label: string, detail?: string) {
  const { setMetadata } = useBreadcrumb();
  const prevRef = useRef<{ label: string; detail?: string } | null>(null);

  useEffect(() => {
    // Only update if changed
    if (prevRef.current?.label !== label || prevRef.current?.detail !== detail) {
      prevRef.current = { label, detail };
      setMetadata({ label, detail });
    }

    return () => {
      setMetadata(null);
    };
  }, [label, detail, setMetadata]);
}
