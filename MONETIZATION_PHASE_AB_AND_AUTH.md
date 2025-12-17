# Monetization & Auth Plan – Phase A/B Focus

_Draft / internal – derived from `MONETIZATION_SKETCH.md` and current codebase._

This note captures a concrete, near‑term plan that only implements:

- **Phase A – Internal quotas (no billing yet).**
- **Phase B – Flat subscriptions via Stripe (no metered overage, no pooled teams yet).**

Downstream ideas (true metered billing, pooled team quotas, enterprise SSO/SLAs) are intentionally out of scope for now.

---

## Phase A – Internal Free‑Tier Quotas

Goal: protect infra costs and create a clear “Free plan” experience, using existing `User`, `UserQuota`, and `UsageEvent` models, without integrating Stripe yet.

### 1. Free‑tier limits (per billing period)

These map onto `UserQuota` and `settings`:

- **Ingestion**
  - `minutes_limit`: **120 minutes** of new video ingestion per period.
  - `videos_limit`: **10 videos** total ingested per period.
- **RAG chat**
  - `messages_limit`: **500 assistant responses** per period.
- **Storage**
  - `storage_mb_limit`: keep existing default (~**1000 MB / 1 GB**).

Implementation hook: `User.subscription_tier="free"`, `subscription_status="active"`, and `UserQuota` seeded with the above limits for the default user or on signup.

### 2. Measuring and enforcing ingest limits

**Measurement**

- `UsageTracker.track_video_ingestion` already:
  - Creates a `UsageEvent(event_type="video_ingested", quota_category="videos")`.
  - Increments `UserQuota.videos_used`, `minutes_used`, and `storage_mb_used`.
- `UsageTracker._get_or_create_quota` resets quotas when `quota_period_end < now` and seeds tier‑specific limits via `_create_initial_quota`.

**Enforcement**

- In `POST /videos/ingest` (`backend/app/api/routes/videos.py`):
  - Re‑enable the previously commented quota checks (see `videos.py.bak`):
    - Before creating `Video`/`Job`, compute `duration_minutes` from `video_info["duration_seconds"]`.
    - Call:
      - `usage_tracker.check_quota(current_user.id, "videos", 1)`
      - `usage_tracker.check_quota(current_user.id, "minutes", duration_minutes)`
  - On `QuotaExceededError`, return an HTTP error (e.g. `429` or `402`‑style) with upgrade‑friendly message text:
    - Example: `"Monthly ingest limit reached on the Free plan. Upgrade to unlock more minutes and videos."`

This makes ingest limits effective immediately for Free accounts without touching the Celery pipeline logic, which already records usage and storage.

### 3. Measuring and enforcing RAG chat limits

**What is counted**

- **Quota unit**: **one assistant answer** in RAG chat = 1 “message”.
- **Analytics only**: keep logging token counts (`prompt_tokens`, `completion_tokens`) in `UsageEvent.event_metadata` so future paid/overage plans can pivot to token‑based billing without changing the current UX.

**Measurement**

- Extend `UsageTracker.track_chat_message` to always receive and store:
  - `tokens_in` and `tokens_out` (from `llm_response.usage`, when available).
  - `chunks_retrieved` for retrieval analytics.
- Each call:
  - Creates a `UsageEvent(event_type="chat_message_sent", quota_category="messages", quota_amount_used=1)`.
  - Increments `UserQuota.messages_used` by 1.

**Enforcement**

- In `POST /conversations/{conversation_id}/messages` (`backend/app/api/routes/conversations.py`):
  - Before any retrieval/LLM call:
    - Instantiate `UsageTracker(db)`.
    - Call `usage_tracker.check_quota(current_user.id, "messages", 1)`.
    - If it raises `QuotaExceededError`, return a quota error (e.g. `429`) with a clear, upgrade‑oriented message:
      - Example: `"RAG chat limit reached for this period on the Free plan. Upgrade to continue chatting."`
  - After generating and saving the assistant `Message`:
    - Call `usage_tracker.track_chat_message(...)` with:
      - `user_id`, `conversation_id`, `message_id`,
      - `tokens_in`, `tokens_out` taken from the LLM provider response (fall back to 0 when unknown),
      - `chunks_retrieved` equal to the number of chunks used for context.

### 4. Surfacing usage to the user

- Reuse `/api/v1/usage/summary` (`backend/app/api/routes/usage.py`) to expose:
  - `videos`, `minutes`, `messages`, and `storage_mb` as `QuotaStat`s derived from `UserQuota`.
  - Counts of videos/transcripts/chunks and approximate storage breakdown.
- Frontend:
  - Add a simple “Usage” section/card (or badge) in the UI showing:
    - `minutes used / limit`, `videos used / limit`, `RAG messages used / limit`.
  - When quotas are near exhausted, show a subtle warning banner and a CTA to upgrade (even before Stripe exists, the CTA can be a placeholder).

---

## Phase B – Flat Stripe Subscriptions (No Metered Overage Yet)

Goal: keep billing simple—flat monthly Pro plan (and optionally Team later), using the same quota enforcement logic as Phase A, but with higher limits per tier and Stripe as the source of truth for plan and billing status.

### 1. User & subscription fields

Extend/confirm `users` table (`backend/app/models/user.py`) includes:

- `subscription_tier: str` – `"free" | "pro" | "team" | "enterprise"`, defaults to `"free"`.
- `subscription_status: str` – `"active" | "past_due" | "canceled" | "trialing"`, defaults to `"active"`.
- `stripe_customer_id: str | None` – Stripe customer reference (already present).
- `stripe_subscription_id: str | None` – primary subscription identifier for the current plan.

