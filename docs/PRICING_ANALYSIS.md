# RAG Transcript Pricing Analysis

**Last Updated:** January 2025
**Status:** Active pricing strategy (Updated January 28, 2025)
**Related:** `backend/app/core/pricing.py`, `docs/MODEL_RESEARCH.md`

## Executive Summary

**Goal:** Validate Pro tier pricing against actual costs to ensure profitability while maximizing free tier conversion.

**Key Finding:** Updated pricing improves margins on heavy users while increasing free tier message limit for better conversion.

**Changes Made (January 2025):**
- Free tier: 50 → **200 messages/month** (4x increase for better trial experience)
- Pro tier: $20/mo → **$23.99/mo** (20% price increase, heavy users now near break-even)
- Enterprise tier: $100/mo → **$79.99/mo** (competitive pricing with dedicated onboarding)

---

## 1. Current Pricing Structure

| Tier | Monthly | Yearly | Videos | Messages | Storage | Video Minutes |
|------|---------|--------|--------|----------|---------|---------------|
| Free | $0 | - | 10 | 200/mo | 1 GB | 1000/mo |
| Pro | $23.99/mo | $229.99/yr | Unlimited | Unlimited | 50 GB | Unlimited |
| Enterprise | $79.99/mo | $799.99/yr | Unlimited | Unlimited | Unlimited | Unlimited |

**Yearly Discounts:**
- Pro: $229.99/year = $19.17/month effective (20% off)
- Enterprise: $799.99/year = $66.67/month effective (17% off)

**Enterprise includes dedicated onboarding manager.**

---

## 2. Cost Breakdown

### 2.1 Railway Infrastructure Costs

