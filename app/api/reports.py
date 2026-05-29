from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from app.services.report_engine import generate_pdf_report

router = APIRouter()

class ReportRequest(BaseModel):
    target_name: str
    summary_data: dict
    molecules: list

@router.post("/generate")
async def create_report(request: ReportRequest):
    try:
        # Validate data
        if not request.molecules:
            raise HTTPException(status_code=400, detail="Molecules list cannot be empty")
            
        # Generate the Report
        file_path = generate_pdf_report(request.target_name, request.summary_data, request.molecules)
        
        if os.path.exists(file_path):
            return FileResponse(
                path=file_path,
                filename=os.path.basename(file_path),
                media_type='application/pdf'
            )
        else:
            raise HTTPException(status_code=500, detail="Report generation failed (File not found)")
            
    except Exception as e:
        print(f"Report Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from app.models.registry import ReportRegistry
from app.api.dependencies import get_current_user
from app.models.user import User

@router.get("/list")
async def list_reports(user: User = Depends(get_current_user)):
    reports = await ReportRegistry.find(ReportRegistry.user_email == user.email).to_list()
    return reports

@router.get("/download/{report_id}")
async def download_registry_report(report_id: str, user: User = Depends(get_current_user)):
    from bson import ObjectId
    try:
        report = await ReportRegistry.get(ObjectId(report_id))
    except:
        report = None
        
    if not report or report.user_email != user.email:
        raise HTTPException(status_code=404, detail="Report not found")
        
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="File missing on server")
    
    return FileResponse(
        path=report.file_path,
        filename=os.path.basename(report.file_path),
        media_type='application/pdf'
    )
