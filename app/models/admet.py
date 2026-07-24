from typing import Optional, Dict, Any, List
from datetime import datetime
from beanie import Document
from pydantic import Field

class ADMETJob(Document):
    smiles: str
    target_id: Optional[str] = None
    status: str = "Pending"
    results: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "admet_jobs"
