import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from sqlalchemy.orm import Session
from datetime import datetime

router = APIRouter(prefix="/stripe", tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or getattr(settings, "stripe_secret", None)
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def _get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/webhook",
    summary="Stripe webhook receiver",
    description="Receive and validate Stripe webhook events. Updates subscription records for checkout/session events.",
)
async def webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {e}")

    # handle relevant events
    type = event["type"]
    obj = event["data"]["object"]

    db: Session = next(_get_db())
    try:
        if type == "checkout.session.completed":
            # Create subscription/customer record if present
            customer = obj.get("customer")
            subscription_id = obj.get("subscription")
            account_id = obj.get("metadata", {}).get("account_id")
            if account_id:
                rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
                if not rec:
                    rec = Subscription(account_id=account_id, stripe_customer_id=customer, stripe_subscription_id=subscription_id, plan="PRO", status="active", current_period_end=datetime.utcfromtimestamp(obj.get("subscriptions", {}).get("current_period_end", 0)))
                    db.add(rec)
                else:
                    rec.stripe_customer_id = customer
                    rec.stripe_subscription_id = subscription_id
                    rec.plan = "PRO"
                    rec.status = "active"
                db.commit()
        elif type == "invoice.payment_failed":
            sub_id = obj.get("subscription")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.status = "past_due"
                    db.commit()
        elif type == "customer.subscription.deleted":
            sub_id = obj.get("id")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.status = "canceled"
                    db.commit()
    finally:
        db.close()

    return {"received": True}
