import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List

from app.models.target import Target
from app.models.user import User
from app.models.activity import UserActivity
from app.api.dependencies import get_current_user
from app.services.uniprot_service import fetch_uniprot_data
from app.services.alphafold_service import fetch_alphafold_metadata
from app.services.chembl_service import fetch_known_ligands

router = APIRouter()

class TargetCreate(BaseModel):
    name: str
    type: str
    sequence: str
    description: str = None

class TargetUpdate(BaseModel):
    name: str = None
    status: str = None
    properties: dict = None

@router.post("/", response_model=Target)
async def create_target(target: TargetCreate, user: User = Depends(get_current_user)):
    new_target = Target(**target.dict(), created_by=user.email)
    await new_target.insert()
    return new_target

@router.get("/", response_model=List[Target])
async def get_targets(search: str = None, user: User = Depends(get_current_user)):
    if search:
        # Case-insensitive search on name
        import re
        search_escaped = re.escape(search)
        targets = await Target.find({"name": {"$regex": search_escaped, "$options": "i"}}).to_list()
        
        # Log Search Activity
        await UserActivity(
            user_id=str(user.id),
            user_email=user.email,
            action="SEARCH_TARGET",
            details={"query": search}
        ).insert()
    else:
        targets = await Target.find_all().to_list()
    return targets

@router.get("/{target_id}", response_model=Target)
async def get_target(target_id: str):
    target = await Target.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target

@router.put("/{target_id}", response_model=Target)
async def update_target(target_id: str, update_data: TargetUpdate):
    target = await Target.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    # Update fields provided
    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(target, key, value)
    
    await target.save()
    return target

from app.services.pdb_service import fetch_pdb_metadata

@router.delete("/{target_id}")
async def delete_target(target_id: str):
    target = await Target.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    await target.delete()
    return {"message": "Target deleted successfully"}

@router.post("/import_pdb/{pdb_id}", response_model=Target)
async def import_pdb_target(pdb_id: str, user: User = Depends(get_current_user)):
    """
    Fetches metadata from RCSB PDB and creates a new Target.
    """
    metadata = fetch_pdb_metadata(pdb_id)
    if not metadata:
        raise HTTPException(status_code=500, detail="PDB API error or structure not available")
    
    if isinstance(metadata, dict) and metadata.get("error") == "NotFound":
        raise HTTPException(
            status_code=404, 
            detail=f"PDB ID '{pdb_id}' not found. Note: '{pdb_id}' may be a gene symbol; PDB requires 4-character structure IDs (e.g., 5CWZ)."
        )
    
    # Check if exists
    existing = await Target.find_one(Target.name == metadata["title"])
    if existing:
        return existing
        
    new_target = Target(
        name=metadata["title"],
        type="Protein Structure",
        sequence=f"PDB:{metadata['pdb_id']}", # Placeholder for actual seq
        description=f"Imported from PDB: {metadata['pdb_id']} | Method: {metadata['experiment_method']}",
        properties=metadata,
        pdb_ids=[metadata['pdb_id']],
        created_by=user.email
    )
    await new_target.insert()
    return new_target

