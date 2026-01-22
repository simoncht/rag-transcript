"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, RefreshCw, MessageSquare, Timer } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const truncate = (value: string, limit = 120) => {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit)}…`;
};

export default function AdminQAFeedPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [auditPage, setAuditPage] = useState(1);
  const auditPageSize = 10;

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["admin-qa-feed", page],
    queryFn: () => adminApi.getQAFeed({ page, page_size: pageSize }),
    placeholderData: (previousData) => previousData,
    refetchInterval: 30000,
  });

  const {
    data: auditData,
    isLoading: auditLoading,
    isFetching: auditFetching,
    error: auditError,
    refetch: refetchAudit,
  } = useQuery({
    queryKey: ["admin-audit-messages", auditPage],
    queryFn: () =>
      adminApi.getAuditLogs({
        page: auditPage,
        page_size: auditPageSize,
      }),
    placeholderData: (previousData) => previousData,
    refetchInterval: 30000,
  });

  const items = data?.items ?? [];
  const totalPages = data ? Math.max(Math.ceil(data.total / pageSize), 1) : 1;
  const auditItems = auditData?.items ?? [];
  const auditTotalPages = auditData
    ? Math.max(Math.ceil(auditData.total / auditPageSize), 1)
    : 1;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-3xl font-bold">Q&A Feed</h1>
          <p className="text-muted-foreground">
            Live questions and answers for monitoring quality and safety.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load Q&A feed</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </Card>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Asked</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Question</TableHead>
              <TableHead>Answer</TableHead>
              <TableHead>Latency</TableHead>
              <TableHead>Tokens</TableHead>
              <TableHead>Flags</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(6)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell colSpan={2}>
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                </TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-10">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <MessageSquare className="h-5 w-5" />
                    <p>No questions captured yet.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.qa_id}>
                  <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(item.asked_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                  <TableCell className="text-sm">
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {item.user_email || "Unknown user"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {item.conversation_id.slice(0, 8)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    <p className="text-sm font-medium leading-tight">
                      {truncate(item.question)}
                    </p>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    {item.answer ? (
                      <p className="text-sm text-muted-foreground leading-tight">
                        {truncate(item.answer)}
                      </p>
                    ) : (
                      <Badge variant="outline" className="text-xs">
                        Pending answer
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {item.response_latency_ms ? (
                      <div className="flex items-center gap-1">
                        <Timer className="h-4 w-4 text-muted-foreground" />
                        <span>
                          {Math.round(item.response_latency_ms)} ms
                        </span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">–</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.input_tokens || item.output_tokens ? (
                      <span>
                        in {item.input_tokens ?? 0} / out{" "}
                        {item.output_tokens ?? 0}
                      </span>
                    ) : (
                      "n/a"
                    )}
                  </TableCell>
                  <TableCell className="space-x-1">
                    {item.flags?.length ? (
                      item.flags.map((flag) => (
                        <Badge key={flag} variant="secondary">
                          {flag}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline">clean</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 pt-10">
        <div>
          <h2 className="text-2xl font-semibold">Recent chat messages (audit)</h2>
          <p className="text-muted-foreground text-sm">
            Append-only view of user and assistant turns for oversight.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {auditData?.total ?? 0} captured
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchAudit()}
            disabled={auditFetching}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${auditFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {auditError && (
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load audit log</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {auditError instanceof Error ? auditError.message : "Unknown error"}
          </p>
        </Card>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Content</TableHead>
              <TableHead>Flags</TableHead>
              <TableHead>Tokens</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {auditLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                </TableRow>
              ))
            ) : auditItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <MessageSquare className="h-5 w-5" />
                    <p>No chat activity captured yet.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              auditItems.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(item.created_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                  <TableCell className="text-sm">
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {item.user_email || "Unknown user"}
                      </span>
                      {item.conversation_id && (
                        <span className="text-xs text-muted-foreground">
                          {item.conversation_id.slice(0, 8)}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.role || "n/a"}
                  </TableCell>
                  <TableCell className="max-w-xl">
                    <p className="text-sm leading-tight">
                      {item.content ? truncate(item.content, 160) : "—"}
                    </p>
                  </TableCell>
                  <TableCell className="space-x-1">
                    {item.flags?.length ? (
                      item.flags.map((flag) => (
                        <Badge key={flag} variant="secondary">
                          {flag}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline">clean</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.token_count
                      ? `${item.token_count} tokens`
                      : item.input_tokens || item.output_tokens
                      ? `in ${item.input_tokens ?? 0} / out ${
                          item.output_tokens ?? 0
                        }`
                      : "n/a"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {auditPage} of {auditTotalPages}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
            disabled={auditPage === 1}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAuditPage((p) => Math.min(auditTotalPages, p + 1))}
            disabled={auditPage >= auditTotalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
