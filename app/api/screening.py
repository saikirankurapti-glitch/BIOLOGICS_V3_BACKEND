from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, Form, Depends
from app.models.screening import ScreeningJob
from app.models.user import User
from app.api.dependencies import get_current_user
from typing import List, Optional
import asyncio
import os
import shutil
import pickle
import numpy as np
from datetime import datetime
from app.utils.cheminformatics import calculate_molecular_properties, extract_features
from app.utils.file_parsers import parse_molecules
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, MACCSkeys, Descriptors

# Disable RDKit C++ backend warnings (hides the MorganGenerator terminal spam)
RDLogger.DisableLog('rdApp.*')

router = APIRouter()

# --- REAL AI INFERENCE ENGINE ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ai_models", "binding_affinity_model.pkl")
AI_MODEL = None

try:
    with open(MODEL_PATH, "rb") as f:
        AI_MODEL = pickle.load(f)
    print("SUCCESS Logic: XGBoost Model Loaded Successfully")
except Exception as e:
    print(f"WARNING Warning: perform 'python train_ai_model.py' first. Using mock mode. {e}")

from app.utils.websockets import manager

async def run_ai_screening_task(job_id: str, file_paths: List[str]):
    """
    Parses multiple uploaded files and runs inference on every molecule.
    Supported formats: .smi, .sdf, .mol2, .csv, .mzml, .mzxml
    """
    all_hits = []
    
    for file_path in file_paths:
        try:
            parsed_molecules = parse_molecules(file_path)
            if not parsed_molecules:
                continue
        except Exception as e:
            await manager.broadcast(f"ERROR Error parsing file {os.path.basename(file_path)}: {e}", job_id)
            continue

        await manager.broadcast(f"SCAN [Job {job_id}] Screening {len(parsed_molecules)} molecules from {os.path.basename(file_path)}...", job_id)

        processed_count = 0
        for mol_entry in parsed_molecules:
            smiles = mol_entry["smiles"]
            mol_id = mol_entry["mol_id"]
            
            props = calculate_molecular_properties(smiles)
            if not props:
                continue
                
            try:
                features = extract_features(smiles).reshape(1, -1)
            except Exception as e:
                continue
                
            score = -5.0
            conf = 0.0
            
            if AI_MODEL:
                try:
                    raw_score = AI_MODEL.predict(features)[0]
                    score = round(float(raw_score), 2)
                    conf = min(0.99, abs(score)/12.0)
                except Exception as e:
                    pass
            
            all_hits.append({
                "molecule_id": mol_id,
                "smiles": smiles,
                "properties": props,
                "affinity": score,
                "confidence": round(conf, 2)
            })
            processed_count += 1
            
            if processed_count % 10 == 0:
                await manager.broadcast(f"Processing {os.path.basename(file_path)}... {processed_count}/{len(parsed_molecules)}", job_id)
                await asyncio.sleep(0.01)

    # Sort all merged hits by affinity
    all_hits.sort(key=lambda x: x["affinity"], reverse=True)
    top_hits = all_hits[:100]

    # Update Job
    job = await ScreeningJob.get(job_id)
    if job:
        job.results = {
        "hits_found": len(all_hits),
        "top_hits": top_hits
    }
    job.status = "Completed"
    job.completed_at = datetime.now()
    await job.save()
    
    await manager.broadcast(f"OK Screening Complete. Found {len(all_hits)} hits across all files.", job_id)
        
    # Cleanup temp files
    for path in file_paths:
        if os.path.exists(path):
            os.remove(path)


@router.post("/run", response_model=ScreeningJob)
async def run_screening(
    target_id: str = Form(...), 
    library_id: str = Form(...), 
    background_tasks: BackgroundTasks = BackgroundTasks(),
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Consolidate all uploaded files
    all_files = []
    if files:
        all_files.extend(files)
    if file:
        all_files.append(file)
        
    if not all_files:
        raise HTTPException(status_code=422, detail="No files provided for screening.")
    
    file_paths = []
    
    for f in all_files:
        original_ext = os.path.splitext(f.filename)[1].lower() if f.filename else ".smi"
        timestamp = int(datetime.now().timestamp())
        # Clean filename to prevent path issues
        safe_name = "".join([c if c.isalnum() else "_" for c in (f.filename or "library")])
        file_path = os.path.join(temp_dir, f"{library_id}_{timestamp}_{safe_name}{original_ext}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        file_paths.append(file_path)
        
    # 2. Create Job
    job = ScreeningJob(target_id=target_id, library_id=library_id, status="Running", created_by=current_user.email)
    await job.insert()
    
    # 3. Dispatch Task
    background_tasks.add_task(run_ai_screening_task, str(job.id), file_paths)
    
    return job

from fastapi.responses import Response
from app.utils.report_generator import generate_screening_pdf

@router.get("/{job_id}/report")
async def download_screening_report(job_id: str, user: User = Depends(get_current_user)):
    """
    Generate and download a PDF report for a screening job.
    """
    job = await ScreeningJob.get(job_id)
    if not job or job.status != "Completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    
    pdf_bytes = generate_screening_pdf(job.dict(), user)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Screening_Report_{job_id[:8]}.pdf"
        }
    )

@router.get("/", response_model=List[ScreeningJob])
async def get_screenings(current_user: User = Depends(get_current_user)):
    return await ScreeningJob.find(ScreeningJob.created_by == current_user.email).sort("-created_at").to_list()

