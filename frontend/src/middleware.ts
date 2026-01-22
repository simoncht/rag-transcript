import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname
  console.log(`[Middleware] Request to ${path}`)

  // Public routes - no auth check needed
  const publicRoutes = [
    "/",
    "/pricing",
    "/login",
    "/sign-in",
    "/checkout",
    "/api",  // API routes handle their own auth
  ]

  if (publicRoutes.some(route => path.startsWith(route))) {
    return NextResponse.next()
  }

  // For protected routes, NextAuth session will be checked by the SessionProvider
  // The middleware just logs the request
  return NextResponse.next()
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
}