@router.post("/discover/{uniprot_id}", response_model=Target)
async def discover_target(uniprot_id: str, user: User = Depends(get_current_user)):
    """
    Implements the full Target Discovery Workflow:
    1. Auto-detect if input is a PDB ID (4-char alphanumeric) → import from PDB
    2. Otherwise, treat as gene name / UniProt ID:
       a. Fetch sequence from UniProt
       b. Retrieve 3D structure from PDB
       c. If unavailable -> fetch AlphaFold prediction
       d. Fetch known binders from ChEMBL
    """
    import re
    safe_id = uniprot_id.strip().upper()
    
    # --- Auto-detect PDB ID (exactly 4 alphanumeric characters, starts with a digit) ---
    if re.match(r'^[0-9][A-Z0-9]{3}$', safe_id):
        # Route to PDB import logic
        metadata = fetch_pdb_metadata(safe_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"PDB ID '{safe_id}' not found or PDB API error.")
        if isinstance(metadata, dict) and metadata.get("error") == "NotFound":
            raise HTTPException(status_code=404, detail=f"PDB ID '{safe_id}' not found in RCSB PDB.")
        
        existing = await Target.find_one(Target.name == metadata["title"])
        if existing:
            return existing
        
        new_target = Target(
            name=metadata["title"],
            type="Protein Structure",
            sequence=f"PDB:{metadata['pdb_id']}",
            description=f"Imported from PDB: {metadata['pdb_id']} | Method: {metadata['experiment_method']}",
            properties=metadata,
            pdb_ids=[metadata['pdb_id']],
            status="Discovered",
            created_by=user.email
        )
        await new_target.insert()
        return new_target
    
    # --- Otherwise: UniProt / Gene Name discovery ---
    # 1. Fetch UniProt Core Data
    uniprot_data = await fetch_uniprot_data(safe_id)
    if not uniprot_data:
        raise HTTPException(status_code=404, detail=f"Target '{safe_id}' not found. Try a gene name (e.g. GPR35), UniProt ID (e.g. Q9Y5Y4), or PDB ID (e.g. 6D9H).")
    
    # 2. Update safe_id to resolved UniProt Accession (e.g. Q9Y5Y4 instead of GPR35)
    # This is critical for subsequent AlphaFold/ChEMBL API calls
    safe_id = uniprot_data.get("uniprot_id", safe_id)
    pdb_ids = uniprot_data.get("pdb_ids", [])
    
    # Check if Target already exists
    existing = await Target.find_one(Target.uniprot_id == safe_id)
    target = existing if existing else Target(
        name=uniprot_data.get("name", safe_id),
        type="Protein",
        uniprot_id=safe_id,
        sequence=uniprot_data.get("sequence", ""),
        description=f"Gene: {uniprot_data.get('gene_name')} | Organism: {uniprot_data.get('organism')}",
        pdb_ids=pdb_ids,
        properties=uniprot_data,
        created_by=user.email
    )

    # 3. Handle AlphaFold Fallback if no PDBs exist
    if not target.pdb_ids:
        af_metadata = await fetch_alphafold_metadata(safe_id)
        if af_metadata and af_metadata.get("pdbUrl"):
            target.alphafold_url = af_metadata["pdbUrl"]
            target.properties["structural_source"] = "AlphaFold Prediction"
    else:
        target.properties["structural_source"] = "PDB Crystal Structure"
            
    # 5. Fetch Known Binders from ChEMBL (Run concurrently if possible, but we'll await here)
    if not target.known_ligands:
        ligands = await fetch_known_ligands(safe_id, limit=50) # Fetch top 50
        target.known_ligands = ligands
        
    # 6. Fetch Protein-Protein Interaction (PPI) Partners (Mocked BioGRID/STRING lookup)
    if not target.interaction_partners:
        import random
        ppi_data = [
            {"symbol": "TP53", "score": 0.98, "type": "Physical Interaction", "method": "AP-MS"},
            {"symbol": "MDM2", "score": 0.95, "type": "Regulatory Binding", "method": "Y2H"},
            {"symbol": "ATM", "score": 0.88, "type": "Phosphorylation", "method": "Biochemical Assay"},
            {"symbol": "KAT5", "score": 0.72, "type": "Structural Complex", "method": "AlphaFold-Multimer"}
        ]
        target.interaction_partners = ppi_data

    target.status = "Discovered"

    if existing:
        # Don't overwrite created_by if it already exists
        if not target.created_by:
            target.created_by = user.email
        await target.save()
    else:
        await target.insert()
        
    return target

from fastapi.responses import Response
from app.utils.report_generator import generate_target_report
import os
import uuid
from datetime import datetime
from app.models.registry import ReportRegistry

@router.get("/{target_id}/report")
async def download_target_report(target_id: str, user: User = Depends(get_current_user)):
    """
    Generate and download a PDF report for a therapeutic target.
    """
    target = await Target.find_one(Target.uniprot_id == target_id)
    if not target:
        # Try ID if UniProt fails
        try:
            from bson import ObjectId
            target = await Target.get(ObjectId(target_id))
        except:
            target = None
        
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    pdf_bytes = generate_target_report(target.dict(), user)
    
    # Save to registry
    os.makedirs("./registry_files", exist_ok=True)
    filename = f"Target_Report_{target_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = os.path.join("./registry_files", filename)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
        
    existing = await ReportRegistry.find_one(
        ReportRegistry.user_email == user.email,
        ReportRegistry.target_id == str(target.id)
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
            target_id=str(target.id),
            target_name=target.name,
            report_type="Target Intelligence",
            file_path=file_path
        )
        await new_report.insert()
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Target_Report_{target_id}.pdf"
        }
    )
