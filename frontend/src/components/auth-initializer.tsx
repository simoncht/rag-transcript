"use client";

import { useRef } from "react";
import { useAuth } from "@clerk/nextjs";

import { setClerkTokenGetter } from "@/lib/api/client";

export function AuthInitializer() {
  const { getToken } = useAuth();
  const registeredRef = useRef(false);

  // Register a token getter used by the shared API client.
  // Do this during render so requests fired on first paint can attach a token.
  if (!registeredRef.current) {
    setClerkTokenGetter(async () => {
      try {
        return await getToken();
      } catch {
        return null;
      }
    });
    registeredRef.current = true;
  }

  return null;
}
