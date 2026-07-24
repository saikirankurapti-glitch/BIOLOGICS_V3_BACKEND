"""
GenQuantis Platform — DevOps Log Analytics API
===============================================
Provides endpoints for the DevOps team to:
  - View real-time log tails
  - Get aggregated user activity summaries
  - Check system health metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.user import User
from app.api.dependencies import get_current_active_superuser
from typing import Optional
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
import psutil

router = APIRouter()

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


@router.get("/logs/tail")
async def tail_logs(
    log_type: str = Query("access", description="Log type: access, errors, performance, system"),
    lines: int = Query(100, ge=1, le=1000, description="Number of recent lines to return"),
    user: User = Depends(get_current_active_superuser)
):
    """
    Returns the last N lines from a specific log file.
    Requires superuser privileges.
    """
    log_files = {
        "access": "platform_access.log",
        "errors": "platform_errors.log",
        "performance": "platform_performance.log",
        "system": "platform_system.log"
    }
    
    filename = log_files.get(log_type)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Invalid log_type. Choose from: {list(log_files.keys())}")
    
    filepath = os.path.join(LOG_DIR, filename)
    if not os.path.exists(filepath):
        return {"log_type": log_type, "lines": [], "message": "Log file not yet created. Waiting for first events."}
    
    with open(filepath, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    recent_lines = all_lines[-lines:]
    parsed = []
    for line in recent_lines:
        try:
            parsed.append(json.loads(line.strip()))
        except:
            parsed.append({"raw": line.strip()})
    
    return {
        "log_type": log_type,
        "total_entries": len(all_lines),
        "returned": len(parsed),
        "lines": parsed
    }


@router.get("/logs/user-activity")
async def user_activity_summary(
    hours: int = Query(24, ge=1, le=168, description="Look-back window in hours"),
    user: User = Depends(get_current_active_superuser)
):
    """
    Aggregates user activity from access logs.
    Shows: which users are active, what endpoints they hit, total time spent.
    """
    filepath = os.path.join(LOG_DIR, "platform_access.log")
    if not os.path.exists(filepath):
        return {"message": "No access logs yet.", "users": {}}
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    user_stats = defaultdict(lambda: {
        "total_requests": 0,
        "total_latency_ms": 0,
        "endpoints_visited": defaultdict(int),
        "errors": 0,
        "first_seen": None,
        "last_seen": None
    })
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", "")
                if not ts:
                    continue
                
                entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if entry_time.replace(tzinfo=None) < cutoff:
                    continue
                
                email = entry.get("user", "anonymous")
                stats = user_stats[email]
                stats["total_requests"] += 1
                stats["total_latency_ms"] += entry.get("latency_ms", 0)
                
                path = entry.get("path", "unknown")
                stats["endpoints_visited"][path] += 1
                
                if entry.get("status", 200) >= 400:
                    stats["errors"] += 1
                
                if not stats["first_seen"] or ts < stats["first_seen"]:
                    stats["first_seen"] = ts
                if not stats["last_seen"] or ts > stats["last_seen"]:
                    stats["last_seen"] = ts
                    
            except:
                continue
    
    # Convert to serializable format
    result = {}
    for email, stats in user_stats.items():
        avg_latency = round(stats["total_latency_ms"] / max(stats["total_requests"], 1), 2)
        
        # Estimate session duration from first/last request
        session_minutes = 0
        if stats["first_seen"] and stats["last_seen"]:
            try:
                first = datetime.fromisoformat(stats["first_seen"].replace("Z", "+00:00"))
                last = datetime.fromisoformat(stats["last_seen"].replace("Z", "+00:00"))
                session_minutes = round((last - first).total_seconds() / 60, 1)
            except:
                pass
        
        # Top 5 most visited endpoints
        top_endpoints = sorted(stats["endpoints_visited"].items(), key=lambda x: x[1], reverse=True)[:5]
        
        result[email] = {
            "total_requests": stats["total_requests"],
            "avg_latency_ms": avg_latency,
            "total_errors": stats["errors"],
            "estimated_session_minutes": session_minutes,
            "first_seen": stats["first_seen"],
            "last_seen": stats["last_seen"],
            "top_endpoints": dict(top_endpoints)
        }
    
    return {
        "window_hours": hours,
        "active_users": len(result),
        "users": result
    }


@router.get("/logs/performance-report")
async def performance_report(
    hours: int = Query(24, ge=1, le=168),
    user: User = Depends(get_current_active_superuser)
):
    """
    Generates a performance summary:
    - Slowest endpoints
    - Average response times by endpoint category
    - Compute job statistics (docking, screening, etc.)
    """
    filepath = os.path.join(LOG_DIR, "platform_access.log")
    if not os.path.exists(filepath):
        return {"message": "No logs yet."}
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    endpoint_stats = defaultdict(lambda: {"count": 0, "total_ms": 0, "max_ms": 0, "errors": 0})
    slow_requests = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", "")
                if not ts:
                    continue
                entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if entry_time.replace(tzinfo=None) < cutoff:
                    continue
                
                path = entry.get("path", "unknown")
                latency = entry.get("latency_ms", 0)
                status = entry.get("status", 200)
                
                # Categorize endpoint
                category = path.split("/")[2] if path.startswith("/api/") and len(path.split("/")) > 2 else path
                
                stats = endpoint_stats[category]
                stats["count"] += 1
                stats["total_ms"] += latency
                stats["max_ms"] = max(stats["max_ms"], latency)
                if status >= 400:
                    stats["errors"] += 1
                
                if latency > SLOW_REQUEST_THRESHOLD * 1000:
                    slow_requests.append({
                        "timestamp": ts,
                        "user": entry.get("user"),
                        "path": path,
                        "latency_ms": latency,
                        "status": status
                    })
            except:
                continue
    
    # Build summary
    summary = {}
    for cat, stats in endpoint_stats.items():
        summary[cat] = {
            "total_requests": stats["count"],
            "avg_latency_ms": round(stats["total_ms"] / max(stats["count"], 1), 2),
            "max_latency_ms": stats["max_ms"],
            "error_rate": round(stats["errors"] / max(stats["count"], 1) * 100, 1)
        }
    
    # Sort by avg latency descending
    sorted_summary = dict(sorted(summary.items(), key=lambda x: x[1]["avg_latency_ms"], reverse=True))
    
    return {
        "window_hours": hours,
        "endpoint_performance": sorted_summary,
        "slow_requests_count": len(slow_requests),
        "slowest_requests": sorted(slow_requests, key=lambda x: x["latency_ms"], reverse=True)[:20]
    }


@router.get("/logs/health")
async def system_health(user: User = Depends(get_current_active_superuser)):
    """Quick health check with log file sizes and last entries."""
    log_files = ["platform_access.log", "platform_errors.log", "platform_performance.log", "platform_system.log"]
    health = {}
    
    for lf in log_files:
        fp = os.path.join(LOG_DIR, lf)
        if os.path.exists(fp):
            size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)
            with open(fp, "r", encoding="utf-8") as f:
                lines = f.readlines()
            last_entry = None
            if lines:
                try:
                    last_entry = json.loads(lines[-1].strip())
                except:
                    last_entry = {"raw": lines[-1].strip()}
            
            health[lf] = {
                "size_mb": size_mb,
                "total_entries": len(lines),
                "last_entry": last_entry
            }
        else:
            health[lf] = {"status": "not_created_yet"}
    
    # System Resource Metrics
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    
    return {
        "log_directory": LOG_DIR,
        "files": health,
        "resources": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2)
        },
        "server_time_utc": datetime.utcnow().isoformat()
    }


@router.get("/logs/model-analytics")
async def model_analytics(
    hours: int = Query(24, ge=1, le=168),
    user: User = Depends(get_current_active_superuser)
):
    """
    Groups system performance by functional models (Docking, Screening, etc.)
    and calculates scientific/system metrics.
    """
    filepath = os.path.join(LOG_DIR, "platform_access.log")
    if not os.path.exists(filepath):
        return {"models": {}}
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    MODEL_MAPPING = {
        "/api/targets": "Target Discovery",
        "/api/pockets": "Pocket Explorer",
        "/api/screening": "AI Hit Screening",
        "/api/docking": "Molecular Docking",
        "/api/admet": "ADMET Predictor",
        "/api/optimization": "Lead Optimization",
        "/api/preformulation": "Preformulation",
        "/api/formulation": "Formulation Design"
    }
    
    model_stats = defaultdict(lambda: {
        "requests": 0,
        "success": 0,
        "total_latency": 0,
        "users": defaultdict(int),
        "max_latency": 0
    })
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp")
                if not ts: continue
                entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if entry_time.replace(tzinfo=None) < cutoff: continue
                
                path = entry.get("path", "")
                latency = entry.get("latency_ms", 0)
                status = entry.get("status_code", 200)
                user_email = entry.get("user", "anonymous")
                
                # Identify Model
                matched_model = "General API"
                for prefix, name in MODEL_MAPPING.items():
                    if path.startswith(prefix):
                        matched_model = name
                        break
                
                stats = model_stats[matched_model]
                stats["requests"] += 1
                stats["total_latency"] += latency
                stats["max_latency"] = max(stats["max_latency"], latency)
                stats["users"][user_email] += 1
                if 200 <= status < 400:
                    stats["success"] += 1
                    
            except: continue
            
    # Final aggregation
    results = []
    for name, stats in model_stats.items():
        avg_latency = round(stats["total_latency"] / max(stats["requests"], 1), 1)
        success_rate = round(stats["success"] / max(stats["requests"], 1) * 100, 1)
        # Find top user for this model
        top_user = "N/A"
        if stats["users"]:
            top_user = max(stats["users"].items(), key=lambda x: x[1])[0]
            
        results.append({
            "model_name": name,
            "requests": stats["requests"],
            "avg_latency_ms": avg_latency,
            "max_latency_ms": stats["max_latency"],
            "success_rate": success_rate,
            "top_user": top_user
        })
        
    return {
        "window_hours": hours,
        "models": sorted(results, key=lambda x: x["requests"], reverse=True)
    }

@router.get("/logs/db")
async def get_db_logs(
    user_email: Optional[str] = Query(None, description="Filter logs by user email"),
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_active_superuser)
):
    """
    Get raw access logs stored in MongoDB.
    Can filter by a specific user.
    """
    from app.models.log import AccessLog
    
    query = {}
    if user_email:
        query["user"] = user_email
        
    logs = await AccessLog.find(query).sort("-timestamp").limit(limit).to_list()
    return logs

# Import threshold
SLOW_REQUEST_THRESHOLD = 2.0
