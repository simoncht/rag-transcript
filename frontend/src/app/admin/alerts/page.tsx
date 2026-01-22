"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function AdminAlertsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: () => adminApi.getAlerts(),
    refetchInterval: 30000,
  });

  const alerts = data?.alerts ?? [];

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Alerts</h1>
          <p className="text-muted-foreground">
            Policy and safety signals. Currently returns an empty list placeholder.
          </p>
        </div>
        <Badge variant="outline">Read only</Badge>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Detected</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(4)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                </TableRow>
              ))
            ) : alerts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                  <div className="flex flex-col items-center gap-2">
                    <AlertTriangle className="h-5 w-5" />
                    <p>No alerts yet.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              alerts.map((alert) => (
                <TableRow key={`${alert.user_id}-${alert.detected_at}`}>
                  <TableCell className="font-medium">{alert.alert_type}</TableCell>
                  <TableCell>{alert.user_email}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{alert.severity}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(alert.detected_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant={alert.is_resolved ? "outline" : "destructive"}>
                      {alert.is_resolved ? "Resolved" : "Open"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
