import asyncio
import os
import random
import subprocess
from datetime import datetime
from app.celery_app import celery_app
from app.models.target import Target
from app.db.engine import init_db

from app.services.pocket_discovery_service import PocketDiscoveryService

async def identify_pockets_logic(target_id: str, tool: str = "p2rank"):
    """
    Core async logic for pocket identification.
    Safe to call directly from FastAPI BackgroundTasks.
    """
    await init_db()
    
    target = await Target.get(target_id)
    if not target:
        print(f"Target {target_id} not found in database.")
        return
    
    target.status = f"Discovering Pockets ({tool})"
    await target.save()
    
    # Real/Simulated integration point
    # Structures are saved as <TARGET_NAME>.pdb (e.g. 5FR9.pdb) 
    # NOT by their mongodb primary key.
    pdb_path = f"structures/{target.name}.pdb"
    pockets = PocketDiscoveryService.identify_pockets(pdb_path, tool)
    
    # Simulate compute time
    await asyncio.sleep(2)
    
    target.pockets = pockets
    target.status = "Pockets Identified"
    target.updated_at = datetime.now()
    await target.save()
    
    print(f"Pocket identification complete for target {target.name} using {tool}")
    return f"Pocket Discovery for {target_id} Completed"

@celery_app.task(name="run_pocket_discovery_task")
def run_pocket_discovery_task(target_id: str, tool: str = "p2rank"):
    """
    Celery wrapper for the pocket identification logic.
    """
    return asyncio.run(identify_pockets_logic(target_id, tool))
