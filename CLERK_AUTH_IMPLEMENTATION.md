# Clerk Authentication Implementation Guide

**Status:** ✅ Implementation Complete
**Date:** 2025-12-11
**Model Used:** Claude Sonnet 4.5

---

## Overview

This document describes the complete Clerk authentication integration for the RAG Transcript System. All code has been implemented and is ready for testing.

---

## What Was Implemented

### Backend Changes (8 files modified/created)

#### 1. **Configuration** (`backend/app/core/config.py`)
- Added Clerk settings:
  - `clerk_secret_key`: Backend secret key for JWT verification
  - `clerk_publishable_key`: Public key (for reference)
  - `clerk_jwt_verification`: Toggle for JWT verification (dev vs prod)

#### 2. **Authentication Module** (`backend/app/core/auth.py`) - NEW FILE
- `ClerkJWTVerifier` class:
  - Fetches JWKS from Clerk
  - Verifies JWT signatures using RS256
  - Supports dev mode (no verification) via config flag
- `get_current_user()` dependency:
  - Extracts Bearer token from Authorization header
  - Validates JWT and extracts Clerk user ID
  - Looks up user by `clerk_user_id`
  - **Lazy user creation**: Creates user on first login with:
    - Email from JWT claims
    - Default `free` subscription tier
    - Active status
- `get_current_active_superuser()` dependency:
  - Additional check for superuser routes

#### 3. **User Model** (`backend/app/models/user.py`)
- Added `clerk_user_id` field:
  - Type: `String(255)`
  - Unique, indexed, nullable
  - Maps Clerk's user ID to app's user record

#### 4. **Database Migration** (`backend/alembic/versions/005_add_clerk_user_id.py`) - NEW FILE
- Adds `clerk_user_id` column to users table
- Creates unique constraint and index
- Includes rollback logic

#### 5. **Route Updates** (5 files)
Replaced mock `get_current_user()` with Clerk auth in:
- `backend/app/api/routes/videos.py`
- `backend/app/api/routes/conversations.py`
- `backend/app/api/routes/collections.py`
- `backend/app/api/routes/jobs.py`
- `backend/app/api/routes/usage.py`
- `backend/app/api/routes/settings.py`

All routes now import: `from app.core.auth import get_current_user`

#### 6. **Dependencies** (`backend/requirements.txt`)
- Added: `pyjwt[crypto]==2.8.0` for JWT verification

---

### Frontend Changes (8 files modified/created)

#### 1. **Package Dependencies** (`frontend/package.json`)
- Added: `@clerk/nextjs: ^5.7.1`

#### 2. **Providers Setup** (`frontend/src/app/providers.tsx`)
- Wrapped app with `<ClerkProvider>`
- Added `<AuthInitializer />` component to configure API client

#### 3. **API Client** (`frontend/src/lib/api/client.ts`)
- Removed localStorage token logic
- Added `setClerkTokenGetter()` function
- Request interceptor now calls Clerk's `getToken()` async
- Response interceptor redirects to `/sign-in` on 401

#### 4. **Auth Initializer** (`frontend/src/components/auth-initializer.tsx`) - NEW FILE
- Client component that uses `useAuth()` hook
- Sets up token getter for API client
- Runs once on app mount

#### 5. **Sign-In Page** (`frontend/src/app/sign-in/[[...sign-in]]/page.tsx`) - NEW FILE
- Uses Clerk's `<SignIn />` component
- Styled with Tailwind
- Configured routing: `/sign-in` → `/sign-up`

#### 6. **Sign-Up Page** (`frontend/src/app/sign-up/[[...sign-up]]/page.tsx`) - NEW FILE
- Uses Clerk's `<SignUp />` component
- Styled with Tailwind
- Configured routing: `/sign-up` → `/sign-in`

#### 7. **Middleware** (`frontend/src/middleware.ts`) - NEW FILE
- Protects all routes except:
  - `/sign-in`
  - `/sign-up`
  - `/` (landing page)
- Uses Clerk's `clerkMiddleware()` with `auth.protect()`

#### 8. **Environment Variables** (`.env.example` files)
- Backend: Added Clerk secret/publishable keys
- Frontend: Added Clerk publishable key and route URLs

---

## File Structure After Implementation

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py           # ✏️ Modified - Added Clerk settings
│   │   └── auth.py             # ✨ NEW - Clerk JWT verification
│   ├── models/
│   │   └── user.py             # ✏️ Modified - Added clerk_user_id
│   ├── api/routes/
│   │   ├── videos.py           # ✏️ Modified - Import auth from core
│   │   ├── conversations.py    # ✏️ Modified - Import auth from core
│   │   ├── collections.py      # ✏️ Modified - Import auth from core
│   │   ├── jobs.py             # ✏️ Modified - Import auth from core
│   │   ├── usage.py            # ✏️ Modified - Import auth from core
│   │   └── settings.py         # ✏️ Modified - Import auth from core
│   └── alembic/versions/
│       └── 005_add_clerk_user_id.py  # ✨ NEW - Migration
├── requirements.txt            # ✏️ Modified - Added pyjwt
└── .env.example                # ✏️ Modified - Added Clerk vars

