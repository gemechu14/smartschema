from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class PlanInfo(BaseModel):
    name: str
    price: int
    limits: Dict[str, Optional[int]]

class PlansResponse(BaseModel):
    plans: Dict[str, PlanInfo]

class CheckoutResponse(BaseModel):
    checkout_session_id: str
    url: str

class PortalResponse(BaseModel):
    url: str

class SubscriptionRead(BaseModel):
    plan: str
    status: str
    current_period_end: Optional[datetime] = None
