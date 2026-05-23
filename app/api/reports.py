from fastapi import APIRouter, HTTPException, BackgroundTasks
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

@router.get("/list")
async def list_reports():
    temp_dir = "./temp_uploads"
    if not os.path.exists(temp_dir):
        return []
        
    reports = [f for f in os.listdir(temp_dir) if f.endswith(".pdf")]
    return reports
