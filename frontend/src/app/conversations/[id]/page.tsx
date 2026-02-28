"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

/**
 * Redirect: /conversations/[id] -> /chat/[id]
 * Preserves old URLs while the primary experience is now at /chat.
 */
export default function ConversationDetailRedirect() {
  const params = useParams();
  const router = useRouter();
  const conversationId = Array.isArray(params?.id) ? params.id[0] : params?.id;

  useEffect(() => {
    if (conversationId) {
      router.replace(`/chat/${conversationId}`);
    } else {
      router.replace("/chat");
    }
  }, [router, conversationId]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Redirecting to chat...
      </div>
    </div>
  );
}
