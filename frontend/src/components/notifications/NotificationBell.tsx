"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, X, ExternalLink, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth, createParallelQueryFn, useAuthState } from "@/lib/auth";
import { notificationsApi } from "@/lib/api/notifications";
import { Notification } from "@/lib/types";
import { cn, parseUTCDate } from "@/lib/utils";
import Link from "next/link";

export function NotificationBell() {
  const authProvider = useAuth();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);

  // Fetch unread count
  const { data: unreadData } = useQuery({
    queryKey: ["notifications-unread-count"],
    queryFn: createParallelQueryFn(authProvider, () => notificationsApi.getUnreadCount()),
    staleTime: 30_000,
    refetchInterval: 60_000, // Refresh every minute
    enabled: canFetch,
  });

  // Fetch notifications when dropdown is opened
  const { data: notificationsData, isLoading } = useQuery({
    queryKey: ["notifications-list"],
    queryFn: createParallelQueryFn(authProvider, () => notificationsApi.list(0, 20)),
    staleTime: 30_000,
    enabled: canFetch && isOpen,
  });

  // Mark as read mutation
  const markReadMutation = useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications-list"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
  });

  // Mark all read mutation
  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications-list"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
  });

  // Dismiss mutation
  const dismissMutation = useMutation({
    mutationFn: notificationsApi.dismiss,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications-list"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
  });

  const handleNotificationClick = useCallback(
    (notification: Notification) => {
      if (!notification.read_at) {
        markReadMutation.mutate(notification.id);
      }
    },
    [markReadMutation]
  );

  const handleDismiss = useCallback(
    (e: React.MouseEvent, notificationId: string) => {
      e.preventDefault();
      e.stopPropagation();
      dismissMutation.mutate(notificationId);
    },
    [dismissMutation]
  );

  const unreadCount = unreadData?.unread_count ?? 0;
  const notifications = notificationsData?.notifications ?? [];

  if (!canFetch) {
    return null;
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              className="absolute -top-1 -right-1 h-5 min-w-5 flex items-center justify-center p-0 text-xs"
              variant="destructive"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
          <span className="sr-only">
            {unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
          </span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80 p-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="font-semibold text-sm">Notifications</h3>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto py-1 px-2 text-xs"
              onClick={() => markAllReadMutation.mutate()}
              disabled={markAllReadMutation.isPending}
            >
              {markAllReadMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <>
                  <Check className="h-3 w-3 mr-1" />
                  Mark all read
                </>
              )}
            </Button>
          )}
        </div>

        {/* Notifications list */}
        <ScrollArea className="max-h-96">
          {isLoading ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-10 w-10 rounded-full flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <Bell className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No notifications yet</p>
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onClick={() => handleNotificationClick(notification)}
                  onDismiss={(e) => handleDismiss(e, notification.id)}
                />
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        <DropdownMenuSeparator />
        <div className="p-2">
          <Button variant="ghost" size="sm" className="w-full justify-center" asChild>
            <Link href="/notifications">View all notifications</Link>
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface NotificationItemProps {
  notification: Notification;
  onClick: () => void;
  onDismiss: (e: React.MouseEvent) => void;
}

function NotificationItem({ notification, onClick, onDismiss }: NotificationItemProps) {
  const isUnread = !notification.read_at;
  const content = (
    <div
      className={cn(
        "flex gap-3 p-3 hover:bg-muted/50 transition-colors cursor-pointer group",
        isUnread && "bg-primary/5"
      )}
      onClick={onClick}
    >
      {/* Unread indicator */}
      <div className="flex-shrink-0 pt-1">
        <div
          className={cn(
            "h-2 w-2 rounded-full",
            isUnread ? "bg-primary" : "bg-transparent"
          )}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        <p className={cn("text-sm leading-tight", isUnread && "font-medium")}>
          {notification.title}
        </p>
        {notification.body && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {notification.body}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {formatDistanceToNow(parseUTCDate(notification.created_at), { addSuffix: true })}
        </p>
      </div>

      {/* Actions */}
      <div className="flex-shrink-0 flex items-start gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {notification.action_url && (
          <Button variant="ghost" size="icon" className="h-6 w-6" asChild>
            <Link href={notification.action_url}>
              <ExternalLink className="h-3 w-3" />
              <span className="sr-only">Open</span>
            </Link>
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-destructive"
          onClick={onDismiss}
        >
          <X className="h-3 w-3" />
          <span className="sr-only">Dismiss</span>
        </Button>
      </div>
    </div>
  );

  // Wrap in link if action URL exists
  if (notification.action_url) {
    return (
      <Link href={notification.action_url} className="block">
        {content}
      </Link>
    );
  }

  return content;
}