**Source:** [Railway Pricing Docs](https://docs.railway.com/reference/pricing/plans)

| Resource | Cost |
|----------|------|
| CPU | $0.000463/vCPU/min (~$20/vCPU/month) |
| Memory | $0.000231/GB/min (~$10/GB/month) |
| Storage | $0.15/GB/month |
| Egress | $0.05/GB |

**Service Resource Allocation (7 containers):**

| Service | CPU | RAM | Monthly Cost |
|---------|-----|-----|--------------|
| `app` (FastAPI) | 0.5 vCPU | 1 GB | $20 |
| `worker` (Celery + Whisper) | 0.5 vCPU | 2 GB | $30 |
| `beat` (Scheduler) | 0.1 vCPU | 256 MB | $4.50 |
| `postgres` | 0.25 vCPU | 1 GB | $15 |
| `redis` | 0.1 vCPU | 256 MB | $4.50 |
| `qdrant` | 0.25 vCPU | 1 GB | $15 |
| `frontend` | 0.25 vCPU | 512 MB | $10 |
| **Total** | ~2 vCPU | ~6 GB | **~$100/month** |

**Storage Costs:**
- Pro user (50 GB limit): $7.50/user/month maximum
- Free user (1 GB limit): $0.15/user/month maximum
- Most users use far less than limits

### 2.2 DeepSeek API Costs

**Source:** [DeepSeek Pricing](https://api-docs.deepseek.com/quick_start/pricing)

| Type | Cost per 1M tokens |
|------|-------------------|
| Input (cache miss) | $0.28 |
| Input (cache hit) | $0.028 (90% cheaper!) |
| Output | $0.42 |

**Per-Message Cost Estimate:**

A typical RAG query involves:
- System prompt + context: ~3,000 tokens input
- User query: ~100 tokens input
- Retrieved chunks: ~2,000 tokens input
- Response: ~500 tokens output
- **Total:** ~5,100 input + 500 output tokens

| Scenario | Input Cost | Output Cost | Total |
|----------|-----------|-------------|-------|
| No cache | $0.00143 | $0.00021 | **$0.0016** |
| 50% cache hit | $0.00086 | $0.00021 | **$0.0010** |
| 80% cache hit | $0.00043 | $0.00021 | **$0.0006** |

**Note:** DeepSeek automatically caches prompt prefixes, so multi-turn conversations benefit significantly from caching.

### 2.3 Other Costs

| Cost | Amount | Notes |
|------|--------|-------|
| Stripe fees | 2.9% + $0.30/txn | $23.99 Pro = $1.00 fee (4.2% effective) |
| Domain/SSL | ~$15/year | Negligible |
| Monitoring | $0-50/month | Datadog, Sentry, etc. |
| Email (transactional) | ~$0.001/email | SendGrid, Resend |
| Embedding generation | Included | Local sentence-transformers |
| Backup/DR | Variable | Database backups |

**Net Revenue After Stripe:**
- Pro monthly ($23.99): $22.99 net
- Pro yearly ($229.99): $223.32 net
- Enterprise monthly ($79.99): $77.37 net
- Enterprise yearly ($799.99): $776.39 net

---

## 3. Per-User Cost Analysis

### 3.1 Free Tier User (Monthly)

| Component | Usage | Cost |
|-----------|-------|------|
| Storage | 1 GB max | $0.15 |
| Messages | 200 x $0.0016 | $0.32 |
| Video processing | 10 videos x $0.05 | $0.50 |
| Infrastructure share | Minimal | ~$0.10 |
| **Total** | | **~$1.07/user/month** |

**Analysis:** Free tier is a deliberate loss-leader. At $1.07/user (up from $0.83 with 50 messages),
the 4x message increase provides significantly better trial experience for only $0.24 more per user.

**Rationale for 200 messages:**
- 100 messages was 15x lower than competitors (NotebookLM: ~1,500/mo)
- With 10 videos and 100 messages = only 10 messages per video (barely one session)
- 200 messages allows ~20 messages per video (full exploration session)
- Cost increase is marginal ($0.24/user) but conversion impact is substantial

### 3.2 Pro Tier User Scenarios

#### Light User (Typical)
| Component | Usage | Cost |
|-----------|-------|------|
| Storage | 5 GB | $0.75 |
| Messages | 100/month | $0.16 |
| Videos | 20 videos | $1.00 |
| Infrastructure | | $0.50 |
| **Total** | | **$2.41/month** |
| **Margin on $23.99** | | **$20.58 (90%)** |

#### Medium User
| Component | Usage | Cost |
|-----------|-------|------|
| Storage | 20 GB | $3.00 |
| Messages | 500/month | $0.80 |
| Videos | 50 videos | $2.50 |
| Infrastructure | | $1.00 |
| **Total** | | **$7.30/month** |
| **Margin on $23.99** | | **$15.69 (70%)** |

#### Heavy User (Power User)
| Component | Usage | Cost |
|-----------|-------|------|
| Storage | 50 GB (max) | $7.50 |
| Messages | 2,000/month | $3.20 |
| Videos | 200 videos | $10.00 |
| Infrastructure | | $3.00 |
| **Total** | | **$23.70/month** |
| **Margin on $23.99** | | **-$0.71 (~break-even)** |

**Key improvement:** Heavy users are now nearly break-even (-$0.71) instead of a $4.88 loss.

#### Extreme User (Abuse Scenario)
| Component | Usage | Cost |
|-----------|-------|------|
| Storage | 50 GB | $7.50 |
| Messages | 10,000/month | $16.00 |
| Videos | 500 videos | $25.00 |
| Infrastructure | | $5.00 |
| **Total** | | **$53.50/month** |
| **Margin on $23.99** | | **-$30.51 (SIGNIFICANT LOSS)** |

**Mitigation:** Fair use policy and monitoring for users >2000 messages/month.

---

## 4. Break-Even Analysis

**Fixed Costs:** ~$100/month base infrastructure

### Scenario A: 100 Users (90 Free, 10 Pro)

| Item | Amount |
|------|--------|
| Pro revenue | 10 x $22.99 = $229.90 |
| Pro costs (medium) | 10 x $7.30 = $73.00 |
| Free user costs | 90 x $1.07 = $96.30 |
| Infrastructure | $100.00 |
| **Net** | **-$39.40/month (LOSS)** |

### Scenario B: 100 Users (85 Free, 15 Pro)

| Item | Amount |
|------|--------|
| Pro revenue | 15 x $22.99 = $344.85 |
| Pro costs (medium) | 15 x $7.30 = $109.50 |
| Free user costs | 85 x $1.07 = $90.95 |
| Infrastructure | $100.00 |
| **Net** | **+$44.40/month (PROFIT)** |

### Break-Even Requirements

- **Minimum conversion rate:** ~12% at medium usage (improved from ~15%)
- **With light users:** ~10% conversion rate
- **With heavy users:** ~15% conversion rate needed (improved from ~20%)

**Key improvement:** Higher Pro price improves profitability at same conversion rates.

---

## 5. Competitor Pricing Comparison

### General AI Chat Platforms

| Platform | Free Limit | Time Period | Effective Monthly |
|----------|-----------|-------------|-------------------|
| **ChatGPT** | 10 messages | per 5 hours | ~1,440/month |
| **Claude.ai** | 20-30 messages | per day | ~600-900/month |
| **Gemini** | 50-100 requests | per day | ~1,500-3,000/month |
| **Microsoft Copilot** | Unlimited | - | Unlimited |
| **Perplexity** | Unlimited basic | - | Unlimited (5 Pro/day) |

### Specialized AI Tools (More Comparable)

| Platform | Free Limit | Notes |
|----------|-----------|-------|
| **NotebookLM** | 50 queries/day | ~1,500/month, document RAG |
| **Fireflies.ai** | 20 AI credits/month | Meeting transcription + AI |
| **Otter.ai** | 300 min transcription | No AI query limit |

### Pricing Comparison

| Service | Free Tier | Paid Entry | Focus |
|---------|-----------|------------|-------|
| **RAG Transcript** | 10 videos, 200 msg, 1GB | $23.99/mo unlimited | Video RAG chat |
| **Otter.ai** | 300 min/mo | $8.33/mo (1200 min) | Meeting transcription |
| **Fireflies.ai** | 800 min storage | $10/mo | Meeting notes + AI |
| **Descript** | 1 hr/mo | $12-16/mo | Video editing + transcript |
| **NotebookLM** | Free | Free (Google) | Document/video analysis |
| **Glasp** | Free | Free | YouTube summaries |

**Key Observations:**
1. Our 200 messages/month is now competitive with Claude.ai free (was 15x lower at 50 messages)
2. Our $23.99/mo is **higher** than meeting transcription tools ($8-16)
3. But we offer **more value**: RAG chat, unlimited messages, memory, citations
4. Free competitors exist (NotebookLM, Glasp) but lack depth
5. "Unlimited messages" on paid tier is aggressive vs competitors with credit limits

**Sources:** [ChatGPT Free Tier FAQ](https://help.openai.com/en/articles/9275245-chatgpt-free-tier-faq), [About Free Claude Usage](https://support.claude.com/en/articles/8602283-about-free-claude-usage), [NotebookLM Help Center](https://support.google.com/notebooklm/answer/16269187?hl=en), [Otter.ai Pricing](https://otter.ai/pricing), [Fireflies Pricing](https://fireflies.ai/pricing), [Descript Pricing](https://www.descript.com/pricing)

---

## 6. Risk Assessment

### HIGH RISK: Unlimited Messages

- Heavy users can send 10,000+ messages = $16+ in LLM costs alone
- Competitors cap AI credits (Fireflies: 50 credits, Descript: 800/mo)
- **Mitigation:** Monitor users >2000 messages/month, fair use policy

### MEDIUM RISK: 50GB Storage

- At $0.15/GB = $7.50 max storage cost per user
- Most users won't hit 50GB (audio files are ~1MB/minute)
- 50GB = ~850 hours of video content
- **Mitigation:** Most users naturally stay well under limit

### LOW RISK: Unlimited Videos/Minutes

- Processing cost ~$0.05/video (one-time)
- Not recurring monthly cost
- Heavy processing users are rare
- **Mitigation:** Processing is bounded by practical time constraints

---

## 7. Recommendations

### Implemented Strategy: Balanced Pricing Update

**Decision:** Increase Pro price and free tier messages for optimal conversion/margin balance.

**Changes Made:**
1. **Free tier: 200 messages/month** (up from 50)
   - Better trial experience
   - Competitive with Claude.ai free
   - Only $0.24/user additional cost
2. **Pro: $23.99/mo** (up from $20.00)
   - Charm pricing (.99 ending)
   - 20% revenue increase
   - Heavy users now nearly break-even
3. **Enterprise: $79.99/mo** (competitive pricing with onboarding)
4. **Yearly: 20% discount** on Pro ($229.99/yr)

### Rationale

- **Free tier increase:** 100 messages was 15x lower than NotebookLM; users couldn't experience full value before hitting limit
- **Pro price increase:** Heavy users were costing $23.70 on a $20 subscription; now nearly break-even
- **Charm pricing:** $23.99 feels like "low twenties" vs $24.00 feeling like "mid twenties"
- **Yearly discount:** 20% off encourages annual commitment

### Profitability Summary

| User Type | Monthly Cost | Margin on $23.99 |
|-----------|-------------|------------------|
| Light (100 msg) | $2.41 | **90%** ($20.58) |
| Medium (500 msg) | $7.30 | **70%** ($15.69) |
| Heavy (2000 msg) | $23.70 | **~0%** (-$0.71) |

### Monitoring Implementation

Heavy user thresholds are configured in `backend/app/core/pricing.py`:

```python
HEAVY_USER_THRESHOLDS = {
    "pro": {
        "messages_per_month": 2000,   # Flag for review
        "videos_per_month": 200,
        "storage_used_gb": 40,
    }
}
```

Use `check_heavy_user()` function to identify users exceeding thresholds.

---

## 8. Implementation Checklist

- [x] Cost configuration added to `pricing.py`
- [x] Heavy user thresholds defined
- [x] Cost estimation functions implemented
- [x] Free tier message limit updated to 200
- [x] Pro tier price updated to $23.99/mo, $229.99/yr
- [x] Enterprise tier price updated to $79.99/mo, $799.99/yr
- [x] TIER_COST_TARGETS updated for new pricing
- [ ] Create new Stripe price IDs for updated prices
- [ ] Admin dashboard: Add heavy user monitoring view
- [ ] Add fair use policy to Terms of Service
- [ ] Stripe webhook: Track subscription revenue
- [ ] Monthly cost report generation

---

## 9. References

- [Railway Pricing Plans](https://docs.railway.com/reference/pricing/plans)
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Otter.ai Pricing](https://otter.ai/pricing)
- [Fireflies.ai Pricing](https://fireflies.ai/pricing)
- [Descript Pricing](https://www.descript.com/pricing)
- Internal: `backend/app/core/pricing.py` - Source of truth for tier limits
- Internal: `docs/MODEL_RESEARCH.md` - LLM model selection rationale
