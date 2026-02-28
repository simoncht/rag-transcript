import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import { cn } from "@/lib/utils"
import { Toaster } from "@/components/ui/toaster"
import { PerformanceLogger } from "@/components/PerformanceLogger"

const inter = Inter({ subsets: ["latin"] })

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://frontend-production-9252.up.railway.app'

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "RAG Transcript - AI-Powered Video Knowledge Base",
    template: "%s | RAG Transcript",
  },
  description:
    "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search. Chat with your videos and get precise, cited answers.",
  keywords: [
    // Core features
    "video transcription",
    "AI transcription",
    "semantic search",
    "YouTube transcription",
    "video knowledge base",
    "RAG",
    "AI transcription",
    // High-value long-tail keywords
    "YouTube to text",
    "video to text converter",
    "AI video search",
    "lecture transcription",
    "podcast transcription",
    "video summarizer",
    "YouTube transcript generator",
    "video Q&A",
    "video chatbot",
    "research video tool",
    "video citation tool",
    "transcribe YouTube videos",
    "search video content",
    "video note taking",
  ],
  authors: [{ name: "RAG Transcript" }],
  creator: "RAG Transcript",
  publisher: "RAG Transcript",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  alternates: {
    canonical: baseUrl,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: baseUrl,
    title: "RAG Transcript - AI-Powered Video Knowledge Base",
    description:
      "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search. Chat with your videos and get precise, cited answers.",
    siteName: "RAG Transcript",
    images: [
      {
        url: '/opengraph-image',
        width: 1200,
        height: 630,
        alt: 'RAG Transcript - AI-Powered Video Knowledge Base',
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "RAG Transcript - AI-Powered Video Knowledge Base",
    description:
      "Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search.",
    images: ['/opengraph-image'],
  },
  // Note: Next.js auto-generates favicons from src/app/icon.svg
  // To add full favicon support, generate files using https://realfavicongenerator.net/
  // and place in public/: favicon.ico, favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png
  manifest: '/site.webmanifest',
  category: 'technology',
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
