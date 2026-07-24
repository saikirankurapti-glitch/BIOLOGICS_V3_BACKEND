from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Optional

class ReportRegistry(Document):
    user_email: str
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    report_type: str = "Target Intelligence"
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "report_registry"
