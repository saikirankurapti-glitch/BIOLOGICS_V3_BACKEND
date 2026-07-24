from beanie import Document
from typing import Dict, Any, Optional
from datetime import datetime

class ScreeningJob(Document):
    target_id: str
    library_id: str
    status: str = "Pending" # Pending, Running, Completed, Failed
    results: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None

    class Settings:
        name = "screenings"
