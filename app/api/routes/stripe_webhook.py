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
from app.services.billing import retrieve_subscription
from app.models.auth_models import User, Membership

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
            # If the Checkout Session didn't include metadata.account_id, try to resolve it
            if not account_id:
                # 1) If subscription id is present, fetch subscription from Stripe to look for metadata
                if subscription_id:
                    try:
                        sub = retrieve_subscription(stripe_subscription_id=subscription_id)
                        if sub:
                            account_id = sub.get("metadata", {}).get("account_id")
                    except Exception:
                        account_id = None
                # 2) If still no account_id, try to find a user by customer email (if provided) and use their first membership
                if not account_id:
                    customer_email = obj.get("customer_details", {}).get("email") or obj.get("customer_email")
                    if customer_email:
                        user = db.query(User).filter(User.email == customer_email.lower()).first()
                        if user:
                            membership = db.query(Membership).filter(Membership.user_id == user.id).first()
                            if membership:
                                account_id = str(membership.account_id)

            if account_id:
                rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
                # try to get current_period_end from event metadata/subscriptions
                cpe_ts = None
                try:
                    cpe_ts = obj.get("subscriptions", {}).get("current_period_end")
                except Exception:
                    cpe_ts = None
                # If the checkout session only has a subscription id (common), fetch the subscription from Stripe
                if not cpe_ts and subscription_id:
                    try:
                        sub_obj = retrieve_subscription(stripe_subscription_id=subscription_id)
                        if sub_obj:
                            # sub_obj may be a stripe.Subscription object or dict-like
                            try:
                                cpe_ts = sub_obj.get("current_period_end")
                            except Exception:
                                # fallback to attribute access
                                cpe_ts = getattr(sub_obj, "current_period_end", None)
                            # Also attempt to read trial_end (if Stripe provided a trial)
                            try:
                                trial_ts = sub_obj.get("trial_end")
                            except Exception:
                                trial_ts = getattr(sub_obj, "trial_end", None)
                            except Exception:
                                # fallback to attribute access
                                cpe_ts = getattr(sub_obj, "current_period_end", None)
                            # Some Stripe responses put current_period_end on the subscription items
                            if not cpe_ts:
                                try:
                                    items = sub_obj.get("items", {}).get("data", [])
                                except Exception:
                                    items = getattr(sub_obj, "items", None)
                                try:
                                    # items may be a ListObject with data attribute
                                    for it in items or []:
                                        try:
                                            cpe_ts = it.get("current_period_end")
                                        except Exception:
                                            cpe_ts = getattr(it, "current_period_end", None)
                                        if cpe_ts:
                                            break
                                except Exception:
                                    pass
                            print(f'[webhook] fetched stripe subscription {subscription_id} cpe={cpe_ts}')
                    except Exception:
                        cpe_ts = None

                cpe = None
                try:
                    cpe = datetime.utcfromtimestamp(int(cpe_ts)) if cpe_ts else None
                except Exception:
                    cpe = None
                trial_dt = None
                try:
                    trial_dt = datetime.utcfromtimestamp(int(trial_ts)) if ("trial_ts" in locals() and trial_ts) else None
                except Exception:
                    trial_dt = None
                if not rec:
                    rec = Subscription(
                        account_id=account_id,
                        stripe_customer_id=customer,
                        stripe_subscription_id=subscription_id,
                        plan="PRO",
                        status=canonicalize_status("active"),
                        raw_stripe_status="active",
                        current_period_end=cpe,
                        trial_ends_at=trial_dt,
                    )
                    db.add(rec)
                else:
                    rec.stripe_customer_id = customer
                    rec.stripe_subscription_id = subscription_id
                    rec.plan = "PRO"
                    rec.raw_stripe_status = "active"
                    rec.status = canonicalize_status("active")
                    rec.current_period_end = cpe
                    # update local trial_ends_at if Stripe provided a trial_end
                    if trial_dt:
                        rec.trial_ends_at = trial_dt
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
                    # also check for trial_end on subscription updates
                    trial_ts = sub.get("trial_end")
                    # If cpe missing in the event, try fetching full subscription from Stripe
                    if not cpe:
                        try:
                            fetched = retrieve_subscription(stripe_subscription_id=sub_id)
                            if fetched:
                                try:
                                    cpe = fetched.get("current_period_end")
                                except Exception:
                                    cpe = getattr(fetched, "current_period_end", None)
                                # attempt to read trial_end from fetched subscription
                                try:
                                    fetched_trial = fetched.get("trial_end")
                                except Exception:
                                    fetched_trial = getattr(fetched, "trial_end", None)
                                # inspect items if still missing
                                if not cpe:
                                    try:
                                        items = fetched.get("items", {}).get("data", [])
                                    except Exception:
                                        items = getattr(fetched, "items", None)
                                    try:
                                        for it in items or []:
                                            try:
                                                cpe = it.get("current_period_end")
                                            except Exception:
                                                cpe = getattr(it, "current_period_end", None)
                                            if cpe:
                                                break
                                    except Exception:
                                        pass
                            print(f'[webhook] customer.subscription.updated fetched cpe={cpe} for sub={sub_id}')
                        except Exception:
                            cpe = None
                    try:
                        rec.current_period_end = datetime.utcfromtimestamp(int(cpe)) if cpe else None
                    except Exception:
                        rec.current_period_end = None
                    # set or clear trial_ends_at from event or fetched subscription
                    try:
                        trial_val = trial_ts or (fetched_trial if 'fetched_trial' in locals() else None)
                        rec.trial_ends_at = datetime.utcfromtimestamp(int(trial_val)) if trial_val else None
                    except Exception:
                        # leave existing value untouched on parse failure
                        pass
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
        elif type == "setup_intent.setup_failed":
            # SetupIntent failed (often during collecting/attaching a payment method)
            si = obj
            # try to resolve a related subscription via customer
            customer = si.get("customer") or si.get("metadata", {}).get("customer")
            updated = False
            if customer:
                sub_obj = retrieve_subscription(stripe_customer_id=customer)
                if sub_obj:
                    sub_id = None
                    try:
                        sub_id = sub_obj.get("id")
                    except Exception:
                        sub_id = getattr(sub_obj, "id", None)
                    if sub_id:
                        rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                        if rec:
                            rec.raw_stripe_status = "incomplete"
                            rec.status = canonicalize_status("incomplete")
                            if ev_id:
                                rec.last_stripe_event_id = ev_id
                            db.commit()
                            updated = True
            if not updated:
                # fallback: if metadata contains account_id try to mark that account subscription
                acct = si.get("metadata", {}).get("account_id")
                if acct:
                    rec = db.query(Subscription).filter(Subscription.account_id == acct).first()
                    if rec:
                        rec.raw_stripe_status = "incomplete"
                        rec.status = canonicalize_status("incomplete")
                        if ev_id:
                            rec.last_stripe_event_id = ev_id
                        db.commit()
        elif type == "payment_intent.payment_failed":
            # Payment failed for a PaymentIntent (could be associated with an invoice/subscription)
            pi = obj
            # Try direct subscription id
            sub_id = pi.get("subscription") or None
            if not sub_id:
                # sometimes PaymentIntent links to invoice which links to subscription
                inv_id = pi.get("invoice")
                if inv_id:
                    try:
                        inv = stripe.Invoice.retrieve(inv_id)
                        sub_id = inv.get("subscription")
                    except Exception:
                        sub_id = None
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    rec.raw_stripe_status = "past_due"
                    rec.status = canonicalize_status("past_due")
                    if ev_id:
                        rec.last_stripe_event_id = ev_id
                    db.commit()
            else:
                # fallback: try resolving by customer
                customer = pi.get("customer")
                if customer:
                    sub_obj = retrieve_subscription(stripe_customer_id=customer)
                    if sub_obj:
                        try:
                            sid = sub_obj.get("id")
                        except Exception:
                            sid = getattr(sub_obj, "id", None)
                        if sid:
                            rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sid).first()
                            if rec:
                                rec.raw_stripe_status = "past_due"
                                rec.status = canonicalize_status("past_due")
                                if ev_id:
                                    rec.last_stripe_event_id = ev_id
                                db.commit()
        elif type == "customer.subscription.deleted":
            sub_id = obj.get("id")
            if sub_id:
                rec = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
                if rec:
                    # mark canceled; attempt to preserve current_period_end if available on the event or via fetch
                    rec.status = "canceled"
                    cpe = obj.get("current_period_end") or obj.get("ended_at")
                    # if Stripe provided trial_end on deletion event, capture it as well
                    trial_ts = obj.get("trial_end")
                    if not cpe:
                        try:
                            fetched = retrieve_subscription(stripe_subscription_id=sub_id)
                            if fetched:
                                try:
                                    cpe = fetched.get("current_period_end")
                                except Exception:
                                    cpe = getattr(fetched, "current_period_end", None)
                                # try to read trial_end from fetched subscription
                                try:
                                    fetched_trial = fetched.get("trial_end")
                                except Exception:
                                    fetched_trial = getattr(fetched, "trial_end", None)
                                if not cpe:
                                    try:
                                        items = fetched.get("items", {}).get("data", [])
                                    except Exception:
                                        items = getattr(fetched, "items", None)
                                    try:
                                        for it in items or []:
                                            try:
                                                cpe = it.get("current_period_end")
                                            except Exception:
                                                cpe = getattr(it, "current_period_end", None)
                                            if cpe:
                                                break
                                    except Exception:
                                        pass
                        except Exception:
                            cpe = None
                    try:
                        rec.current_period_end = datetime.utcfromtimestamp(int(cpe)) if cpe else None
                    except Exception:
                        rec.current_period_end = None
                    db.commit()
    finally:
        db.close()

    return {"received": True}
