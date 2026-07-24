from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional, Dict, Any

class TokenTransaction(Document):
    user_id: str
    user_email: Optional[str] = None
    amount: int
    module: str
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    order_id: Optional[str] = None
    payment_session_id: Optional[str] = None
    status: str = "COMPLETED" # PENDING, SUCCESS, FAILED, COMPLETED
    amount_paid: Optional[float] = None
    currency: str = "USD"

    class Settings:
        name = "token_transactions"
