"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  User,
  Shield,
  Video,
  MessageSquare,
  Database,
  DollarSign,
  TrendingUp,
  Edit,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow, format } from "date-fns";
import { useParams } from "next/navigation";
import { useToast } from "@/hooks/use-toast";

export default function AdminUserDetailPage() {
  const params = useParams();
  const userId = params?.id as string;
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [quotaDialogOpen, setQuotaDialogOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => adminApi.getUserDetail(userId),
    enabled: !!userId,
  });

  const updateMutation = useMutation({
    mutationFn: (updates: {
      subscription_tier?: string;
      subscription_status?: string;
      is_active?: boolean;
      is_superuser?: boolean;
    }) => adminApi.updateUser(userId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast({
        title: "User updated",
        description: "User settings have been updated successfully.",
      });
      setEditDialogOpen(false);
    },
    onError: (error) => {
      toast({
        title: "Update failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      });
    },
  });

  const quotaMutation = useMutation({
    mutationFn: (quotas: {
      videos_limit?: number;
      minutes_limit?: number;
      messages_limit?: number;
      storage_mb_limit?: number;
    }) => adminApi.overrideQuota(userId, quotas),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      toast({
        title: "Quota updated",
        description: "User quota limits have been updated successfully.",
      });
      setQuotaDialogOpen(false);
    },
    onError: (error) => {
      toast({
        title: "Update failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      });
    },
  });

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load user details</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/admin/users">
            <Button variant="outline" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold">
              {isLoading ? (
                <Skeleton className="h-9 w-64" />
              ) : (
                data?.full_name || data?.email
              )}
            </h1>
            {!isLoading && data && (
              <p className="text-muted-foreground mt-1">{data.email}</p>
            )}
          </div>
        </div>
        {!isLoading && data && (
          <div className="flex items-center gap-2">
            <EditUserDialog
              user={data}
              open={editDialogOpen}
              onOpenChange={setEditDialogOpen}
              onSave={updateMutation.mutate}
              isLoading={updateMutation.isPending}
            />
            <EditQuotaDialog
              user={data}
              open={quotaDialogOpen}
              onOpenChange={setQuotaDialogOpen}
              onSave={quotaMutation.mutate}
              isLoading={quotaMutation.isPending}
            />
          </div>
        )}
      </div>

      {/* User Info Card */}
      <Card className="p-6">
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Subscription Tier
            </p>
            {isLoading ? (
              <Skeleton className="h-6 w-20 mt-1" />
            ) : (
              <Badge variant="secondary" className="mt-1 capitalize">
                {data?.subscription_tier}
              </Badge>
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Status</p>
            {isLoading ? (
              <Skeleton className="h-6 w-16 mt-1" />
            ) : data?.is_active ? (
              <Badge variant="default" className="mt-1">
                Active
              </Badge>
            ) : (
              <Badge variant="destructive" className="mt-1">
                Inactive
              </Badge>
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Account Created
            </p>
            {isLoading ? (
              <Skeleton className="h-5 w-24 mt-1" />
            ) : (
              <p className="mt-1 text-sm">
                {format(new Date(data!.created_at), "MMM d, yyyy")}
              </p>
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Last Active
            </p>
            {isLoading ? (
              <Skeleton className="h-5 w-24 mt-1" />
            ) : data?.last_login_at ? (
              <p className="mt-1 text-sm">
                {formatDistanceToNow(new Date(data.last_login_at), {
                  addSuffix: true,
                })}
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">Never</p>
            )}
          </div>
        </div>
        {!isLoading && data?.is_superuser && (
          <>
            <Separator className="my-4" />
            <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400">
              <Shield className="h-4 w-4" />
              <span className="text-sm font-medium">Administrator</span>
            </div>
          </>
        )}
      </Card>

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Videos"
          value={data?.metrics.videos_total || 0}
          subtitle={`${data?.metrics.videos_completed || 0} completed`}
          icon={Video}
          isLoading={isLoading}
        />
        <MetricCard
          title="Conversations"
          value={data?.metrics.conversations_total || 0}
          subtitle={`${data?.metrics.conversations_active || 0} active`}
          icon={MessageSquare}
          isLoading={isLoading}
        />
        <MetricCard
          title="Messages"
          value={data?.metrics.messages_sent || 0}
          subtitle={`${(data?.metrics.total_tokens || 0).toLocaleString()} tokens`}
          icon={MessageSquare}
          isLoading={isLoading}
        />
        <MetricCard
          title="Storage"
          value={`${(data?.metrics.storage_mb || 0).toFixed(1)} MB`}
          subtitle={`${(data?.metrics.total_transcription_minutes || 0).toFixed(0)} mins transcribed`}
          icon={Database}
          isLoading={isLoading}
        />
      </div>

      {/* Quota Usage */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Quota Usage</h2>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            <QuotaItem
              label="Videos"
              used={data?.metrics.quota_videos_used || 0}
              limit={data?.metrics.quota_videos_limit || 0}
            />
            <QuotaItem
              label="Minutes"
              used={data?.metrics.quota_minutes_used || 0}
              limit={data?.metrics.quota_minutes_limit || 0}
            />
            <QuotaItem
              label="Messages"
              used={data?.metrics.quota_messages_used || 0}
              limit={data?.metrics.quota_messages_limit || 0}
            />
            <QuotaItem
              label="Storage (MB)"
              used={data?.metrics.quota_storage_used || 0}
              limit={data?.metrics.quota_storage_limit || 0}
            />
          </div>
        )}
      </Card>

      {/* Cost Analysis */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Cost Analysis</h2>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            <CostItem
              label="Transcription Cost"
              value={data?.costs.transcription_cost || 0}
            />
            <CostItem
              label="Embedding Cost"
              value={data?.costs.embedding_cost || 0}
            />
            <CostItem label="LLM Cost" value={data?.costs.llm_cost || 0} />
            <CostItem
              label="Storage Cost"
              value={data?.costs.storage_cost || 0}
            />
            <Separator />
            <CostItem
              label="Total Cost"
              value={data?.costs.total_cost || 0}
              highlight
            />
            <CostItem
              label="Subscription Revenue"
              value={data?.costs.subscription_revenue || 0}
              positive
            />
            <Separator />
            <div className="flex items-center justify-between pt-2">
              <span className="font-semibold">Net Profit</span>
              <div className="flex items-center gap-2">
                <span
                  className={`text-lg font-bold ${
                    (data?.costs.net_profit || 0) >= 0
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  ${(data?.costs.net_profit || 0).toFixed(2)}
                </span>
                <Badge
                  variant={
                    (data?.costs.profit_margin || 0) >= 0
                      ? "default"
                      : "destructive"
                  }
                >
                  {(data?.costs.profit_margin || 0).toFixed(1)}% margin
                </Badge>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: number | string;
  subtitle: string;
  icon: React.ElementType;
  isLoading?: boolean;
}

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  isLoading,
}: MetricCardProps) {
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      {isLoading ? (
        <>
          <Skeleton className="h-8 w-20 mb-1" />
          <Skeleton className="h-4 w-32" />
        </>
      ) : (
        <>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
        </>
      )}
    </Card>
  );
}

interface QuotaItemProps {
  label: string;
  used: number;
  limit: number;
}

function QuotaItem({ label, used, limit }: QuotaItemProps) {
  const percentage = limit > 0 ? (used / limit) * 100 : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <Progress value={percentage} className="h-2" />
    </div>
  );
}

interface CostItemProps {
  label: string;
  value: number;
  highlight?: boolean;
  positive?: boolean;
}

function CostItem({ label, value, highlight, positive }: CostItemProps) {
  return (
    <div className="flex items-center justify-between">
      <span
        className={`text-sm ${highlight ? "font-semibold" : "text-muted-foreground"}`}
      >
        {label}
      </span>
      <span
        className={`${
          highlight
            ? "font-semibold text-lg"
            : positive
              ? "text-green-600 dark:text-green-400"
              : ""
        }`}
      >
        ${value.toFixed(2)}
      </span>
    </div>
  );
}

interface EditUserDialogProps {
  user: any;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (updates: any) => void;
  isLoading: boolean;
}

function EditUserDialog({
  user,
  open,
  onOpenChange,
  onSave,
  isLoading,
}: EditUserDialogProps) {
  const [tier, setTier] = useState(user.subscription_tier);
  const [status, setStatus] = useState(user.subscription_status);
  const [isActive, setIsActive] = useState(user.is_active);
  const [isSuperuser, setIsSuperuser] = useState(user.is_superuser);

  const handleSave = () => {
    onSave({
      subscription_tier: tier,
      subscription_status: status,
      is_active: isActive,
      is_superuser: isSuperuser,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Edit className="h-4 w-4 mr-2" />
          Edit User
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit User Settings</DialogTitle>
          <DialogDescription>
            Update subscription tier, status, and permissions.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Subscription Tier</Label>
            <Select value={tier} onValueChange={setTier}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Subscription Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="past_due">Past Due</SelectItem>
                <SelectItem value="canceled">Canceled</SelectItem>
                <SelectItem value="trialing">Trialing</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded border-gray-300"
            />
            <Label htmlFor="is_active">Account Active</Label>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_superuser"
              checked={isSuperuser}
              onChange={(e) => setIsSuperuser(e.target.checked)}
              className="rounded border-gray-300"
            />
            <Label htmlFor="is_superuser">Administrator</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EditQuotaDialogProps {
  user: any;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (quotas: any) => void;
  isLoading: boolean;
}

function EditQuotaDialog({
  user,
  open,
  onOpenChange,
  onSave,
  isLoading,
}: EditQuotaDialogProps) {
  const [videosLimit, setVideosLimit] = useState(
    user.metrics.quota_videos_limit.toString()
  );
  const [minutesLimit, setMinutesLimit] = useState(
    user.metrics.quota_minutes_limit.toString()
  );
  const [messagesLimit, setMessagesLimit] = useState(
    user.metrics.quota_messages_limit.toString()
  );
  const [storageLimit, setStorageLimit] = useState(
    user.metrics.quota_storage_limit.toString()
  );

  const handleSave = () => {
    onSave({
      videos_limit: parseInt(videosLimit),
      minutes_limit: parseInt(minutesLimit),
      messages_limit: parseInt(messagesLimit),
      storage_mb_limit: parseInt(storageLimit),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Edit className="h-4 w-4 mr-2" />
          Edit Quotas
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Override Quota Limits</DialogTitle>
          <DialogDescription>
            Set custom quota limits for this user.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Videos Limit</Label>
            <Input
              type="number"
              value={videosLimit}
              onChange={(e) => setVideosLimit(e.target.value)}
              className="mt-1"
            />
          </div>

          <div>
            <Label>Minutes Limit</Label>
            <Input
              type="number"
              value={minutesLimit}
              onChange={(e) => setMinutesLimit(e.target.value)}
              className="mt-1"
            />
          </div>

          <div>
            <Label>Messages Limit</Label>
            <Input
              type="number"
              value={messagesLimit}
              onChange={(e) => setMessagesLimit(e.target.value)}
              className="mt-1"
            />
          </div>

          <div>
            <Label>Storage Limit (MB)</Label>
            <Input
              type="number"
              value={storageLimit}
              onChange={(e) => setStorageLimit(e.target.value)}
              className="mt-1"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? "Saving..." : "Save Quotas"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
