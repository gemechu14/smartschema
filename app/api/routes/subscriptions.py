from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps_auth import require_role_for_account, get_db
from app.models.auth_models import Role
from app.models.subscription import Subscription
from app.services.billing import create_checkout_session, create_billing_portal_session, PLANS
from app.services.billing import status_description
from app.core.config import settings
from uuid import UUID
from app.schemas.subscription import PlansResponse, CheckoutResponse, PortalResponse, SubscriptionRead

router = APIRouter(prefix="/accounts/{account_id}/subscriptions", tags=["subscriptions"])


# account-scoped plans endpoint removed in favor of public `/plans` endpoint


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
    # Return the user to a dedicated billing portal return page so frontend can display updated status
    return_url = f"{settings.app_base_url}/billing/portal-return"
    try:
        session = create_billing_portal_session(rec.stripe_customer_id, return_url)
    except Exception as e:
        # Common cause: Billing Portal not configured in Stripe test/live settings
        msg = str(e)
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not create Billing Portal session: "
                f"{msg}.\nEnsure you have configured the Customer Portal in your Stripe dashboard (test/live) at: "
                "https://dashboard.stripe.com/test/settings/billing/portal"
            ),
        )
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
        free = PLANS.get("FREE", {})
        return {
            "plan": "FREE",
            "status": "active",
            "current_period_end": None,
            "display_status": "Active (Free)",
            "status_description": status_description("active"),
            "limits": free.get("limits"),
            "features": {
                "api_access": False,
                "white_label_embedding": False,
                "community_support": True,
                "priority_support": False,
            }
        }

    plan_meta = PLANS.get(rec.plan, {})
    features = {
        "api_access": True if rec.plan == "PRO" else False,
        "white_label_embedding": True if rec.plan == "PRO" else False,
        "community_support": True if rec.plan == "FREE" else False,
        "priority_support": True if rec.plan == "PRO" else False,
    }

    return {
        "plan": rec.plan,
        "status": rec.status,
        "current_period_end": rec.current_period_end,
        "display_status": (rec.status.capitalize() if rec.status else "Unknown"),
        "status_description": status_description(rec.status or "unknown"),
        "limits": plan_meta.get("limits"),
        "features": features,
    }
