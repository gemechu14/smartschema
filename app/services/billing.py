import stripe
from typing import Optional
from app.core.config import settings

stripe.api_key = settings.stripe_secret if hasattr(settings, "stripe_secret") else None

# We'll read env var STRIPE_SECRET_KEY at runtime too as a fallback
import os
if not stripe.api_key:
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Plan ids - recommend mapping to Stripe Price IDs in your Stripe dashboard
PLANS = {
    "FREE": {
        "id": "free",
        "name": "Free",
        "price": 0,
        "import_formats": ["csv", "excel", "json"],
        "limits": {
            "rows": 1000,
            "schemas": 5,
            "members": 3,
        },
    },
    "PRO": {
        "id": "pro",
        "name": "Pro",
        "price": 19900,  # in cents
        "import_formats": ["csv", "excel", "json"],
        "limits": {
            "rows": None,
            "schemas": None,
            "members": None,
        },
    },
}


def create_checkout_session(customer_email: str, plan_key: str, success_url: str, cancel_url: str, account_id: str) -> dict:
    """Create a Stripe Checkout Session for the given plan_key.

    plan_key should be one of 'FREE' or 'PRO'. For 'FREE' we may still create a customer but no subscription.
    """
    if plan_key not in PLANS:
        raise ValueError("Unknown plan")

    plan = PLANS[plan_key]

    # For PRO, expect you created a Price in Stripe and set PRICE_ID_PRO in env
    if plan_key == "PRO":
        price_id = os.getenv("STRIPE_PRICE_ID_PRO")
        if not price_id:
            raise RuntimeError("STRIPE_PRICE_ID_PRO not configured")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=customer_email,
            line_items=[{"price": price_id, "quantity": 1}],
            # Request a 14-day trial period on the subscription created by Checkout.
            # Stripe will set `trial_end` on the created subscription and emit webhook events
            # which our webhook handler should use to populate the local `trial_ends_at`.
            subscription_data={"trial_period_days": 14},
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"account_id": str(account_id)},
        )
        return session
    else:
        # Free plan: create a customer only (optional)
        customer = stripe.Customer.create(email=customer_email, metadata={"account_id": str(account_id)})
        return {"customer": customer}


def create_billing_portal_session(stripe_customer_id: str, return_url: str) -> dict:
    if not stripe_customer_id:
        raise ValueError("stripe_customer_id required")
    session = stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=return_url)
    return session


def retrieve_subscription(stripe_subscription_id: Optional[str] = None, stripe_customer_id: Optional[str] = None) -> Optional[dict]:
    try:
        if stripe_subscription_id:
            sub = stripe.Subscription.retrieve(stripe_subscription_id)
            return sub
        if stripe_customer_id:
            subs = stripe.Subscription.list(customer=stripe_customer_id, limit=1)
            if subs and subs.data:
                return subs.data[0]
    except Exception:
        return None
    return None


def canonicalize_status(raw_status: Optional[str]) -> str:
    """Map Stripe raw status to a small canonical set used by the app."""
    if not raw_status:
        return "unknown"
    s = raw_status.lower()
    if s in ("active", "trialing"):
        return "active"
    if s in ("incomplete", "incomplete_expired"):
        return "incomplete"
    if s in ("past_due", "unpaid"):
        return "past_due"
    if s in ("canceled", "cancelled"):
        return "canceled"
    if s in ("paused", "pause_collection"):
        return "paused"
    return s


def status_description(canonical_status: str) -> str:
    """Return a user-friendly description for a canonical status."""
    desc = {
        "active": "Subscription is active and billing is up to date.",
        "trialing": "Subscription is on a trial period.",
        "incomplete": "Subscription has an incomplete or failed initial payment.",
        "past_due": "Payment is past due; action may be required to avoid cancellation.",
        "unpaid": "Subscription payments have failed and it is unpaid.",
        "canceled": "Subscription has been canceled and will not renew.",
        "paused": "Subscription is paused.",
        "unknown": "Subscription status is unknown.",
    }
    return desc.get(canonical_status, "Subscription status: " + canonical_status)
