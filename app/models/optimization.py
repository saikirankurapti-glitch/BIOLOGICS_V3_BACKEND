from beanie import Document
from typing import Dict, Any, Optional
from datetime import datetime

class OptimizationJob(Document):
    target_id: str
    constraints: Dict[str, Any]
    status: str = "Pending"
    results: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None

    class Settings:
        name = "optimizations"
