# Phase 2: SaaS Features - Implementation Roadmap

## Status: Foundation Complete ✅

**Date Started**: 2026-01-18
**Current Progress**: 20% Complete (Infrastructure ready)

---

## Completed Work

### Phase 2.1: Foundation (COMPLETE ✅)

#### Database Models & Schemas
- ✅ Created `Subscription` model (`backend/app/models/subscription.py`)
  - Tracks subscription lifecycle
  - Stripe integration fields (customer_id, subscription_id, price_id)
  - Billing period tracking
  - Status management (active, canceled, past_due, trialing)

- ✅ Created comprehensive Pydantic schemas (`backend/app/schemas/subscription.py`)
  - `SubscriptionCreate`, `SubscriptionUpdate`, `SubscriptionDetail`
  - `CheckoutSessionRequest`, `CheckoutSessionResponse`
  - `CustomerPortalRequest`, `CustomerPortalResponse`
  - `QuotaUsage` - tracks usage vs limits
  - `PricingTier` - tier configuration

- ✅ Added dependencies:
  - `stripe==7.8.0` - Payment processing
  - `resend==0.8.0` - Email notifications

- ✅ Created database migration:
  - `007_add_subscriptions.py` - Creates subscriptions table with indexes

#### User Model Updates (Already Present)
- ✅ User model already has subscription fields:
  - `subscription_tier` (free/pro/enterprise)
  - `subscription_status` (active/canceled/suspended)
  - `stripe_customer_id`

---

## Remaining Work

### Phase 2.2: Subscription Service & Quota Enforcement

**Estimated Time**: 6-8 hours

#### 2.2.1: Pricing Configuration
Create `backend/app/core/pricing.py`:
```python
PRICING_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
        "features": [
            "2 videos",
            "50 messages/month",
            "1GB storage",
            "60 minutes video/month",
        ],
        "video_limit": 2,
        "message_limit": 50,
        "storage_limit_mb": 1000,
        "minutes_limit": 60,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 2000,  # $20/month in cents
        "price_yearly": 20000,  # $200/year in cents
        "stripe_price_id_monthly": "price_xxx",  # Set in Stripe dashboard
        "stripe_price_id_yearly": "price_yyy",
        "features": [
            "Unlimited videos",
            "Unlimited messages",
            "50GB storage",
            "1000 minutes video/month",
            "Priority support",
        ],
        "video_limit": -1,  # -1 = unlimited
        "message_limit": -1,
        "storage_limit_mb": 50000,
        "minutes_limit": 1000,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 10000,  # $100/month
        "price_yearly": 100000,  # $1000/year
        "stripe_price_id_monthly": "price_zzz",
        "stripe_price_id_yearly": "price_www",
        "features": [
            "Everything in Pro",
            "Custom video limits",
            "Unlimited storage",
            "Unlimited minutes",
            "Dedicated support",
            "SLA guarantee",
        ],
        "video_limit": -1,
        "message_limit": -1,
        "storage_limit_mb": -1,
        "minutes_limit": -1,
    },
}
```

#### 2.2.2: Subscription Service
Create `backend/app/services/subscription.py`:
- `get_user_quota()` - Calculate current usage vs limits
- `check_quota()` - Verify if action allowed
- `create_checkout_session()` - Initialize Stripe checkout
- `create_customer_portal_session()` - Manage subscription
- `handle_subscription_created()` - Stripe webhook handler
- `handle_subscription_updated()` - Update subscription status
- `handle_subscription_deleted()` - Cancel subscription
- `upgrade_tier()` - Immediate tier upgrade
- `downgrade_tier()` - Schedule tier downgrade

#### 2.2.3: Quota Enforcement Middleware
Create `backend/app/core/quota.py`:
```python
async def check_video_quota(user: User, db: Session):
    """Check if user can ingest another video."""
    quota = await subscription_service.get_user_quota(user.id, db)
    if quota.videos_remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "quota_exceeded",
                "message": "Video quota exceeded",
                "quota": quota.dict()
            }
        )

async def check_message_quota(user: User, db: Session):
    """Check if user can send another message."""
    # Similar implementation
```

Update endpoints:
- `backend/app/api/routes/videos.py:ingest_video()` - Add quota check
- `backend/app/api/routes/conversations.py:send_message()` - Add quota check

#### 2.2.4: Stripe Integration Endpoints
Create `backend/app/api/routes/subscriptions.py`:
```python
@router.post("/checkout")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Stripe checkout session for subscription."""

@router.post("/portal")
async def create_customer_portal_session(
    request: CustomerPortalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Stripe customer portal session."""

@router.get("/quota")
async def get_quota_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current quota usage."""

@router.get("/pricing")
async def get_pricing_tiers():
    """Get available pricing tiers."""
```

