"use client"

import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Shield, AlertCircle } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { apiClient } from "@/lib/api/client"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { useAuthState } from "@/lib/auth"

const navItems = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/qa", label: "Q&A Feed" },
  { href: "/admin/conversations", label: "Conversations" },
  { href: "/admin/videos", label: "Videos" },
  { href: "/admin/collections", label: "Collections" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/alerts", label: "Alerts" },
]

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const authState = useAuthState()
  const router = useRouter()
  const pathname = usePathname()
  const [isAdminBackend, setIsAdminBackend] = useState<boolean | null>(null)

  useEffect(() => {
    if (!authState.isAuthenticated) {
      router.push("/sign-in")
      return
    }

    let isMounted = true

    const fetchAdminStatus = async () => {
      try {
        const response = await apiClient.get("/auth/me")
        if (isMounted) {
          setIsAdminBackend(Boolean(response.data?.is_superuser))
        }
      } catch {
        if (isMounted) {
          setIsAdminBackend(false)
        }
      }
    }

    fetchAdminStatus()

    return () => {
      isMounted = false
    }
  }, [authState.isAuthenticated, router])

  const hasAdminAccess = isAdminBackend === true

  useEffect(() => {
    if (isAdminBackend === false) {
      // Redirect non-admin users to home page
      router.push("/videos")
    }
  }, [isAdminBackend, router])

  // Loading state
  if (!authState.isAuthenticated || isAdminBackend === null) {
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
    )
  }

  // Access denied for non-admin users
  if (!hasAdminAccess) {
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
    )
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
      <div className="border-b bg-muted/40">
        <div className="container mx-auto px-6 py-3 flex flex-wrap gap-2">
          {navItems.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "text-sm px-3 py-2 rounded-md border transition-colors",
                  active
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background hover:bg-muted border-border"
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </div>
      </div>
      {children}
    </div>
  )
}
