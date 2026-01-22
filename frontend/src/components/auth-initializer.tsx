"use client"

import { useRef } from "react"
import { useAuth } from "@/lib/auth"
import { setAuthTokenGetter } from "@/lib/api/client"

export function AuthInitializer() {
  const auth = useAuth()
  const registeredRef = useRef(false)

  // Register a token getter used by the shared API client.
  // Do this during render so requests fired on first paint can attach a token.
  if (!registeredRef.current) {
    setAuthTokenGetter(async () => {
      try {
        return await auth.getToken()
      } catch {
        return null
      }
    })
    registeredRef.current = true
  }

  return null
}