#### 2.2.5: Stripe Webhook Handler
Update `backend/app/api/routes/webhooks.py`:
```python
@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks."""
    # Verify webhook signature
    # Handle events:
    #   - checkout.session.completed
    #   - customer.subscription.created
    #   - customer.subscription.updated
    #   - customer.subscription.deleted
    #   - invoice.payment_succeeded
    #   - invoice.payment_failed
```

---

### Phase 2.3: Frontend UI Components

**Estimated Time**: 8-10 hours

#### 2.3.1: Landing Page with Pricing
Create `frontend/src/app/page.tsx`:
- Hero section with value proposition
- Feature highlights
- Pricing table (Free/Pro/Enterprise)
- CTA buttons → Stripe checkout
- Social proof / testimonials
- FAQ section

#### 2.3.2: Pricing Components
Create `frontend/src/components/pricing/`:
- `PricingTable.tsx` - Display all tiers
- `PricingCard.tsx` - Individual tier card
- `ComparisonTable.tsx` - Feature comparison
- `FAQSection.tsx` - Pricing FAQs

#### 2.3.3: Subscription Management UI
Create `frontend/src/app/account/subscription/page.tsx`:
- Current plan display
- Usage meters (videos, messages, storage, minutes)
- Upgrade/downgrade buttons
- Manage subscription (Stripe Customer Portal)
- Billing history

#### 2.3.4: Quota Display Components
Create `frontend/src/components/shared/`:
- `QuotaMeter.tsx` - Visual quota progress bar
- `QuotaWarning.tsx` - Warning when approaching limit
- `UpgradePrompt.tsx` - CTA when quota exceeded

Update existing pages:
- Add quota meters to `/videos`, `/conversations`
- Show upgrade prompts when limits reached
- Disable actions when quota exceeded

#### 2.3.5: Checkout Flow
Create `frontend/src/app/checkout/page.tsx`:
- Tier selection
- Billing cycle (monthly/yearly)
- Redirect to Stripe Checkout
- Success/cancel redirects

---

### Phase 2.4: Email Notifications

**Estimated Time**: 4-6 hours

#### 2.4.1: Email Service
Create `backend/app/services/email.py`:
```python
class EmailService:
    def send_welcome_email(user: User):
        """Send welcome email to new users."""

    def send_video_complete_notification(user: User, video: Video):
        """Notify when video processing completes."""

    def send_quota_warning(user: User, quota_type: str, usage_percent: int):
        """Warn when approaching quota limit (80%, 90%, 100%)."""

    def send_payment_success(user: User, subscription: Subscription):
        """Confirm successful payment."""

    def send_payment_failed(user: User, subscription: Subscription):
        """Alert on payment failure."""

    def send_subscription_canceled(user: User):
        """Confirm subscription cancellation."""
```

#### 2.4.2: Email Templates
Create HTML email templates in `backend/app/templates/emails/`:
- `welcome.html` - Welcome new users
- `video_complete.html` - Video processing done
- `quota_warning.html` - Approaching quota limit
- `payment_success.html` - Payment confirmation
- `payment_failed.html` - Payment failure alert
- `subscription_canceled.html` - Cancellation confirmation

#### 2.4.3: Email Triggers
Integrate email sending:
- `auth.py` → Send welcome email on signup
- `video_tasks.py` → Send completion email after video processing
- `conversations.py` → Send quota warning when approaching message limit
- `videos.py` → Send quota warning when approaching video limit
- `webhooks.py` (Stripe) → Send payment/cancellation emails

---

### Phase 2.5: Testing & Validation

**Estimated Time**: 6-8 hours

#### 2.5.1: Subscription Lifecycle Tests
Create `backend/tests/test_subscription_lifecycle.py`:
- Test free user signup
- Test upgrade to Pro
- Test downgrade to Free
- Test subscription cancellation
- Test subscription renewal
- Test payment failure handling

#### 2.5.2: Quota Enforcement Tests
Create `backend/tests/test_quota_enforcement.py`:
- Test video quota blocking
- Test message quota blocking
- Test storage quota blocking
- Test quota reset on upgrade
- Test unlimited quotas for Pro/Enterprise

#### 2.5.3: Stripe Integration Tests
Create `backend/tests/test_stripe_integration.py`:
- Test checkout session creation
- Test webhook signature verification
- Test subscription event handling
- Test customer portal session creation
- Test pricing tier retrieval

#### 2.5.4: Email Notification Tests
Create `backend/tests/test_email_notifications.py`:
- Test welcome email sending
- Test video completion email
- Test quota warning emails
- Test payment notification emails
- Test email template rendering

#### 2.5.5: End-to-End Testing
Manual testing checklist:
- [ ] Sign up as free user
- [ ] Ingest 2 videos (hit limit)
- [ ] Try to ingest 3rd video (should block with upgrade prompt)
- [ ] Upgrade to Pro via Stripe checkout (test mode)
- [ ] Verify quota increased
- [ ] Ingest additional videos (should work)
- [ ] Open customer portal, cancel subscription
- [ ] Verify cancellation at period end
- [ ] Receive all expected emails

---