frontend/
├── src/
│   ├── app/
│   │   ├── providers.tsx                        # ✏️ Modified - ClerkProvider
│   │   ├── sign-in/[[...sign-in]]/page.tsx     # ✨ NEW
│   │   └── sign-up/[[...sign-up]]/page.tsx     # ✨ NEW
│   ├── components/
│   │   └── auth-initializer.tsx                 # ✨ NEW
│   ├── lib/api/
│   │   └── client.ts                            # ✏️ Modified - Clerk token
│   └── middleware.ts                            # ✨ NEW - Route protection
├── package.json                # ✏️ Modified - Added @clerk/nextjs
└── .env.example                # ✨ NEW - Clerk config
```

---

## Setup Instructions

### 1. Create Clerk Account & Application

1. Go to [https://dashboard.clerk.com](https://dashboard.clerk.com)
2. Sign up or log in
3. Create a new application
4. Choose authentication methods (Email + Google/GitHub recommended)
5. Copy the API keys from the dashboard

### 2. Configure Backend

1. Copy `.env.example` to `.env`:
   ```bash
   cd backend
   cp .env.example .env
   ```

2. Edit `.env` and add your Clerk keys:
   ```env
   CLERK_SECRET_KEY="sk_test_YOUR_ACTUAL_SECRET_KEY_HERE"
   CLERK_PUBLISHABLE_KEY="pk_test_YOUR_ACTUAL_PUBLISHABLE_KEY_HERE"
   CLERK_JWT_VERIFICATION=True
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migration:
   ```bash
   alembic upgrade head
   ```

### 3. Configure Frontend

1. Copy `.env.example` to `.env.local`:
   ```bash
   cd frontend
   cp .env.example .env.local
   ```

2. Edit `.env.local` and add your Clerk key:
   ```env
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_YOUR_ACTUAL_PUBLISHABLE_KEY_HERE"
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

### 4. Start the Application

1. **Backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

2. **Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the app:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## Testing the Implementation

### Test Flow

1. **Visit Frontend:** Navigate to `http://localhost:3000`
   - Should redirect to `/sign-in` (middleware protection)

2. **Sign Up:**
   - Click "Sign Up" or go to `/sign-up`
   - Enter email and password (or use Google/GitHub)
   - Verify email if required by your Clerk settings

3. **First Login:**
   - After successful authentication, Clerk redirects to `/videos`
   - Backend receives JWT token in Authorization header
   - `get_current_user()` extracts Clerk user ID
   - New user record is created automatically in database
   - User is assigned `free` tier by default

4. **Verify User Creation:**
   - Check database: `SELECT * FROM users;`
   - Should see user with `clerk_user_id` populated

5. **Test Protected Routes:**
   - Navigate to `/videos`, `/conversations`, etc.
   - All should work with authenticated requests

6. **Test API Calls:**
   - Open browser DevTools → Network tab
   - Watch API requests - should include `Authorization: Bearer <jwt>`
   - Backend should respond with user-specific data

7. **Test Logout:**
   - Sign out via Clerk user menu
   - Try to access `/videos` → should redirect to `/sign-in`

### Troubleshooting

**Backend Issues:**

1. **JWT verification fails:**
   - Check `CLERK_SECRET_KEY` is correct
   - Temporarily set `CLERK_JWT_VERIFICATION=False` for debugging (NOT for production)

2. **User not created on first login:**
   - Check backend logs for errors
   - Verify email is present in JWT claims
   - Check database connection

3. **401 Unauthorized:**
   - Verify token is being sent: Check browser DevTools → Network → Headers
   - Verify backend can reach Clerk JWKS endpoint (internet required)

**Frontend Issues:**

1. **Clerk components not showing:**
   - Check `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set
   - Verify key starts with `pk_test_` or `pk_live_`
   - Check browser console for errors

2. **API calls fail with 401:**
   - Check `AuthInitializer` is rendering
   - Verify `getToken()` is being called (add console.log in client.ts)
   - Check token is not expired (Clerk auto-refreshes)

3. **Infinite redirects:**
   - Check middleware `isPublicRoute()` matcher includes current route
   - Verify Clerk sign-in URL matches: `/sign-in`

---

## Architecture Details

### Authentication Flow

```
┌─────────────┐
│   Browser   │
│  (Next.js)  │
└──────┬──────┘
       │
       │ 1. User signs in via Clerk
       ▼
