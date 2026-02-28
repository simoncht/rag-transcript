"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth, useAuthState, createParallelQueryFn } from "@/lib/auth";
import { apiClient } from "@/lib/api/client";
import { subscriptionsApi } from "@/lib/api/subscriptions";
import { conversationsApi } from "@/lib/api/conversations";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import type { QuotaUsage, Conversation } from "@/lib/types";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const authProvider = useAuth();
  const { user, isAuthenticated } = useAuthState();
  const queryClient = useQueryClient();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isAdminBackend, setIsAdminBackend] = useState<boolean | null>(null);

  // Extract active conversation ID from pathname
  const activeConversationId = pathname.startsWith("/chat/")
    ? pathname.split("/chat/")[1]?.split("?")[0]
    : undefined;

  // Check admin status
  const isAdmin = user?.metadata?.is_superuser === true;
  const hasAdminAccess = isAdmin || isAdminBackend === true;

  useEffect(() => {
    if (!user) {
      setIsAdminBackend(false);
      return;
    }
    let isMounted = true;
    const fetchAdminStatus = async () => {
      try {
        const response = await apiClient.get("/auth/me");
        if (isMounted) {
          setIsAdminBackend(Boolean(response.data?.is_superuser));
        }
      } catch {
        if (isMounted) {
          setIsAdminBackend(false);
        }
      }
    };
    fetchAdminStatus();
    return () => { isMounted = false; };
  }, [user?.id]);

  // Fetch conversations for sidebar
  const { data: conversationsData } = useQuery({
    queryKey: ["conversations"],
    queryFn: createParallelQueryFn(authProvider, () => conversationsApi.list(0, 50)),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const conversations = conversationsData?.conversations ?? [];

  // Fetch quota
  const { data: quota } = useQuery<QuotaUsage>({
    queryKey: ["subscription-quota"],
    queryFn: subscriptionsApi.getQuota,
    enabled: isAuthenticated,
    staleTime: 60 * 1000,
    refetchInterval: 120 * 1000,
  });

  const handleLogout = () => {
    authProvider.signOut("/sign-in");
  };

  const handleConversationDeleted = useCallback(
    (deletedId: string): string | null => {
      if (!conversations || conversations.length <= 1) {
        queryClient.setQueryData(["conversations"], (prev: any) =>
          prev ? { ...prev, conversations: [] } : prev
        );
        router.push("/chat");
        return null;
      }
      const idx = conversations.findIndex((c: Conversation) => c.id === deletedId);
      if (idx === -1) return null;
      const nextId = idx < conversations.length - 1
        ? conversations[idx + 1].id
        : conversations[idx - 1].id;
      queryClient.setQueryData(["conversations"], (prev: any) =>
        prev
          ? { ...prev, conversations: prev.conversations.filter((c: Conversation) => c.id !== deletedId) }
          : prev
      );
      router.push(nextId ? `/chat/${nextId}` : "/chat");
      return nextId;
    },
    [conversations, queryClient, router]
  );

  // Close mobile sidebar on navigation
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-muted-foreground">Sign in to start chatting.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button asChild>
              <Link href="/sign-up">Create account</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        sidebarOpen={sidebarOpen}
        onCloseSidebar={() => setSidebarOpen(false)}
        hasAdminAccess={hasAdminAccess}
        user={user ? { displayName: user.displayName, email: user.email } : null}
        quota={quota ?? null}
        onLogout={handleLogout}
        onConversationDeleted={handleConversationDeleted}
      />

      {/* Main content — children provide SourcesPanelProvider + SourcesPanel */}
      <div className="flex h-full flex-1 min-h-0">
        {children}
      </div>
    </div>
  );
}
