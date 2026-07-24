from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import Field

class PreformulationReport(Document):
    compound_id: str
    smiles: str
    molecular_weight: float
    logp: float
    tpsa: float
    h_bond_donors: int
    h_bond_acceptors: int
    rotatable_bonds: int
    solubility_prediction: str
    stability_risk: List[str]
    recommended_excipients: List[str]
    lipinski_violations: int
    veber_violations: int
    drug_likeness_status: str
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "preformulation_reports"
