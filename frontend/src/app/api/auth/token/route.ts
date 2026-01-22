import { NextRequest, NextResponse } from "next/server"
import { SignJWT } from "jose"
import { cookies } from "next/headers"

// Force dynamic rendering since we access request headers
export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  try {
    // Forward the cookies to the session endpoint
    const cookieStore = await cookies()
    const cookieHeader = cookieStore.getAll()
      .map(c => `${c.name}=${c.value}`)
      .join('; ')

    console.log("[Token API] Forwarding cookies to session endpoint")

    // Fetch session from our own session endpoint (which works)
    const sessionResponse = await fetch(`${request.nextUrl.origin}/api/auth/session`, {
      headers: {
        'Cookie': cookieHeader,
      },
    })

    const session = await sessionResponse.json()

    console.log("[Token API] Session from endpoint:", session ? `user=${session?.user?.email}` : "null/empty")

    if (!session?.user?.email) {
      console.log("[Token API] No valid session found")
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 })
    }

    // Generate a simple JWT for the backend
    const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!)

    const jwt = await new SignJWT({
      sub: session.user.id || session.user.email,
      email: session.user.email,
      name: session.user.name || "",
      picture: session.user.image || "",
    })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("7d")
      .sign(secret)

    console.log("[Token API] Generated JWT for user:", session.user.email)
    return NextResponse.json({ token: jwt })
  } catch (error) {
    console.error("[Token API] Error:", error)
    return NextResponse.json({ error: "Token fetch failed" }, { status: 500 })
  }
}