┌──────────────┐
│    Clerk     │
│   (OAuth)    │
└──────┬───────┘
       │
       │ 2. JWT token issued
       ▼
┌──────────────┐
│  Frontend    │
│  (API call)  │
└──────┬───────┘
       │
       │ 3. Authorization: Bearer <jwt>
       ▼
┌──────────────────────┐
│  Backend Middleware  │
│  (get_current_user)  │
└──────┬───────────────┘
       │
       │ 4. Verify JWT signature (Clerk JWKS)
       │ 5. Extract clerk_user_id from token
       │ 6. Lookup/create user in database
       ▼
┌─────────────┐
│  Database   │
│   (User)    │
└─────────────┘
```

### Token Lifecycle

1. **Token Generation:**
   - User signs in → Clerk generates JWT
   - Token stored in Clerk SDK (httpOnly cookie + memory)

2. **Token Usage:**
   - Frontend calls `getToken()` from `useAuth()` hook
   - Token getter set in API client interceptor
   - Every API request includes: `Authorization: Bearer <jwt>`

3. **Token Verification (Backend):**
   - Extract token from header
   - Decode header to get `kid` (key ID)
   - Fetch JWKS from Clerk (cached)
   - Verify signature using matching public key
   - Extract claims (user ID, email, etc.)

4. **Token Refresh:**
   - Clerk automatically refreshes tokens before expiry
   - No manual refresh needed

### User Mapping

```
Clerk User              App User
─────────────────       ─────────────────
user_2abc123xyz    →    clerk_user_id: "user_2abc123xyz"
email: john@...         email: "john@..."
                        id: <uuid>
                        subscription_tier: "free"
```

---

## Security Considerations

### What's Protected

✅ **All API endpoints** require valid JWT token
✅ **All frontend routes** (except `/sign-in`, `/sign-up`, `/`)
✅ **User data isolation** - queries filtered by `current_user.id`
✅ **JWT signature verification** using Clerk's public keys

### Best Practices Implemented

1. **JWT Verification:** Always enabled in production
2. **HTTPS Required:** Use HTTPS in production for token security
3. **No Password Storage:** Clerk handles all credentials
4. **Automatic Token Refresh:** Clerk SDK manages token lifecycle
5. **User Scoping:** All data queries include `user_id` filter

### What to Add Later

- **Rate Limiting:** Add per-user API rate limits
- **Webhook Handlers:** Sync user updates from Clerk webhooks
- **Role-Based Access:** Add permissions for team features
- **Audit Logging:** Track who accessed what and when

---

## Next Steps

### Phase A: Usage Tracking (Ready to Implement)

With authentication in place, you can now implement quota enforcement:

1. **Quota Service** (`backend/app/services/quota_service.py`):
   - Check user's subscription tier
   - Enforce limits on ingest/chat/storage
   - Record usage events

2. **Usage Events Tracking:**
   - Every video ingest → record event
   - Every chat message → record event
   - Aggregate for billing

3. **Frontend Usage Dashboard:**
   - Show quota usage per user
   - Display warnings at 80% usage
   - Suggest upgrade at limit

### Phase B: Stripe Integration (Future)

1. Add Stripe customer creation on user signup
2. Link `stripe_customer_id` to user record
3. Handle subscription webhooks
4. Implement metered billing for overages

---

## Migration from Mock Auth

### Existing Users (if any)

If you have existing users in the database from the mock auth:

1. **Option 1: Manual Migration**
   - Users re-register with Clerk
   - Admin manually links old data to new `clerk_user_id`

2. **Option 2: Clerk Import**
   - Use Clerk's user import API
   - Bulk import existing users
   - Send password reset emails

3. **Option 3: Hybrid Mode (deprecated)**
   - Legacy mock auth is removed; Clerk-only is the supported path.
   - If you still need migration, keep a one-time script to link prior users, but do not run dual auth in-app.

---

## Support & Resources

- **Clerk Documentation:** https://clerk.com/docs
- **Clerk Dashboard:** https://dashboard.clerk.com
- **Next.js Integration:** https://clerk.com/docs/quickstarts/nextjs
- **FastAPI Integration:** https://clerk.com/docs/backend-requests/handling/python

---

## Summary

✅ **Backend:** Complete - JWT verification, user lookup/creation, all routes protected
✅ **Frontend:** Complete - Sign-in/up pages, token injection, route protection
✅ **Database:** Complete - Migration ready, `clerk_user_id` field added
✅ **Environment:** Complete - `.env.example` files updated

**Status:** Ready for testing! Just add your Clerk API keys and run migrations.
