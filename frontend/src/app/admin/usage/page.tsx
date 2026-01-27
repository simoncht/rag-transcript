"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Coins,
  Zap,
  TrendingDown,
  Clock,
  AlertTriangle,
  Database,
  Users,
  ArrowUpRight,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function LLMUsagePage() {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-llm-usage", days],
    queryFn: () => adminApi.getLLMUsage({ days, limit: 50 }),
    refetchInterval: 60000, // Refresh every minute
  });

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="font-semibold">Failed to load LLM usage data</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </Card>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-US").format(value);
  };

  const formatTokens = (value: number) => {
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)}M`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(1)}K`;
    }
    return value.toString();
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">LLM Usage & Costs</h1>
          <p className="text-muted-foreground mt-1">
            Monitor token usage, API costs, and cache performance
          </p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30, 90].map((d) => (
            <Button
              key={d}
              variant={days === d ? "default" : "outline"}
              size="sm"
              onClick={() => setDays(d)}
            >
              {d}d
            </Button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          [...Array(4)].map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-24 mb-1" />
              <Skeleton className="h-3 w-32" />
            </Card>
          ))
        ) : (
          <>
            <StatCard
              title="Total Cost"
              value={formatCurrency(data?.stats.total_cost_usd || 0)}
              subtitle={`${formatNumber(data?.stats.total_requests || 0)} requests`}
              icon={Coins}
              variant="default"
            />
            <StatCard
              title="Total Tokens"
              value={formatTokens(data?.stats.total_tokens || 0)}
              subtitle={`${formatTokens(data?.stats.total_input_tokens || 0)} in / ${formatTokens(data?.stats.total_output_tokens || 0)} out`}
              icon={Zap}
              variant="default"
            />
            <StatCard
              title="Cache Savings"
              value={formatCurrency(data?.stats.estimated_savings_usd || 0)}
              subtitle={`${((data?.stats.cache_hit_rate || 0) * 100).toFixed(1)}% hit rate`}
              icon={TrendingDown}
              variant="success"
            />
            <StatCard
              title="Avg Response Time"
              value={`${(data?.stats.avg_response_time_seconds || 0).toFixed(2)}s`}
              subtitle={`${formatTokens(data?.stats.total_cache_hit_tokens || 0)} cached tokens`}
              icon={Clock}
              variant="default"
            />
          </>
        )}
      </div>

      {/* Model Breakdown */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Requests by Model</h2>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(2)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(data?.stats.requests_by_model || {}).map(
              ([model, count]) => (
                <div
                  key={model}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <Database className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{model}</p>
                      <p className="text-sm text-muted-foreground">
                        {((count / (data?.stats.total_requests || 1)) * 100).toFixed(1)}% of requests
                      </p>
                    </div>
                  </div>
                  <Badge variant="secondary" className="text-lg">
                    {formatNumber(count)}
                  </Badge>
                </div>
              )
            )}
          </div>
        )}
      </Card>

      {/* Per-User Breakdown */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Users className="h-5 w-5" />
          <h2 className="text-xl font-semibold">Usage by User</h2>
        </div>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : data?.by_user && data.by_user.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead className="text-right">Requests</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Cache Hit Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.by_user.map((user) => (
                <TableRow key={user.user_id}>
                  <TableCell className="font-medium">
                    {user.user_email || user.user_id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatNumber(user.total_requests)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatTokens(user.total_tokens)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatCurrency(user.total_cost_usd)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant={user.cache_hit_rate > 0.5 ? "default" : "secondary"}
                    >
                      {(user.cache_hit_rate * 100).toFixed(1)}%
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            No usage data for this period
          </p>
        )}
      </Card>

      {/* Recent Events */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <ArrowUpRight className="h-5 w-5" />
          <h2 className="text-xl font-semibold">Recent API Calls</h2>
        </div>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(10)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : data?.recent_events && data.recent_events.length > 0 ? (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Input</TableHead>
                  <TableHead className="text-right">Output</TableHead>
                  <TableHead className="text-right">Cache</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                      {formatDate(event.created_at)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {event.user_email || event.user_id.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{event.model}</Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {formatTokens(event.input_tokens)}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {formatTokens(event.output_tokens)}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {event.cache_hit_tokens > 0 && (
                        <span className="text-green-600">
                          {formatTokens(event.cache_hit_tokens)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm font-medium">
                      {formatCurrency(event.cost_usd)}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {event.response_time_seconds?.toFixed(2)}s
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-8">
            No recent events
          </p>
        )}
      </Card>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ElementType;
  variant?: "default" | "success" | "warning";
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
}: StatCardProps) {
  const variants = {
    default: "",
    success: "border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/50",
    warning: "border-yellow-200 bg-yellow-50/50 dark:border-yellow-900 dark:bg-yellow-950/50",
  };

  const iconVariants = {
    default: "text-muted-foreground",
    success: "text-green-600 dark:text-green-400",
    warning: "text-yellow-600 dark:text-yellow-400",
  };

  return (
    <Card className={`p-6 ${variants[variant]}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <Icon className={`h-4 w-4 ${iconVariants[variant]}`} />
      </div>
      <div className="space-y-1">
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
    </Card>
  );
}
