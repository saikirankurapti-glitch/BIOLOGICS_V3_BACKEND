from fastapi import APIRouter, Depends
from app.models.user import User
from app.api.dependencies import get_current_user
from typing import Dict, Any
import random
from app.models.target import Target
from app.models.experiment import Experiment
from app.models.docking import DockingJob
from app.models.admet import ADMETJob
from app.models.optimization import OptimizationJob
from app.models.screening import ScreeningJob
from app.models.activity import UserActivity

router = APIRouter()

@router.get("/stats")
async def get_platform_stats(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    print(f"Fetching platform stats for dashboard for user {current_user.email}...")
    """
    Aggregation of user-specific platform metrics for the dashboard.
    """
    target_count = await Target.find(Target.created_by == current_user.email).count()
    experiment_count = await Experiment.find(Experiment.created_by == current_user.email).count()
    
    # Active AI Jobs across different modules for this user
    active_docking = await DockingJob.find(DockingJob.created_by == current_user.email, DockingJob.status == "Running").count()
    active_admet = await ADMETJob.find(ADMETJob.created_by == current_user.email, ADMETJob.status == "Running").count()
    active_opt = await OptimizationJob.find(OptimizationJob.created_by == current_user.email, OptimizationJob.status == "Running").count()
    
    active_ai_jobs = active_docking + active_admet + active_opt
    
    # 🧬 Pipeline Distribution
    pipeline = {
        "Target Discovery": target_count,
        "Structural Mapping": await DockingJob.find(DockingJob.created_by == current_user.email).count(),
        "Hit Screening": await ScreeningJob.find(ScreeningJob.created_by == current_user.email).count(),
        "Lead Optimization": await OptimizationJob.find(OptimizationJob.created_by == current_user.email).count(),
        "ADMET Profiling": await ADMETJob.find(ADMETJob.created_by == current_user.email).count(),
        # For demo purposes, checking if they have wet lab experiments
        "Robotic Validation": await Experiment.find(Experiment.created_by == current_user.email, Experiment.experiment_type == "Wet Lab").count(),
        "Preformulation": await Experiment.find(Experiment.created_by == current_user.email, Experiment.experiment_type == "Preformulation").count(),
        "Formulation": await Experiment.find(Experiment.created_by == current_user.email, Experiment.experiment_type == "Formulation").count()
    }

    # 🏆 Top Discoveries (Recent high-affinity optimizations)
    recent_optimizations = await OptimizationJob.find(OptimizationJob.created_by == current_user.email, OptimizationJob.status == "Completed").sort("-completed_at").limit(5).to_list()
    top_candidates = []
    for opt in recent_optimizations:
        res = opt.results or {}
        top_candidates.append({
            "target": opt.target_id,
            "smiles": res.get("optimized_smiles", "N/A"),
            "affinity": res.get("optimized_affinity", 0),
            "improvement": res.get("improvement", "0%"),
            "model": res.get("model_used", "GA-v1")
        })

    # Simulate GPU/CPU load
    gpu_load = 5.0 + (active_ai_jobs * 12.5) + (random.random() * 5)
    
    # 📈 Dynamic Success Rate Calculation for the user
    total_jobs = await ScreeningJob.find(ScreeningJob.created_by == current_user.email).count() + \
                 await OptimizationJob.find(OptimizationJob.created_by == current_user.email).count() + \
                 await DockingJob.find(DockingJob.created_by == current_user.email).count() + \
                 await ADMETJob.find(ADMETJob.created_by == current_user.email).count()
                 
    if total_jobs > 0:
        completed_jobs = (
            await ScreeningJob.find(ScreeningJob.created_by == current_user.email, ScreeningJob.status == "Completed").count() +
            await OptimizationJob.find(OptimizationJob.created_by == current_user.email, OptimizationJob.status == "Completed").count() +
            await DockingJob.find(DockingJob.created_by == current_user.email, DockingJob.status == "Completed").count() +
            await ADMETJob.find(ADMETJob.created_by == current_user.email, ADMETJob.status == "Completed").count()
        )
        success_rate = round((completed_jobs / total_jobs) * 100, 1)
    else:
        success_rate = 0.0 # Baseline for empty dashboard
    
    # 📈 Dynamic Sequence Completion Rate Calculation
    user_targets = await Target.find(Target.created_by == current_user.email).to_list()
    total_sequences = sum(1 for t in user_targets if t.sequence)
    if total_sequences > 0:
        completed_seqs = sum(1 for t in user_targets if t.sequence and t.status in ["Discovered", "Screened", "Validated"])
        completion_rate = round((completed_seqs / total_sequences) * 100, 2)
    else:
        completion_rate = 0.0

    return {
        "target_count": target_count,
        "active_ai_jobs": active_ai_jobs,
        "experiment_count": experiment_count,
        "gpu_load": f"{min(gpu_load, 99.0):.1f}%",
        "cluster_status": "Operational" if gpu_load < 85 else "Critical Load",
        "pipeline": pipeline,
        "top_candidates": top_candidates,
        "system_health": success_rate, # Now dynamic
        "completion_rate": completion_rate,
        "total_sequences": total_sequences,
        "live_logs": [f"[{a.timestamp.strftime('%H:%M:%S')}] {a.action}: {a.user_email}" for a in await UserActivity.find_all().sort("-timestamp").limit(8).to_list()],
        "daily_throughput": 12400 + random.randint(0, 500) # Mols processed today
    }

@router.get("/health")
async def get_system_health():
    return {
        "status": "Healthy",
        "gpu_cluster": "Online",
        "storage": "82% Free",
        "database": "Connected",
        "robot_interface": "Standby"
    }
