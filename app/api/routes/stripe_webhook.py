import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.models.subscription import WebhookEvent
from sqlalchemy.orm import Session
from datetime import datetime
from app.services.billing import canonicalize_status

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
        # Idempotency: skip events we've already processed
        ev_id = event.get("id")
        if ev_id:
            exists = db.query(WebhookEvent).filter(WebhookEvent.event_id == ev_id).first()
            if exists:
                return {"received": True}
            db.add(WebhookEvent(event_id=ev_id))
            db.commit()
        if type == "checkout.session.completed":
            # Create subscription/customer record if present
            customer = obj.get("customer")
            subscription_id = obj.get("subscription")
            account_id = obj.get("metadata", {}).get("account_id")
            if account_id:
                rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
                # try to get current_period_end from event metadata/subscriptions
                cpe_ts = None
                try:
                    cpe_ts = obj.get("subscriptions", {}).get("current_period_end")
                except Exception:
                    cpe_ts = None
                cpe = datetime.utcfromtimestamp(int(cpe_ts)) if cpe_ts else None
                if not rec:
                    rec = Subscription(
                        account_id=account_id,
                        stripe_customer_id=customer,
                        stripe_subscription_id=subscription_id,
                        plan="PRO",
                        status=canonicalize_status("active"),
                        raw_stripe_status="active",
                        current_period_end=cpe,
                    )
                    db.add(rec)
                else:
                    rec.stripe_customer_id = customer
                    rec.stripe_subscription_id = subscription_id
                    rec.plan = "PRO"
                    rec.raw_stripe_status = "active"
                    rec.status = canonicalize_status("active")
                    rec.current_period_end = cpe
                if ev_id:
                    rec.last_stripe_event_id = ev_id
                db.commit()
        elif type == "customer.subscription.updated":
            # Update current_period_end and status when subscription changes (e.g., cancel_at_period_end)
            sub = obj
            sub_id = sub.get("id")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    # Stripe provides current_period_end as a timestamp
                    cpe = sub.get("current_period_end")
                    try:
                        rec.current_period_end = datetime.utcfromtimestamp(int(cpe)) if cpe else None
                    except Exception:
                        rec.current_period_end = None
                    # store raw stripe status and map to canonical
                    raw = sub.get("status")
                    rec.raw_stripe_status = raw or rec.raw_stripe_status
                    rec.status = canonicalize_status(raw) if raw else rec.status
                    if ev_id:
                        rec.last_stripe_event_id = ev_id
                    db.commit()
        elif type == "invoice.payment_failed":
            sub_id = obj.get("subscription")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.raw_stripe_status = "past_due"
                    rec.status = canonicalize_status("past_due")
                    if ev_id:
                        rec.last_stripe_event_id = ev_id
                    db.commit()
        elif type == "invoice.payment_succeeded" or type == "invoice.paid":
            sub_id = obj.get("subscription")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.raw_stripe_status = "active"
                    rec.status = canonicalize_status("active")
                    if ev_id:
                        rec.last_stripe_event_id = ev_id
                    db.commit()
        elif type == "checkout.session.async_payment_failed":
            # Async payment that failed after checkout completion
            session = obj
            sub_id = session.get("subscription")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.raw_stripe_status = "incomplete"
                    rec.status = canonicalize_status("incomplete")
                    if ev_id:
                        rec.last_stripe_event_id = ev_id
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
