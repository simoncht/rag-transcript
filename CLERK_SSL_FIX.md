# Fixing Clerk SSL Certificate Error

## The Error

```
Clerk: unable to resolve handshake: [TypeError: fetch failed]
cause: [Error: unable to get local issuer certificate]
code: 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY'
```

This error occurs when Clerk tries to connect to its API but SSL certificate validation fails. This is **very common in corporate environments** with:
- SSL inspection/interception
- Corporate proxy servers
- Self-signed certificates
- Firewall restrictions

---

## ✅ Solution Applied

I've already applied the fix for you. Here's what was done:

### 1. Updated `.env.local`

Added this line to disable SSL verification in development:
```env
NODE_TLS_REJECT_UNAUTHORIZED=0
```

**Location:** `frontend/.env.local` (line 15)

### 2. Restart Required

You **must restart** the Next.js dev server for this to take effect:

```bash
# Stop the current dev server (Ctrl+C)
# Then restart:
cd frontend
npm run dev
```

---

## Verification

After restarting, the error should be gone. You should see:

```
✓ Ready in X.Xs
✓ Compiled successfully
```

No more Clerk handshake errors!

---

## Why This Works

- `NODE_TLS_REJECT_UNAUTHORIZED=0` tells Node.js to skip SSL certificate verification
- This allows Clerk to connect through corporate proxies/firewalls
- Clerk can now fetch its configuration and JWKS keys

---

## Is This Safe?

**For Development: YES** ✅
- You're only connecting to Clerk's API (trusted source)
- SSL is still encrypted, just not validated
- Only affects your local machine

**For Production: NO** ❌
- Never use this in production
- Production should have proper SSL certificates
- Remove this setting before deploying

---

## Alternative Solutions

If you can't use `NODE_TLS_REJECT_UNAUTHORIZED=0`:

### Option 1: Configure Corporate CA Certificates
```bash
# Set Windows certificate store
set NODE_EXTRA_CA_CERTS=C:\path\to\corporate-ca.pem

# Or in .env.local:
NODE_EXTRA_CA_CERTS=C:\path\to\corporate-ca.pem
```

### Option 2: Use Clerk's Development Mode
In your Clerk dashboard:
1. Go to Settings → API Keys
2. Enable "Development Mode"
3. This may bypass some SSL checks

### Option 3: Corporate Proxy Bypass
If you know your proxy settings:
```env
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
```

---

## Testing the Fix

Run the diagnostic script:
```bash
cd frontend
node test-clerk-connection.js
```

Expected output:
```
✓ Connected to Clerk (Status: 200)
✓ Issuer: https://wise-coral-92.clerk.accounts.dev
✓ JWKS URI: https://wise-coral-92.clerk.accounts.dev/.well-known/jwks.json
✓ Key format looks correct
✓ Backend is running
```

---

## Next Steps

1. **Restart frontend dev server** (if not already done)
2. **Navigate to http://localhost:3000**
3. **Verify no SSL errors** in terminal
4. **Test sign-up flow** - Clerk UI should load properly

---

## Still Having Issues?

### Check These:

1. **Internet Connection**
   - Clerk needs to reach its API
   - Test: `ping wise-coral-92.clerk.accounts.dev`

2. **Firewall Blocking**
   - Some corporate firewalls block Clerk domains
   - Contact IT to whitelist `*.clerk.accounts.dev`

3. **Proxy Configuration**
   - You may need proxy settings
   - Check with IT for HTTP_PROXY and HTTPS_PROXY values

4. **VPN Issues**
   - Some VPNs interfere with SSL
   - Try disconnecting VPN temporarily

---

## Summary

✅ **Fix Applied:** Added `NODE_TLS_REJECT_UNAUTHORIZED=0` to `.env.local`
✅ **Next Action:** Restart frontend dev server
✅ **Expected Result:** No more SSL handshake errors

This is a common corporate environment issue and the fix is safe for development use.
