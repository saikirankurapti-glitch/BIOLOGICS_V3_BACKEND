from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional

class AccessLog(Document):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event: str
    user: str
    method: str
    path: str
    query: str
    status: int
    latency_ms: float
    client_ip: str
    user_agent: str
    
    class Settings:
        name = "access_logs"
