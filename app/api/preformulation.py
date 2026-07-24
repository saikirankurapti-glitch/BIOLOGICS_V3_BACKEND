from fastapi import APIRouter, HTTPException, Depends, Response
from typing import List
from app.models.preformulation import PreformulationReport
from app.models.user import User
from app.api.dependencies import get_current_user
from app.utils.drug_development import calculate_preformulation_properties
from app.utils.report_generator import generate_preformulation_pdf
from pydantic import BaseModel

router = APIRouter()

class PreformulationRequest(BaseModel):
    compound_id: str
    smiles: str

@router.post("/analyze", response_model=PreformulationReport)
async def analyze_preformulation(request: PreformulationRequest):
    properties = calculate_preformulation_properties(request.smiles)
    if not properties:
        raise HTTPException(status_code=400, detail="Invalid SMILES string")
    
    report = PreformulationReport(
        compound_id=request.compound_id,
        smiles=request.smiles,
        **properties
    )
    
    existing = await PreformulationReport.find_one(PreformulationReport.compound_id == request.compound_id)
    if existing:
        report.id = existing.id
        await report.save()
    else:
        await report.insert()
        
    return report

@router.get("/reports", response_model=List[PreformulationReport])
async def get_all_reports():
    return await PreformulationReport.find_all().to_list()

@router.get("/report/{compound_id}", response_model=PreformulationReport)
async def get_report(compound_id: str):
    report = await PreformulationReport.find(PreformulationReport.compound_id == compound_id).sort("-_id").first_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

from fastapi.responses import Response
from app.utils.report_generator import generate_preformulation_pdf
import os
import uuid
from datetime import datetime
from app.models.registry import ReportRegistry

@router.get("/report/{compound_id}/pdf")
async def get_report_pdf(compound_id: str, user: User = Depends(get_current_user)):
    report = await PreformulationReport.find(PreformulationReport.compound_id == compound_id).sort("-_id").first_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    pdf_content = generate_preformulation_pdf(report.dict(), user)
    
    os.makedirs("./registry_files", exist_ok=True)
    filename = f"Preformulation_Report_{compound_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = os.path.join("./registry_files", filename)
    with open(file_path, "wb") as f:
        f.write(pdf_content)
        
    existing = await ReportRegistry.find_one(
        ReportRegistry.user_email == user.email,
        ReportRegistry.target_id == compound_id
    )
    if existing:
        if existing.file_path and os.path.exists(existing.file_path):
            try: os.remove(existing.file_path)
            except: pass
        existing.file_path = file_path
        existing.created_at = datetime.utcnow()
        await existing.save()
    else:
        new_report = ReportRegistry(
            user_email=user.email,
            target_id=compound_id,
            target_name=f"Compound {compound_id}",
            report_type="Preformulation Analysis",
            file_path=file_path
        )
        await new_report.insert()
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Preformulation_{compound_id}.pdf"
        }
    )
