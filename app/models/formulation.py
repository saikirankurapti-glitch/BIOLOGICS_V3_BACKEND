from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import Field

class FormulationDesign(Document):
    compound_id: str
    formulation_type: str
    drug_concentration: str
    buffer: str
    stabilizer: str
    surfactant: str
    recommended_ph: float
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "formulation_designs"
