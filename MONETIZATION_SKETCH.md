# Monetization Sketch – RAG Transcript System

_Last updated: 2025-12-11 (draft / internal)_

This document outlines a practical monetization model for the RAG Transcript System, aligned with the existing schema (`users`, `usage_events`, `user_quotas`, `jobs`) and the planned Stripe integration mentioned in the README.

---

## 1. Positioning & Target Users

- **Primary value**: “Chat with any YouTube / internal video library with precise citations back to timestamps,” plus semantic enrichment (summaries, keywords, highlights).
- **Primary buyers**:
  - Content creators / YouTube channels repurposing and mining their own catalog.
  - Knowledge workers and educators relying on YouTube, MOOCs, and webinars.
  - Companies with large internal video libraries (trainings, all-hands, sales calls).
- **Billing primitives**:
  - Ingested **video minutes** (Whisper + chunking + embeddings).
  - **RAG chat usage** (tokens/messages against stored content).
  - Optional: storage footprint (number of videos / total minutes retained).

---

## 2. Pricing Tiers (Proposal)

All tiers share the same core UX and APIs; higher tiers get more quota, priority processing, and team features.

### 2.1 Tier Summary

- **Free**
  - Price: **$0 / user / month**
  - Ingestion: up to **120 minutes** of new video per month.
  - Storage: up to **10 videos** (or 300 minutes) retained.
  - Chat: up to **500 messages** per month (RAG-enabled).
  - Concurrency: **1** active ingest job at a time.
  - Features: basic YouTube ingestion, single workspace, manual source selection, basic exports (copy/paste, markdown).
  - Purpose: product-led growth, testing the workflow.

- **Pro**
  - Price: **$20 / user / month**
  - Ingestion: up to **600 minutes** (10 hours) per month.
  - Storage: up to **100 videos** (or ~2,000 minutes) retained.
  - Chat: up to **3,000 messages** per month.
  - Concurrency: up to **4** active ingest jobs.
  - Features: collections, richer exports (notes, outlines), reranking, multiple LLM providers, priority queueing for jobs.
  - Overage: **$2 per +60 minutes** of ingestion, **$2 per +1,000 messages** (billed via metered usage).

- **Team**
  - Price: **$80 / month** for 5 seats (then **$10 / extra seat**).
  - Ingestion: **3,000 minutes** (50 hours) per month (pooled).
  - Storage: **500 videos** retained.
  - Chat: **10,000 messages** per month (pooled).
  - Concurrency: up to **10** active ingest jobs.
  - Features: shared workspaces, team collections, role-based permissions, basic audit log (who ingested / chatted with what), priority support.
  - Overage: same as Pro, but billed at team level (one Stripe subscription).

- **Enterprise**
  - Price: custom (high-touch sales).
  - Ingestion / storage / chat: negotiated limits and SLAs.
  - Deployment: dedicated cluster / VPC, custom SSO, DPA, priority SLAs.
  - Features: advanced audit & compliance, custom retention, optional on-prem or private cloud.

### 2.2 Metrics (per tier)

Each tier can be implemented as a row in a `subscription_tier` enum or config, mapping to:

- `max_ingested_minutes_per_month`
- `max_stored_minutes`
- `max_stored_videos`
- `max_chat_messages_per_month`
- `max_concurrent_jobs`
- `priority_level` (for job queue ordering)

These map naturally to `user_quotas` and can be adjusted without schema changes.

---

## 3. Usage Measurement Model

The existing tables suggest a usage-based approach:

- **`usage_events`**: append-only log of billable and quota-relevant actions.
  - Example `event_type` values:
    - `video_ingested`
    - `video_reingested`
    - `message_answered`
    - `export_generated`
  - Example `metadata` per event (JSON):
    - For ingest: `{ "video_id": ..., "duration_minutes": 23.4 }`
    - For chat: `{ "conversation_id": ..., "prompt_tokens": 512, "completion_tokens": 384, "provider": "openai" }`

- **`user_quotas`**: stores current aggregated usage and limits per billing period.
  - Example fields:
    - `ingested_minutes_used`
    - `chat_messages_used`
    - `stored_minutes`
    - `stored_videos`
    - `period_start`, `period_end`
  - Derived from `usage_events` via:
    - Real-time updates (increment counters when an event is recorded), and/or
    - Periodic reconciliation jobs (e.g., nightly aggregation over the last N days for safety).

---

## 4. Quota Enforcement Model

Enforce quotas at the service layer so both HTTP routes and Celery tasks respect the same rules.

### 4.1 Ingestion (Videos)

