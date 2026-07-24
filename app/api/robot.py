from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import os

router = APIRouter()

class ProtocolRequest(BaseModel):
    ligands: List[str] # SMILES or IDs
    target_id: str
    plate_type: str = "96-well"
    experiment_type: str = "IC50_Mapping"

@router.post("/generate")
async def generate_protocol(request: ProtocolRequest):
    """
    Generates an Opentrons OT-2 executable Python script.
    """
    protocol_template = f"""
from opentrons import protocol_api

metadata = {{
    'protocolName': 'Biologics Discovery Validation - {request.experiment_type}',
    'author': 'BioAssist AI',
    'description': 'Automated assay for target {request.target_id}',
    'apiLevel': '2.13'
}}

def run(protocol: protocol_api.ProtocolContext):
    # Labware
    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', '1')
    tiprack = protocol.load_labware('opentrons_96_tiprack_300ul', '2')
    
    # Pipettes
    p300 = protocol.load_instrument('p300_single', 'right', tip_racks=[tiprack])
    
    # Logic for {len(request.ligands)} compounds
    protocol.comment("Starting automated validation for {request.target_id}")
    
    for i in range({len(request.ligands)}):
        protocol.comment(f"Processing Compound {{i+1}}")
        p300.pick_up_tip()
        p300.transfer(50, plate['A1'], plate.wells()[i], new_tip='never')
        p300.drop_tip()

    protocol.comment("Protocol Complete.")
"""
    return {
        "protocol_id": "PROTO_" + os.urandom(4).hex(),
        "script": protocol_template,
        "filename": f"opentrons_{request.target_id}_protocol.py",
        "supported_robot": "OT-2 / OT-3"
    }
