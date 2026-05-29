import asyncio
from app.celery_app import celery_app
from app.models.docking import DockingJob
from app.db.engine import init_db
from datetime import datetime
import random

@celery_app.task(name="run_docking_task")
def run_docking_task(job_id: str):
    """
    Simulated long-running molecular docking simulation.
    """
    # Celery runs in a synchronous environment but we can use asyncio.run if needed,
    # or just keep it simple with synchronous calls to the DB if we use motor's sync wrapper.
    # However, Beanie is async. So we'll use a runner.
    
    async def _impl():
        await init_db()
        job = await DockingJob.get(job_id)
        if not job: return
        
        job.status = "Running"
        await job.save()
        
        # Simulate heavy compute
        await asyncio.sleep(15)
        
        job.status = "Completed"
        job.results = {
            "binding_energy": -7.2 - random.random() * 3,
            "best_pose_index": 0,
            "total_poses": 9,
            "runtime_seconds": 15.4,
            "software": "AutoDock Vina (Simulated)"
        }
        job.completed_at = datetime.now()
        await job.save()
        
    asyncio.run(_impl())
    return f"Docking Job {job_id} Completed"
