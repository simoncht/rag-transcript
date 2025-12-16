"use client";

import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Shield, AlertCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoaded } = useUser();
  const router = useRouter();

  // Check if user is admin (stored in Clerk public metadata)
  const isAdmin = user?.publicMetadata?.is_superuser === true;

  useEffect(() => {
    if (isLoaded && !isAdmin) {
      // Redirect non-admin users to home page
      router.push("/videos");
    }
  }, [isLoaded, isAdmin, router]);

  // Loading state
  if (!isLoaded) {
    return (
      <div className="container mx-auto p-6 space-y-6">
        <div className="flex items-center gap-2 mb-6">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-16 mb-1" />
              <Skeleton className="h-3 w-24" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Access denied for non-admin users
  if (!isAdmin) {
    return (
      <div className="container mx-auto p-6">
        <Card className="p-8 border-destructive">
          <div className="flex flex-col items-center text-center gap-4">
            <div className="rounded-full bg-destructive/10 p-3">
              <AlertCircle className="h-8 w-8 text-destructive" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Access Denied</h1>
              <p className="text-muted-foreground mt-2">
                You do not have permission to access the admin dashboard.
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Only administrators can view this page.
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  // Admin access granted
  return (
    <div className="min-h-screen">
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-background border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            <span className="text-sm font-medium text-muted-foreground">
              Administrator Dashboard
            </span>
          </div>
        </div>
      </div>
      {children}
    </div>
  );
}
