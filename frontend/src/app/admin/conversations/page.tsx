"use client";

import { useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, MessageSquare, Search } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function AdminConversationsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const pageSize = 20;

  const { data, isLoading, error, isFetching, refetch } = useQuery({
    queryKey: ["admin-conversations", page, search],
    queryFn: () =>
      adminApi.listConversations({
        page,
        page_size: pageSize,
        search: search || undefined,
      }),
    placeholderData: (previousData) => previousData,
  });

  const totalPages = data ? Math.max(Math.ceil(data.total / pageSize), 1) : 1;

  const handleSearch = () => {
    setPage(1);
    setSearch(searchInput);
  };

  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Conversations</h1>
          <p className="text-muted-foreground">
            Read-only view of active and historic conversations.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          Refresh
        </Button>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[240px] flex items-center gap-2">
            <Input
              placeholder="Search by title..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyPress}
            />
            <Button onClick={handleSearch}>
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </div>
          <Badge variant="outline" className="text-xs">
            {data?.total ?? 0} total
          </Badge>
        </div>
      </Card>

      {error && (
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load conversations</p>
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
              <TableHead>Title</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Messages</TableHead>
              <TableHead>Tokens</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Last Activity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(6)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-40" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                </TableRow>
              ))
            ) : data && data.conversations.length > 0 ? (
              data.conversations.map((conversation) => (
                <TableRow key={conversation.id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {conversation.title || "Untitled"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {conversation.id.slice(0, 8)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium">
                        {conversation.user_email || "Unknown"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {conversation.user_id.slice(0, 8)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">
                    {conversation.message_count}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {(conversation.total_tokens || 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(conversation.started_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {conversation.last_message_at ? (
                      formatDistanceToNow(new Date(conversation.last_message_at), {
                        addSuffix: true,
                      })
                    ) : (
                      <Badge variant="outline" className="text-xs">
                        No activity
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <MessageSquare className="h-5 w-5" />
                    <p>No conversations yet.</p>
                  </div>
                </TableCell>
              </TableRow>
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
    </div>
  );
}