## Environment Configuration

### Required Environment Variables

Add to `backend/.env`:
```bash
# Stripe
STRIPE_API_KEY="sk_test_..."  # Get from Stripe dashboard
STRIPE_WEBHOOK_SECRET="whsec_..."  # Get from Stripe webhook settings
STRIPE_PRICE_ID_PRO_MONTHLY="price_..."
STRIPE_PRICE_ID_PRO_YEARLY="price_..."
STRIPE_PRICE_ID_ENTERPRISE_MONTHLY="price_..."
STRIPE_PRICE_ID_ENTERPRISE_YEARLY="price_..."

# Resend
RESEND_API_KEY="re_..."  # Get from resend.com
FROM_EMAIL="noreply@yourdomain.com"
```

Add to `frontend/.env.local`:
```bash
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

---

## Stripe Dashboard Setup

### 1. Create Products
1. Go to Stripe Dashboard → Products
2. Create "Pro Plan":
   - Name: "Pro Plan"
   - Pricing: $20/month OR $200/year
   - Copy Price IDs

3. Create "Enterprise Plan":
   - Name: "Enterprise Plan"
   - Pricing: $100/month OR $1000/year
   - Copy Price IDs

### 2. Configure Webhooks
1. Go to Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/api/v1/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy webhook signing secret

### 3. Customer Portal
1. Go to Settings → Customer Portal
2. Enable portal
3. Configure:
   - Allow subscription cancellation
   - Allow plan changes
   - Show invoice history

---

## Implementation Checklist

### Backend
- [ ] Add pricing configuration (`backend/app/core/pricing.py`)
- [ ] Implement subscription service (`backend/app/services/subscription.py`)
- [ ] Add quota enforcement middleware (`backend/app/core/quota.py`)
- [ ] Create subscriptions API routes (`backend/app/api/routes/subscriptions.py`)
- [ ] Update Stripe webhook handler (`backend/app/api/routes/webhooks.py`)
- [ ] Integrate quota checks in videos.py and conversations.py
- [ ] Implement email service (`backend/app/services/email.py`)
- [ ] Create email templates (6 templates)
- [ ] Add email triggers in endpoints
- [ ] Run database migration: `alembic upgrade head`

### Frontend
- [ ] Create landing page with pricing (`frontend/src/app/page.tsx`)
- [ ] Build pricing components (4 components)
- [ ] Create subscription management page
- [ ] Build quota display components (3 components)
- [ ] Create checkout flow
- [ ] Update videos page with quota meters
- [ ] Update conversations page with quota warnings
- [ ] Add upgrade prompts throughout UI

### Testing
- [ ] Write subscription lifecycle tests
- [ ] Write quota enforcement tests
- [ ] Write Stripe integration tests
- [ ] Write email notification tests
- [ ] Run all Phase 1 security tests
- [ ] Perform end-to-end manual testing
- [ ] Load test quota enforcement
- [ ] Test Stripe webhooks in production mode

### Configuration
- [ ] Set up Stripe products and prices
- [ ] Configure Stripe webhooks
- [ ] Set up Stripe Customer Portal
- [ ] Create Resend account and get API key
- [ ] Add all environment variables
- [ ] Update CLAUDE.md with new features

---

## Success Criteria

Phase 2 is complete when:
- ✅ Users can upgrade/downgrade via Stripe
- ✅ Quotas are enforced on all actions
- ✅ Stripe webhooks handle all subscription events
- ✅ Emails sent for all key events
- ✅ Landing page displays pricing tiers
- ✅ Users can manage subscriptions via Customer Portal
- ✅ All tests pass
- ✅ End-to-end flow works in Stripe test mode

---

## Estimated Total Time

- **Phase 2.2 (Backend)**: 6-8 hours
- **Phase 2.3 (Frontend)**: 8-10 hours
- **Phase 2.4 (Email)**: 4-6 hours
- **Phase 2.5 (Testing)**: 6-8 hours

**Total**: 24-32 hours of implementation work

---

## Next Steps

1. **Run database migration**:
   ```bash
   docker compose exec app alembic upgrade head
   ```

2. **Install new dependencies**:
   ```bash
   docker compose exec app pip install stripe==7.8.0 resend==0.8.0
   ```

3. **Run Phase 1 security tests**:
   ```bash
   docker compose exec app pytest tests/test_phase1_security.py -v
   ```

4. **Start Phase 2.2 implementation**:
   - Begin with pricing configuration
   - Then subscription service
   - Then API endpoints
   - Test each component before moving forward

---

## Phase 3 Preview: Deployment

After Phase 2 is complete, Phase 3 will cover:
- Deploying to Railway or Hetzner VPS
- Setting up custom domain with SSL
- Configuring production environment variables
- Setting up database backups
- Adding monitoring (Sentry, UptimeRobot)
- Creating CI/CD pipeline
- Load testing and optimization

---

**Document Version**: 1.0
**Last Updated**: 2026-01-18
