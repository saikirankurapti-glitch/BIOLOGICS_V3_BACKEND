from typing import Optional, Dict, Any, List
from beanie import Document, Link
from pydantic import BaseModel, Field
from datetime import datetime
from .target import Target
from .user import User

class ExperimentResult(BaseModel):
    data: Dict[str, Any] # Flexible storage for results
    score: Optional[float] = None
    artifacts: List[str] = [] # Paths to images or files

class Experiment(Document):
    name: str
    blinded_id: Optional[str] = None # Secure ID for blinded reviewers
    description: Optional[str] = None
    experiment_type: str # e.g., "Binding Affinity", "Toxicity", "Stability"
    target_id: Optional[str] = None # Reference to a Target ID string manually if needed, or Link
    # For simplicity in this demo/MVP, we store IDs as strings mostly, or use Link which Beanie supports.
    # Let's use string for simpler initial setup unless we want strict relations.
    target_name: Optional[str] = None
    
    status: str = "Planned" # Planned, Running, Completed, Failed
    parameters: Dict[str, Any] = {}
    results: Optional[ExperimentResult] = None
    
    created_by: Optional[str] = None # User email or ID
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "experiments"
