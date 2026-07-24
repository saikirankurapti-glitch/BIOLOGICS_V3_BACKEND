from typing import Optional, Dict, Any, List
from datetime import datetime
from beanie import Document
from pydantic import Field

class DockingJob(Document):
    target_id: str
    ligand_id: Optional[str] = None
    ligand_smiles: str
    status: str = "Pending" # Pending, Running, Completed, Failed
    results: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "docking_jobs"
