"use client"

import { Suspense } from "react"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  // Get callback URL from query params (for post-login redirect)
  const callbackUrl = searchParams.get('callbackUrl') || '/videos'

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 rounded-2xl border bg-card p-8 shadow-sm">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold">Welcome to RAG Transcript</h1>
          <p className="text-muted-foreground">
            Transform YouTube videos into searchable knowledge with AI
          </p>
        </div>

        <div className="space-y-3">
          <Button
            onClick={() => router.push(`/sign-in?callbackUrl=${encodeURIComponent(callbackUrl)}`)}
            className="w-full"
            size="lg"
          >
            Sign In with Google
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            New users will automatically create an account
          </p>
        </div>

        <div className="text-center">
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back to home
          </Link>
        </div>
      </div>
    </div>
  )
}

function LoginFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 rounded-2xl border bg-card p-8 shadow-sm">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold">Welcome to RAG Transcript</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginContent />
    </Suspense>
  )
}
