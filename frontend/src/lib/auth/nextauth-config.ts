import NextAuth from "next-auth"
import type { NextAuthConfig } from "next-auth"
import GoogleProvider from "next-auth/providers/google"

export const authConfig: NextAuthConfig = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
        },
      },
    }),
  ],

  pages: {
    signIn: "/login",
    error: "/login", // Redirect errors to login page
  },

  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60, // 7 days (industry best practice)
  },

  cookies: {
    sessionToken: {
      name: "next-auth.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },

  callbacks: {
    async jwt({ token, user, account }) {
      // First sign in
      if (user && account) {
        token.id = user.id
        token.email = user.email
        token.name = user.name
        token.picture = user.image
        token.provider = account.provider
        token.providerAccountId = account.providerAccountId
      }
      return token
    },

    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
        session.user.email = token.email as string
        session.user.name = token.name as string
        session.user.image = token.picture as string
      }
      return session
    },

    async redirect({ url, baseUrl }) {
      // Allow callback URLs on the same origin
      if (url.startsWith("/")) return `${baseUrl}${url}`
      else if (new URL(url).origin === baseUrl) return url
      return baseUrl
    },
  },

  events: {
    async signIn({ user }) {
      console.log(`[NextAuth] User signed in: ${user.email}`)
    },
    async signOut() {
      console.log(`[NextAuth] User signed out`)
    },
  },
}

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig)
