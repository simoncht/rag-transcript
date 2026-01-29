"use client"

import { useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { SessionProvider } from "next-auth/react"

import { AuthInitializer } from "@/components/auth-initializer"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthProvider } from "@/lib/auth"
import { BreadcrumbProvider } from "@/contexts/BreadcrumbContext"

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  )

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <SessionProvider>
        <AuthProvider>
          <QueryClientProvider client={queryClient}>
            <BreadcrumbProvider>
              <AuthInitializer />
              {children}
            </BreadcrumbProvider>
          </QueryClientProvider>
        </AuthProvider>
      </SessionProvider>
    </ThemeProvider>
  )
}