- Before accepting a new ingest job:
  - Compute `projected_ingested_minutes = ingested_minutes_used + video_duration_estimate`.
  - If `projected_ingested_minutes > max_ingested_minutes_per_month`:
    - **Free**: reject with a clear HTTP 402-style error (“Monthly ingest limit reached; upgrade to Pro / Team”).
    - **Paid tiers**: accept if within an overage safety cap, record extra usage for metered billing, or offer to “pause until next billing period.”
- On completion of ingestion:
  - Emit `usage_events` with actual `duration_minutes`.
  - Update `stored_minutes` and `stored_videos` (for storage-based limits).

### 4.2 Chat (RAG)

- On each assistant response:
  - Measure `prompt_tokens` and `completion_tokens` (provider-specific metadata already captured in messages/LLM layer).
  - Increment `chat_messages_used` and optionally a `chat_tokens_used` counter.
- If `chat_messages_used` (or tokens) exceeds tier limit:
  - **Free**: return a “quota exceeded” message and suggest upgrade.
  - **Paid**: allow a small buffer and mark overage for billing, or gracefully degrade:
    - Use a cheaper LLM provider/model.
    - Reduce `RETRIEVAL_TOP_K` or disable reranking if desired.

### 4.3 Storage Limits

- On ingestion completion or when changing video retention:
  - Enforce `max_stored_minutes` and `max_stored_videos` by:
    - Blocking new ingest, or
    - Asking user to archive/delete older content, or
    - For paid tiers, offering auto-upgrade or storage add-ons.

---

## 5. Stripe Integration (High-Level)

The README already notes that `users` includes subscription tiers and Stripe IDs. This section sketches the full flow.

### 5.1 User & Subscription Fields

Extend or confirm `users` table includes:

- `stripe_customer_id`
- `stripe_subscription_id`
- `subscription_tier` (enum: `free`, `pro`, `team`, `enterprise`)
- `subscription_status` (e.g., `active`, `past_due`, `canceled`, `trialing`)

Optionally, keep a separate `subscription_plans` config table or static mapping in code for tier limits.

### 5.2 Checkout & Upgrades

- When a user upgrades from Free:
  - Create or reuse `stripe_customer` using their email.
  - Redirect them to a Stripe Checkout session for the desired plan (Pro / Team).
  - On `checkout.session.completed` webhook:
    - Set `subscription_tier` and `subscription_status`.
    - Initialize `user_quotas` for the new tier (reset usage counters for the new period).

- When a subscription is updated or canceled:
  - Handle `customer.subscription.updated` & `customer.subscription.deleted` webhooks.
  - Update `subscription_tier`, `subscription_status`, and adjust quotas.
  - For downgrades, mark which limits will be enforced next period (graceful transition).

### 5.3 Metered Usage Reporting

If using Stripe metered billing:

- Maintain one or more **metered subscription items**:
  - `video_ingest_minutes`
  - `rag_chat_messages` (or `rag_tokens`)
- Periodically (e.g., hourly or daily) aggregate `usage_events` for the last N hours:
  - Sum `duration_minutes` for ingest events.
  - Count chat messages or tokens.
- Call Stripe’s usage record API with:
  - `timestamp`, `quantity`, and `subscription_item` reference.
- Ensure idempotency with a simple “last reported cursor” based on `usage_events` IDs or timestamps.

---

## 6. Implementation Roadmap (Phased)

**Phase A – Internal Limits (no billing yet)**
- Implement `user_quotas` reads/writes and enforcement in:
  - Video ingest path (before creating jobs).
  - Conversation message path (before sending to LLM).
- Record all billable actions in `usage_events`.
- Surface quotas & usage in the frontend (per user / workspace).

**Phase B – Stripe Subscriptions**
- Add Stripe integration (customers, checkout, webhooks).
- Map tiers (`free`, `pro`, `team`) to quota presets.
- On webhook events, update `subscription_tier`, `subscription_status`, and reset `user_quotas` for each billing cycle.

**Phase C – Metered Overage & Teams**
- Introduce metered usage items for ingest minutes and chat usage.
- Implement daily aggregation job that reports usage to Stripe.
- Enable team plans with pooled quotas, shared workspaces, and seat-based pricing.

**Phase D – Enterprise**
- Add support for dedicated deployments, advanced audit logging, and custom retention policies.
- Integrate SSO (SAML/OIDC) and SLAs at the contract level (off-app).

---

This sketch is intentionally high-level but opinionated enough to guide schema changes, service-level checks, and Stripe integration work without constraining pricing experiments later.

