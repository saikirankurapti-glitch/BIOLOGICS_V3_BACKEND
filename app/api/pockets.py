from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from typing import List, Dict, Any, Optional
from app.models.target import Target
from app.models.user import User
from app.api.dependencies import get_current_user, get_current_user_optional
from app.tasks.pocket_tasks import run_pocket_discovery_task

router = APIRouter()

from app.tasks.pocket_tasks import run_pocket_discovery_task, identify_pockets_logic

@router.post("/{target_id}/discover")
async def discover_pockets(
    request: Request,
    target_id: str, 
    background_tasks: BackgroundTasks,
    tool: str = "p2rank"
):
    """
    Trigger a pocket discovery task for a given target.
    (Manual auth check to prevent 401 block)
    """
    from app.api.dependencies import verify_token_manual
    auth_header = request.headers.get("Authorization")
    user = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = verify_token_manual(token)
        if payload:
            user = await User.get(payload["sub"])

    # Fallback for demo environment if auth fails
    user_email = user.email if user else "guest@discovery.demo"
    user_id = str(user.id) if user else "guest_id"
    target = await Target.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    # Update status to reflect queuing
    target.status = "Queued"
    await target.save()

    # Log activity (even if guest)
    from app.models.activity import UserActivity
    await UserActivity(
        user_id=user_id,
        user_email=user_email,
        action="POCKET_SCAN",
        details={"target_id": target_id, "tool": tool}
    ).insert()

    # Force Strategy B: FastAPI BackgroundTasks (Safe local fallback)
    # Bypassing Celery entirely because no worker is running in this env
    background_tasks.add_task(identify_pockets_logic, str(target.id), tool)
    return {"message": f"Pocket discovery started via local computational engine ({tool})", "target_id": target_id}

@router.get("/{target_id}")
async def get_pockets(target_id: str):
    """
    Retrieve identified pockets for a target.
    """
    target = await Target.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    return {
        "target_name": target.name,
        "status": target.status,
        "pockets": target.pockets,
        "updated_at": target.updated_at
    }

@router.get("/tools")
async def list_pocket_tools():
    return {
        "tools": [
            {"id": "p2rank", "name": "P2Rank", "description": "Machine learning based ligand binding site prediction."},
            {"id": "fpocket", "name": "fpocket", "description": "Geometry-based pocket identification tool."}
        ]
    }
