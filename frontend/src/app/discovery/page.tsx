"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { useAuth, createParallelQueryFn, useAuthState } from "@/lib/auth";
import { MainLayout } from "@/components/layout/MainLayout";
import { discoveryApi } from "@/lib/api/discovery";
import {
  DiscoverySource,
  DiscoverySourceListResponse,
  DiscoveredContentListResponse,
  DiscoveredContent,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Plus,
  Trash2,
  Bell,
  BellOff,
  RefreshCw,
  Loader2,
  Youtube,
  Rss,
  Check,
  X,
  ExternalLink,
  Clock,
  Sparkles,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn, parseUTCDate } from "@/lib/utils";
import Link from "next/link";

export default function SubscriptionsPage() {
  const authProvider = useAuth();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [channelInput, setChannelInput] = useState("");

  // Fetch discovery sources
  const {
    data: sourcesData,
    isLoading: sourcesLoading,
  } = useQuery<DiscoverySourceListResponse>({
    queryKey: ["discovery-sources"],
    queryFn: createParallelQueryFn(authProvider, () => discoveryApi.listSources()),
    staleTime: 30_000,
    enabled: canFetch,
  });

  // Fetch discovered content
  const {
    data: contentData,
    isLoading: contentLoading,
  } = useQuery<DiscoveredContentListResponse>({
    queryKey: ["discovered-content"],
    queryFn: createParallelQueryFn(authProvider, () =>
      discoveryApi.listDiscoveredContent(0, 50, "pending")
    ),
    staleTime: 30_000,
    enabled: canFetch,
  });

  // Subscribe to channel mutation
  const subscribeMutation = useMutation({
    mutationFn: async (identifier: string) => {
      // First get channel info to validate
      const info = await discoveryApi.getChannelInfo(identifier);
      // Then create the source
      return discoveryApi.createSource({
        source_type: "youtube_channel",
        source_identifier: info.channel_id,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["discovery-sources"] });
      toast({
        title: "Subscribed",
        description: `Now following ${data.display_name}`,
      });
      setIsAddDialogOpen(false);
      setChannelInput("");
    },
    onError: (error: unknown) => {
      const axiosError = error as any;
      const detail = axiosError?.response?.data?.detail;
      let message = "Failed to subscribe. Please check the channel URL.";
      if (typeof detail === "string") message = detail;
      toast({
        title: "Subscribe failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  // Delete source mutation
  const deleteMutation = useMutation({
    mutationFn: discoveryApi.deleteSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discovery-sources"] });
      toast({ title: "Unsubscribed" });
    },
  });

  // Update source mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; is_active?: boolean; config?: any }) => {
      return discoveryApi.updateSource(id, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discovery-sources"] });
    },
  });

  // Action content mutation
  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "import" | "dismiss" }) => {
      return discoveryApi.actionContent(id, action);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["discovered-content"] });
      if (variables.action === "import") {
        queryClient.invalidateQueries({ queryKey: ["videos"] });
        toast({ title: "Video imported" });
      } else {
        toast({ title: "Dismissed" });
      }
    },
  });

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (!channelInput.trim()) return;
    subscribeMutation.mutate(channelInput.trim());
  };

  const sources = sourcesData?.sources ?? [];
  const pendingContent = contentData?.items ?? [];
  const pendingCount = contentData?.pending ?? 0;

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Content discovery</p>
            <h1 className="text-3xl font-semibold tracking-tight">Subscriptions</h1>
            <p className="text-sm text-muted-foreground">
              Follow YouTube channels and topics to discover new content.
            </p>
          </div>
          <Button className="gap-2" onClick={() => setIsAddDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Subscribe to channel
          </Button>
        </div>

        <Tabs defaultValue="sources" className="space-y-6">
          <TabsList>
            <TabsTrigger value="sources" className="gap-2">
              <Rss className="h-4 w-4" />
              Sources ({sources.length})
            </TabsTrigger>
            <TabsTrigger value="discovered" className="gap-2">
              <Sparkles className="h-4 w-4" />
              Discovered
              {pendingCount > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {pendingCount}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Sources Tab */}
          <TabsContent value="sources" className="space-y-4">
            {!canFetch ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  <p className="mb-4">Sign in to manage your subscriptions.</p>
                  <div className="flex justify-center gap-2">
                    <Button asChild>
                      <Link href="/sign-up">Create account</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/login">Sign in</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : sourcesLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3].map((i) => (
                  <Card key={i}>
                    <CardContent className="p-4">
                      <div className="flex gap-3">
                        <Skeleton className="h-12 w-12 rounded-full" />
                        <div className="flex-1 space-y-2">
                          <Skeleton className="h-4 w-3/4" />
                          <Skeleton className="h-3 w-1/2" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : sources.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  <Rss className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">No subscriptions yet</p>
                  <p className="text-sm mb-4">
                    Subscribe to YouTube channels to get notified about new videos.
                  </p>
                  <Button onClick={() => setIsAddDialogOpen(true)} className="gap-2">
                    <Plus className="h-4 w-4" />
                    Subscribe to channel
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {sources.map((source) => (
                  <SourceCard
                    key={source.id}
                    source={source}
                    onToggleActive={(active) =>
                      updateMutation.mutate({ id: source.id, is_active: active })
                    }
                    onToggleNotify={(notify) =>
                      updateMutation.mutate({
                        id: source.id,
                        config: { ...source.config, notify },
                      })
                    }
                    onDelete={() => deleteMutation.mutate(source.id)}
                    isDeleting={deleteMutation.isPending}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          {/* Discovered Content Tab */}
          <TabsContent value="discovered" className="space-y-4">
            {!canFetch ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  <p>Sign in to see discovered content.</p>
                </CardContent>
              </Card>
            ) : contentLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Card key={i}>
                    <CardContent className="p-4">
                      <div className="flex gap-4">
                        <Skeleton className="w-40 h-24 rounded-md" />
                        <div className="flex-1 space-y-2">
                          <Skeleton className="h-5 w-3/4" />
                          <Skeleton className="h-4 w-1/2" />
                          <Skeleton className="h-3 w-1/4" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : pendingContent.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">No new content discovered</p>
                  <p className="text-sm">
                    New videos from your subscriptions will appear here.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {pendingContent.map((content) => (
                  <DiscoveredContentCard
                    key={content.id}
                    content={content}
                    onImport={() => actionMutation.mutate({ id: content.id, action: "import" })}
                    onDismiss={() => actionMutation.mutate({ id: content.id, action: "dismiss" })}
                    isLoading={actionMutation.isPending}
                  />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* Subscribe Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Subscribe to a channel</DialogTitle>
            <DialogDescription>
              Enter a YouTube channel URL or handle to follow.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubscribe} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="channel-input">Channel URL or handle</Label>
              <Input
                id="channel-input"
                placeholder="https://youtube.com/@channel or @channel"
                value={channelInput}
                onChange={(e) => setChannelInput(e.target.value)}
                disabled={subscribeMutation.isPending}
              />
              <p className="text-xs text-muted-foreground">
                Examples: @mkbhd, https://youtube.com/c/MKBHD
              </p>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsAddDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={subscribeMutation.isPending || !channelInput.trim()}
                className="gap-2"
              >
                {subscribeMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Subscribing...
                  </>
                ) : (
                  "Subscribe"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}

interface SourceCardProps {
  source: DiscoverySource;
  onToggleActive: (active: boolean) => void;
  onToggleNotify: (notify: boolean) => void;
  onDelete: () => void;
  isDeleting: boolean;
}

function SourceCard({
  source,
  onToggleActive,
  onToggleNotify,
  onDelete,
  isDeleting,
}: SourceCardProps) {
  const getSourceIcon = () => {
    switch (source.source_type) {
      case "youtube_channel":
        return <Youtube className="h-5 w-5 text-red-500" />;
      default:
        return <Rss className="h-5 w-5" />;
    }
  };

  return (
    <Card className={cn(!source.is_active && "opacity-60")}>
      <CardContent className="p-4 space-y-4">
        <div className="flex gap-3">
          {/* Avatar */}
          <div className="flex-shrink-0">
            {source.display_image_url ? (
              <img
                src={source.display_image_url}
                alt={source.display_name}
                className="h-12 w-12 rounded-full object-cover"
              />
            ) : (
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                {getSourceIcon()}
              </div>
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-sm truncate">{source.display_name}</h3>
            <p className="text-xs text-muted-foreground capitalize">
              {source.source_type.replace("_", " ")}
            </p>
            {source.last_checked_at && (
              <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                <Clock className="h-3 w-3" />
                Checked{" "}
                {formatDistanceToNow(parseUTCDate(source.last_checked_at), {
                  addSuffix: true,
                })}
              </p>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={source.is_active}
                onCheckedChange={onToggleActive}
                id={`active-${source.id}`}
              />
              <Label htmlFor={`active-${source.id}`} className="text-xs">
                Active
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={source.config?.notify !== false}
                onCheckedChange={onToggleNotify}
                id={`notify-${source.id}`}
              />
              <Label htmlFor={`notify-${source.id}`} className="text-xs">
                Notify
              </Label>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
            onClick={onDelete}
            disabled={isDeleting}
          >
            <Trash2 className="h-4 w-4" />
            <span className="sr-only">Unsubscribe</span>
          </Button>
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-1">
          {!source.is_explicit && (
            <Badge variant="secondary" className="text-xs">
              Auto-followed
            </Badge>
          )}
          {source.config?.auto_import && (
            <Badge variant="secondary" className="text-xs">
              Auto-import
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface DiscoveredContentCardProps {
  content: DiscoveredContent;
  onImport: () => void;
  onDismiss: () => void;
  isLoading: boolean;
}

function DiscoveredContentCard({
  content,
  onImport,
  onDismiss,
  isLoading,
}: DiscoveredContentCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Thumbnail */}
          <div className="relative w-40 h-24 rounded-md overflow-hidden flex-shrink-0 bg-muted">
            {content.thumbnail_url ? (
              <img
                src={content.thumbnail_url}
                alt={content.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Youtube className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
            {content.preview_metadata?.duration_display && (
              <div className="absolute bottom-1 right-1 px-1 py-0.5 bg-black/80 text-white text-xs rounded">
                {content.preview_metadata.duration_display}
              </div>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-2">
            <h3 className="font-medium text-sm line-clamp-2">{content.title}</h3>
            <p className="text-xs text-muted-foreground">
              {content.preview_metadata?.channel_name || content.discovery_context?.channel_name}
            </p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="text-xs capitalize">
                {content.discovery_reason.replace("_", " ")}
              </Badge>
              {content.discovered_at && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDistanceToNow(parseUTCDate(content.discovered_at), {
                    addSuffix: true,
                  })}
                </span>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 flex-shrink-0">
            <Button
              size="sm"
              className="gap-1"
              onClick={onImport}
              disabled={isLoading}
            >
              <Check className="h-4 w-4" />
              Import
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="gap-1"
              onClick={onDismiss}
              disabled={isLoading}
            >
              <X className="h-4 w-4" />
              Dismiss
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