In code, keep tier → limits mapping centralized inside `UsageTracker._create_initial_quota` so changing plan limits does not require schema changes.

### 2. Tier presets (no overage)

Initial proposal (flat limits, no per‑unit overages inside the app; Stripe just charges a flat monthly fee):

- **Free**
  - Ingest: **120 minutes**, **10 videos**.
  - Chat: **500 messages**.
  - Storage: **1 GB**.
- **Pro** (single‑user)
  - Ingest: **600 minutes** (10 hours), **100 videos**.
  - Chat: **3,000 messages**.
  - Storage: **10 GB**.
- **Team / Enterprise**
  - Keep sketched but unimplemented until later; for Phase B it is enough to support **Free → Pro** upgrades cleanly.

These values live in:

- `settings.*` for Free (already present, update as needed).
- The `tier_limits` mapping in `UsageTracker._create_initial_quota` for Pro/Team/Enterprise.

### 3. Stripe lifecycle (flat plans)

**Upgrade (Free → Pro)**

- Backend endpoint (e.g. `POST /billing/create-checkout-session`) that:
  - Ensures the user has a `stripe_customer` (create if needed).
  - Creates a Stripe Checkout session for the `pro` price.
  - Returns the session URL to the frontend.
- Frontend redirects user to Stripe Checkout.
- On Stripe `checkout.session.completed` webhook:
  - Fetch the subscription object.
  - Set `user.subscription_tier = "pro"`.
  - Set `subscription_status` from Stripe’s status.
  - Set `stripe_subscription_id`.
  - Reset or re‑seed `UserQuota` for the new tier and period:
    - `quota_period_start`/`quota_period_end` aligned with Stripe’s billing period.
    - Limits populated from Pro presets.

**Renewals, downgrades, cancellations**

- Handle `customer.subscription.updated` / `customer.subscription.deleted`:
  - Keep `subscription_status` in sync with Stripe.
  - On downgrade (e.g. Pro → Free at period end):
    - Mark in app that lower limits apply from the next billing period.
    - On next quota reset, seed Free‑tier limits again.
  - On `canceled`/`past_due`:
    - Option A: immediately enforce Free limits but keep existing content accessible.
    - Option B: allow limited grace period, then fall back to Free limits.

**Enforcement**

- Core enforcement remains exactly as in Phase A:
  - `UsageTracker.check_quota` gates ingest and chat.
  - `UsageTracker.track_*` methods record usage.
- The only difference across tiers is the limits used when (re)seeding `UserQuota`.

---

## Auth & Login – Supporting Monetization

Goal: provide a minimal but robust identity layer so quotas and subscriptions are per‑user, while keeping implementation small enough not to block monetization work.

### 1. Baseline: email + password

**Backend**

- Add `POST /auth/register`:
  - Accepts `email`, `password`, optional `full_name`.
  - Creates `User` with:
    - `hashed_password` set via a secure password hasher.
    - `subscription_tier="free"`, `subscription_status="active"`.
  - Creates initial `UserQuota` using Free‑tier limits.
  - Returns a JWT or session cookie.
- Add `POST /auth/login`:
  - Validates `email` + `password`.
  - Checks `subscription_status`:
    - If not `"active"`, still allow login but show in‑app messaging and enforce appropriate limits (e.g. Free after cancellation).
  - Returns JWT/session.
- Replace placeholder `get_current_user` helpers with JWT/session‑based lookup once auth is wired.

**Frontend**

- Single login page with:
  - Email/password login form.
  - Link or toggle to “Create free account.”
  - On successful auth, redirect to the main dashboard where usage/plan info is visible.

### 2. Optional: OAuth (Google first, others later)

To reduce friction without over‑complicating the system, add **one primary OAuth provider** first (Google), with others (GitHub, etc.) as future options.

**Data model**

- Extend `User` with:
  - `auth_provider: str | None` – e.g., `"password" | "google" | "github"`.
  - `auth_provider_id: str | None` – provider’s subject/ID.
- For OAuth users:
  - `hashed_password` can remain `NULL`.
  - `subscription_tier` / `UserQuota` logic is identical to password users.

**Flow**

- `GET /auth/oauth/{provider}/start`:
  - Redirects to the provider’s authorization URL.
- `GET /auth/oauth/{provider}/callback`:
  - Exchanges the code for an access token.
  - Retrieves the user’s email + subject ID.
  - If a user with that `(auth_provider, auth_provider_id)` exists:
    - Log them in and issue JWT/session.
  - Else:
    - Create a new `User` with:
      - `email`, `auth_provider`, `auth_provider_id`.
      - `subscription_tier="free"`, `subscription_status="active"`.
    - Create initial `UserQuota` for Free tier.
    - Issue JWT/session.

**Frontend**

- On the login/registration page:
  - Add “Continue with Google” button (and later, GitHub, etc.).
  - These buttons hit the `/auth/oauth/{provider}/start` endpoint to initiate the OAuth flow.

---

## What’s Explicitly Deferred

To keep the initial scope small and shippable, the following are **deliberately out of scope** for the Phase A/B implementation:

- True **metered overage** (per‑minute or per‑token billing in Stripe).
- **Pooled team quotas** (org‑level `TeamQuota` objects and shared limits).
- **Enterprise features**:
  - Tenant‑level SSO (SAML/OIDC).
  - Advanced retention controls and DPAs.
  - Dedicated clusters/VPCs.

The design above keeps enough data (especially `UsageEvent` with token metadata) that these can be added later without breaking existing behavior or pricing experiments.

