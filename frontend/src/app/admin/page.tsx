"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  Video,
  MessageSquare,
  Database,
  TrendingUp,
  TrendingDown,
  Clock,
  AlertTriangle,
  Activity,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AdminDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => adminApi.getDashboard(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="font-semibold">Failed to load admin dashboard</p>
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
        <div>
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            System overview and user management
          </p>
        </div>
        <Link href="/admin/users">
          <Button>
            <Users className="h-4 w-4 mr-2" />
            Manage Users
          </Button>
        </Link>
      </div>

      {/* System Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <>
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="p-6">
                <Skeleton className="h-4 w-20 mb-2" />
                <Skeleton className="h-8 w-16 mb-1" />
                <Skeleton className="h-3 w-24" />
              </Card>
            ))}
          </>
        ) : (
          <>
            <StatCard
              title="Total Users"
              value={data?.system_stats.total_users || 0}
              subtitle={`${data?.system_stats.active_users || 0} active`}
              icon={Users}
              trend={data?.system_stats.new_users_this_month || 0}
              trendLabel="new this month"
            />
            <StatCard
              title="Videos"
              value={data?.system_stats.total_videos || 0}
              subtitle={`${data?.system_stats.videos_completed || 0} completed`}
              icon={Video}
              badge={
                (data?.system_stats.videos_processing || 0) > 0
                  ? `${data?.system_stats.videos_processing} processing`
                  : undefined
              }
            />
            <StatCard
              title="Conversations"
              value={data?.system_stats.total_conversations || 0}
              subtitle={`${data?.system_stats.total_messages || 0} messages`}
              icon={MessageSquare}
            />
            <StatCard
              title="Storage"
              value={`${data?.system_stats.total_storage_gb.toFixed(1)} GB`}
              subtitle={`${(data?.system_stats.total_transcription_minutes || 0).toLocaleString()} mins transcribed`}
              icon={Database}
            />
          </>
        )}
      </div>

      {/* Subscription Tiers */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Subscription Tiers</h2>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            {Object.entries(data?.system_stats.users_by_tier || {}).map(
              ([tier, count]) => (
                <div
                  key={tier}
                  className="flex flex-col items-center justify-center p-4 border rounded-lg"
                >
                  <p className="text-3xl font-bold">{count}</p>
                  <p className="text-sm text-muted-foreground capitalize mt-1">
                    {tier}
                  </p>
                </div>
              )
            )}
          </div>
        )}
      </Card>

      {/* User Engagement */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">User Engagement Health</h2>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <EngagementCard
              label="Active"
              count={data?.engagement_stats.active_users || 0}
              variant="success"
              icon={Activity}
            />
            <EngagementCard
              label="At Risk"
              count={data?.engagement_stats.at_risk_users || 0}
              variant="warning"
              icon={Clock}
            />
            <EngagementCard
              label="Churning"
              count={data?.engagement_stats.churning_users || 0}
              variant="danger"
              icon={TrendingDown}
            />
            <EngagementCard
              label="Dormant"
              count={data?.engagement_stats.dormant_users || 0}
              variant="muted"
              icon={Users}
            />
          </div>
        )}
      </Card>

      {/* System Health */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">Processing Status</h2>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Completed Videos
                </span>
                <span className="font-semibold">
                  {data?.system_stats.videos_completed || 0}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Processing
                </span>
                <Badge variant="secondary">
                  {data?.system_stats.videos_processing || 0}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Failed</span>
                <Badge variant="destructive">
                  {data?.system_stats.videos_failed || 0}
                </Badge>
              </div>
            </div>
          )}
        </Card>

        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">Token Usage</h2>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Total Tokens
                </span>
                <span className="font-semibold">
                  {(data?.system_stats.total_tokens_used || 0).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Transcription Minutes
                </span>
                <span className="font-semibold">
                  {(data?.system_stats.total_transcription_minutes || 0).toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ElementType;
  trend?: number;
  trendLabel?: string;
  badge?: string;
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendLabel,
  badge,
}: StatCardProps) {
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <p className="text-2xl font-bold">{value}</p>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
        {trend !== undefined && trendLabel && (
          <div className="flex items-center gap-1 text-xs">
            <TrendingUp className="h-3 w-3 text-green-500" />
            <span className="text-green-500 font-medium">{trend}</span>
            <span className="text-muted-foreground">{trendLabel}</span>
          </div>
        )}
        {badge && <Badge variant="secondary">{badge}</Badge>}
      </div>
    </Card>
  );
}

interface EngagementCardProps {
  label: string;
  count: number;
  variant: "success" | "warning" | "danger" | "muted";
  icon: React.ElementType;
}

function EngagementCard({
  label,
  count,
  variant,
  icon: Icon,
}: EngagementCardProps) {
  const variants = {
    success: "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950",
    warning: "border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950",
    danger: "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950",
    muted: "border-muted bg-muted/50",
  };

  const iconVariants = {
    success: "text-green-600 dark:text-green-400",
    warning: "text-yellow-600 dark:text-yellow-400",
    danger: "text-red-600 dark:text-red-400",
    muted: "text-muted-foreground",
  };

  return (
    <div className={`flex items-center gap-4 p-4 border rounded-lg ${variants[variant]}`}>
      <Icon className={`h-8 w-8 ${iconVariants[variant]}`} />
      <div>
        <p className="text-2xl font-bold">{count}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}
