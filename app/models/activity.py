from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional, Dict, Any

class UserActivity(Document):
    user_id: str
    user_email: str
    action: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "user_activities"
