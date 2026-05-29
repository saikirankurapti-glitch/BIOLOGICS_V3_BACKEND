from fastapi import APIRouter, HTTPException, Depends, Response
from typing import List
from app.models.formulation import FormulationDesign
from app.models.preformulation import PreformulationReport
from app.models.user import User
from app.api.dependencies import get_current_user
from app.utils.drug_development import design_formulation_logic
from app.utils.report_generator import generate_formulation_pdf
from pydantic import BaseModel

router = APIRouter()

class FormulationRequest(BaseModel):
    compound_id: str
    route: str = "injection"

@router.post("/design", response_model=FormulationDesign)
async def design_formulation(request: FormulationRequest):
    # Fetch preformulation results first
    pre_report = await PreformulationReport.find_one(PreformulationReport.compound_id == request.compound_id)
    if not pre_report:
        raise HTTPException(status_code=400, detail="Preformulation analysis must be completed first")
    
    design_data = design_formulation_logic(pre_report.dict(), request.route)
    
    design = FormulationDesign(
        compound_id=request.compound_id,
        **design_data
    )
    
    existing = await FormulationDesign.find_one(FormulationDesign.compound_id == request.compound_id)
    if existing:
        design.id = existing.id
        await design.save()
    else:
        await design.insert()
        
    return design

@router.get("/designs", response_model=List[FormulationDesign])
async def get_all_designs():
    return await FormulationDesign.find_all().to_list()

@router.get("/design/{compound_id}", response_model=FormulationDesign)
async def get_design(compound_id: str):
    design = await FormulationDesign.find(FormulationDesign.compound_id == compound_id).sort("-_id").first_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    return design

from fastapi.responses import Response
from app.utils.report_generator import generate_formulation_pdf
import os
import uuid
from datetime import datetime
from app.models.registry import ReportRegistry

@router.get("/design/{compound_id}/pdf")
async def get_design_pdf(compound_id: str, user: User = Depends(get_current_user)):
    design = await FormulationDesign.find(FormulationDesign.compound_id == compound_id).sort("-_id").first_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    
    pre_report = await PreformulationReport.find_one(PreformulationReport.compound_id == compound_id)
    if not pre_report:
         raise HTTPException(status_code=404, detail="Associated preformulation report not found")

    pdf_content = generate_formulation_pdf(design.dict(), pre_report.dict(), user)
    
    os.makedirs("./registry_files", exist_ok=True)
    filename = f"Formulation_Report_{compound_id}_{uuid.uuid4().hex[:8]}.pdf"
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
            report_type="Formulation Design",
            file_path=file_path
        )
        await new_report.insert()
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Formulation_{compound_id}.pdf"
        }
    )
