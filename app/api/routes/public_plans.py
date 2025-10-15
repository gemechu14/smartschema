from typing import Any, Dict
from fastapi import APIRouter
from app.services.billing import PLANS

router = APIRouter(prefix="", tags=["public"])


@router.get(
    "/plans",
    response_model=Dict[str, Any],
    summary="Public list of plans",
    description="Return available plans and their limits and feature flags. Public (no account required).",
)
def public_list_plans():
    out = {}
    for k, v in PLANS.items():
        limits = v.get("limits", {})
        features = {
            "api_access": True if k == "PRO" else False,
            "white_label_embedding": True if k == "PRO" else False,
            "community_support": True if k == "FREE" else False,
            "priority_support": True if k == "PRO" else False,
        }
        out[k] = {
            "id": v.get("id"),
            "name": v.get("name"),
            "price": v.get("price"),
            "import_formats": v.get("import_formats", []),
            "limits": {
                "rows": limits.get("rows"),
                "schemas": limits.get("schemas"),
                "members": limits.get("members"),
            },
            "features": features,
        }
    return out
