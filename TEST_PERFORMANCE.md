# Performance Testing Guide

## How to Test Navigation Performance

### Step 1: Stop Current Server

```bash
# Kill any running dev servers
pkill -f "next dev"
pkill -f "npm run dev"
```

### Step 2: Start Development Server with Logging

```bash
cd /Users/simonchia/projects/rag-transcript/frontend
npm run dev
```

### Step 3: Open Browser with DevTools

1. Open Chrome
2. Navigate to `http://localhost:3000`
3. Open DevTools (Cmd+Option+I / F12)
4. Go to **Console** tab
5. Clear console (Cmd+K)

### Step 4: Test Navigation

Navigate between pages:
```
/videos → /conversations → /collections → /videos
```

### Step 5: Check Console Logs

Look for these log messages:

#### Middleware Logs (Server-Side)
```
[Middleware] Request to /videos - isPublic: true/false, isDev: true/false
[Middleware] auth().protect() took XXXms for /videos
[Middleware] Total middleware time: XXXms for /videos
```

#### Performance Logs (Client-Side)
```
[Performance] Navigation started to /videos
[Performance] Render #1 at /videos { timeSinceNavigationStart: XXXms }
[Performance] Page interactive at /videos { totalTime: XXXms }
```

#### Parallel Fetch Logs (Client-Side)
```
[ParallelFetch] { authenticated: true, timing: { authMs, dataMs, totalMs }}
```

---

## What to Look For

### If Middleware is the Bottleneck

```
[Middleware] auth().protect() took 5000ms for /videos  ← THIS IS THE PROBLEM
```

**Solution**: Routes should be public in development mode.

### If Client Auth is the Bottleneck

```
[ParallelFetch] { timing: { authMs: 5000ms }}  ← THIS IS THE PROBLEM
```

**Solution**: Token caching not working.

### If Data Fetch is Slow

```
[ParallelFetch] { timing: { dataMs: 5000ms }}  ← Backend is slow
```

**Solution**: Backend optimization needed.

---

## Expected Results (Good Performance)

```
[Middleware] Total middleware time: <100ms for /videos
[Performance] Page interactive at /videos { totalTime: 500-1500ms }
[ParallelFetch] { timing: { authMs: 50-200ms, dataMs: 100-500ms, totalMs: 500-1000ms }}
```

---

## Common Issues

### Issue 1: Routes Not Public in Development

**Symptom**:
```
[Middleware] Request to /videos - isPublic: false, isDev: true
[Middleware] auth().protect() took 5000ms
```

**Fix**: Check `frontend/src/middleware.ts` line 12 - should include all app routes.

### Issue 2: Running Production Build Locally

**Symptom**:
```
[Middleware] Request to /videos - isPublic: false, isDev: false
```

**Fix**: Use `npm run dev` NOT `npm start` (production mode blocks on auth).

### Issue 3: Clerk Keys Invalid

**Symptom**: No middleware logs at all, blank pages.

**Fix**: Check `.env.local` for valid `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.

### Issue 4: AuthProvider Not Working

**Symptom**: Console shows errors about `useAuth()` context.

**Fix**: Verify `AuthProvider` wraps app in `app/providers.tsx`.

---

## Performance Debugging Checklist

- [ ] Server running with `npm run dev` (not `npm start`)
- [ ] Console shows middleware logs
- [ ] Middleware reports `isDev: true`
- [ ] Routes reported as `isPublic: true` in development
- [ ] `auth().protect()` takes <100ms (or doesn't run)
- [ ] Client `[Performance]` logs show <2000ms total
- [ ] `[ParallelFetch]` logs show auth + data in parallel
- [ ] No React errors in console
- [ ] No network errors in Network tab

---

## Network Tab Check

1. Open DevTools → Network tab
2. Navigate to /videos
3. Check **Timing** column for the page request

Expected:
- **Waiting (TTFB)**: <500ms
- **Content Download**: <100ms
- **Total**: <1000ms

If **Waiting (TTFB)** is >5000ms, the server middleware is blocking.

---

## Report Results

After testing, report:

1. **Middleware logs** - Are routes public? How long does auth().protect() take?
2. **Performance logs** - How long until page interactive?
3. **Parallel fetch logs** - Are auth and data actually parallel? Timings?
4. **Network tab** - What's the TTFB for page requests?
5. **Environment** - Running dev server (`npm run dev`) or production (`npm start`)?

This will help identify the exact bottleneck.
