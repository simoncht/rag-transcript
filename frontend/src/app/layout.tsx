import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { cn } from "@/lib/utils";
import { ClerkProvider } from "@clerk/nextjs";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RAG Transcript System",
  description: "AI-powered video transcript chat application",
};

// Check if Clerk is configured with valid keys
const isClerkConfigured = () => {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  return publishableKey &&
         publishableKey.startsWith('pk_') &&
         !publishableKey.includes('xxxx');
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const content = (
    <html lang="en" suppressHydrationWarning>
      <body className={cn("min-h-screen bg-background font-sans antialiased", inter.className)}>
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );

  // Only use ClerkProvider if valid keys are configured
  if (isClerkConfigured()) {
    return <ClerkProvider>{content}</ClerkProvider>;
  }

  return content;
}
