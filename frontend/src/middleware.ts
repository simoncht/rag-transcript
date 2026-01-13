import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// For local development: make all routes public since we're using test Clerk keys
const isLocalDevelopment = process.env.NODE_ENV === 'development';

const isPublicRoute = createRouteMatcher([
  "/",
  "/login",
  "/sign-in(.*)",
  "/sign-up(.*)",
  // Add all routes as public in development
  ...(isLocalDevelopment ? ["/videos(.*)", "/conversations(.*)", "/collections(.*)", "/admin(.*)"] : []),
]);

export default clerkMiddleware((auth, req) => {
  if (!isPublicRoute(req)) {
    auth().protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and static assets
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
