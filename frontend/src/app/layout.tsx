import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import { cn } from "@/lib/utils"
import { Toaster } from "@/components/ui/toaster"
import { PerformanceLogger } from "@/components/PerformanceLogger"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: {
    default: "RAG Transcript - AI-Powered Video Knowledge Base",
    template: "%s | RAG Transcript",
  },
  description:
    "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search. Chat with your videos and get precise, cited answers.",
  keywords: [
    "video transcription",
    "AI transcription",
    "semantic search",
    "YouTube transcription",
    "video knowledge base",
    "RAG",
    "Whisper AI",
  ],
  authors: [{ name: "RAG Transcript" }],
  openGraph: {
    type: "website",
    title: "RAG Transcript - AI-Powered Video Knowledge Base",
    description:
      "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search.",
    siteName: "RAG Transcript",
  },
  twitter: {
    card: "summary_large_image",
    title: "RAG Transcript - AI-Powered Video Knowledge Base",
    description:
      "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search.",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn("min-h-screen bg-background font-sans antialiased", inter.className)}>
        <Providers>
          <PerformanceLogger />
          {children}
        </Providers>
        <Toaster />
      </body>
    </html>
  )
}
