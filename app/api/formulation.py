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

@router.get("/design/{compound_id}/pdf")
async def get_design_pdf(compound_id: str, user: User = Depends(get_current_user)):
    design = await FormulationDesign.find(FormulationDesign.compound_id == compound_id).sort("-_id").first_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    
    pre_report = await PreformulationReport.find_one(PreformulationReport.compound_id == compound_id)
    if not pre_report:
         raise HTTPException(status_code=404, detail="Associated preformulation report not found")

    pdf_content = generate_formulation_pdf(design.dict(), pre_report.dict(), user)
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Formulation_{compound_id}.pdf"
        }
    )
