from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps_auth import require_role_for_account, get_db
from app.models.auth_models import Role
from app.models.subscription import Subscription
from app.services.billing import create_checkout_session, create_billing_portal_session, PLANS
from app.core.config import settings
from uuid import UUID
from app.schemas.subscription import PlansResponse, CheckoutResponse, PortalResponse, SubscriptionRead

router = APIRouter(prefix="/accounts/{account_id}/subscriptions", tags=["subscriptions"])


@router.get(
    "/plans",
    response_model=Dict[str, PlansResponse] | Dict[str, Any],
    summary="List available plans",
    description="Return available plans and their limits (rows, schemas, members). Does not expose Stripe price IDs.",
)
def list_plans():
    # Return simple plan metadata (do not expose Stripe price ids here)
    return {k: {"name": v["name"], "price": v["price"], "limits": v["limits"]} for k, v in PLANS.items()}


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Create a Stripe Checkout session (PRO)",
    description="Create a Stripe Checkout session to subscribe the account to the PRO plan. Only OWNER/ADMIN may create."
)
def create_checkout(
    account_id: UUID,
    db: Session = Depends(get_db),
    tup = Depends(require_role_for_account({Role.OWNER})),
):
    # For now create a checkout only for PRO; price id must be configured in STRIPE_PRICE_ID_PRO
    user, _aid, _role = tup
    plan_key = "PRO"
    success_url = settings.app_base_url + "/billing/success"
    cancel_url = settings.app_base_url + "/billing/cancel"
    session = create_checkout_session(user.email, plan_key, success_url, cancel_url, account_id)
    return {"checkout_session_id": session.id, "url": session.url}


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create a Stripe Billing Portal session",
    description="Redirects account owner to the Stripe Billing Portal for subscription management. Requires an existing Stripe customer linked to the account."
)
def create_portal(account_id: UUID, db: Session = Depends(get_db), tup = Depends(require_role_for_account({Role.OWNER}))):
    user, _aid, _role = tup
    # Look up subscription record to get stripe_customer_id
    rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
    if not rec or not rec.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No billing customer found for account")
    session = create_billing_portal_session(rec.stripe_customer_id, settings.app_base_url)
    return {"url": session.url}


@router.get(
    "/",
    response_model=SubscriptionRead,
    summary="Get subscription status for account",
    description="Return the current subscription plan and status for the given account."
)
def get_subscription(account_id: UUID, db: Session = Depends(get_db), tup = Depends(require_role_for_account({Role.OWNER}))):
    user, _aid, _role = tup
    rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
    if not rec:
        # default to FREE
        return {"plan": "FREE", "status": "free", "current_period_end": None}
    return {
        "plan": rec.plan,
        "status": rec.status,
        "current_period_end": rec.current_period_end,
    }
