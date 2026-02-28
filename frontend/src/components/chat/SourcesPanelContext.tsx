"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { ConversationSource, Collection } from "@/lib/types";

export interface LibraryContentItem {
  id: string;
  title: string;
  type: "video" | "document";
  status: string;
  duration_seconds?: number;
  page_count?: number;
  channel_name?: string;
  thumbnail_url?: string;
}

export interface SourcesPanelState {
  mode: "library" | "conversation";
  // Library mode
  libraryItems: LibraryContentItem[];
  processingItems: LibraryContentItem[];
  selectedIds: string[];
  selectedCollectionId: string;
  onSelectionChange: (ids: string[]) => void;
  onCollectionChange: (id: string) => void;
  // Conversation mode
  conversationSources: ConversationSource[];
  selectedSourcesCount: number;
  totalSourcesCount: number;
  onToggleSource: (videoId: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  sourcesUpdatePending: boolean;
  sourcesUpdateError: string | null;
  onReprocessSource?: (videoId: string) => void;
  reprocessPending?: boolean;
  // Shared
  isLoading: boolean;
  collections: Collection[];
  // Panel visibility
  isPanelOpen: boolean;
  togglePanel: () => void;
}

const defaultState: SourcesPanelState = {
  mode: "library",
  libraryItems: [],
  processingItems: [],
  selectedIds: [],
  selectedCollectionId: "",
  onSelectionChange: () => {},
  onCollectionChange: () => {},
  conversationSources: [],
  selectedSourcesCount: 0,
  totalSourcesCount: 0,
  onToggleSource: () => {},
  onSelectAll: () => {},
  onDeselectAll: () => {},
  sourcesUpdatePending: false,
  sourcesUpdateError: null,
  isLoading: false,
  collections: [],
  isPanelOpen: true,
  togglePanel: () => {},
};

const SourcesPanelContext = createContext<SourcesPanelState>(defaultState);

export function useSourcesPanel() {
  return useContext(SourcesPanelContext);
}

interface SourcesPanelProviderProps {
  children: ReactNode;
  value: Omit<SourcesPanelState, "isPanelOpen" | "togglePanel">;
}

export function SourcesPanelProvider({ children, value }: SourcesPanelProviderProps) {
  const [isPanelOpen, setIsPanelOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    const stored = localStorage.getItem("sources-panel-open");
    return stored === null ? true : stored === "true";
  });

  const togglePanel = useCallback(() => {
    setIsPanelOpen((prev) => {
      const next = !prev;
      localStorage.setItem("sources-panel-open", String(next));
      return next;
    });
  }, []);

  return (
    <SourcesPanelContext.Provider value={{ ...value, isPanelOpen, togglePanel }}>
      {children}
    </SourcesPanelContext.Provider>
  );
}
