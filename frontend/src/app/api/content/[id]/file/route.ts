import { NextRequest, NextResponse } from "next/server";
import { SignJWT } from "jose";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

// Server-side URL: inside Docker/Railway, backend uses internal networking
const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    // Get session from NextAuth cookies (same approach as /api/auth/token)
    const cookieStore = await cookies();
    const cookieHeader = cookieStore
      .getAll()
      .map((c) => `${c.name}=${c.value}`)
      .join("; ");

    // Server-to-server session call: use internal URL or localhost
    const baseUrl = process.env.NEXTAUTH_URL || request.nextUrl.origin;

    const sessionResponse = await fetch(`${baseUrl}/api/auth/session`, {
      headers: { Cookie: cookieHeader },
    });

    const session = await sessionResponse.json();

    if (!session?.user?.email) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    // Generate JWT for backend
    const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);
    const jwt = await new SignJWT({
      sub: session.user.id || session.user.email,
      email: session.user.email,
      name: session.user.name || "",
      picture: session.user.image || "",
    })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(secret);

    // Fetch file from backend API (use internal URL for container-to-container)
    const fileResponse = await fetch(
      `${BACKEND_INTERNAL_URL}/api/v1/content/${id}/file`,
      {
        headers: { Authorization: `Bearer ${jwt}` },
      }
    );

    if (!fileResponse.ok) {
      return NextResponse.json(
        { error: "File not found" },
        { status: fileResponse.status }
      );
    }

    // Stream the PDF back to the browser
    const blob = await fileResponse.blob();
    return new NextResponse(blob, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": "inline",
        "Cache-Control": "private, max-age=3600",
      },
    });
  } catch (error) {
    console.error("[Content File Proxy] Error:", error);
    return NextResponse.json(
      { error: "Failed to fetch file" },
      { status: 500 }
    );
  }
}
