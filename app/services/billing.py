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
        "limits": {
            "rows": 1000,
            "schemas": 5,
            "members": 3,
        }
    },
    "PRO": {
        "id": "pro",
        "name": "Pro",
        "price": 19900,  # in cents
        "limits": {
            "rows": None,
            "schemas": None,
            "members": None,
        }
    }
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
