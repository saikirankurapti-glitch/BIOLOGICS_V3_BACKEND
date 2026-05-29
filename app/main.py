import os
import webbrowser
import threading
import time
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
print("DEBUG: MAIN.PY STARTED", flush=True)

# ── Initialize Logging FIRST (before anything else) ─────────────────
from app.logging_config import setup_logging
setup_logging()
system_logger = logging.getLogger("genquantis.system")

app = FastAPI(
    title="GenQuantis Discovery API",
    description="Backend API for AI-assisted biologics discovery, screening, and validation.",
    version="0.1.0"
)
print("DEBUG: FASTAPI APP CREATED", flush=True)

@app.post("/sync-profile")
async def sync_profile(request: Request):
    data = await request.json()
    full_name = data.get("full_name", "Researcher")
    email = data.get("email", "unknown@zerokost.com")
    
    # Return valid JSON structure that matches UserResponse
    return {
        "id": "6a0166abfde087badfa2dfd3", # Mock ID for sync
        "full_name": full_name,
        "email": email,
        "is_active": True,
        "is_superuser": True
    }
print("DEBUG: [main.py] Starting sequential router imports...", flush=True)

# 1. Auth Router
print("DEBUG: [main.py] Importing auth router...", flush=True)
from app.api import auth
print("DEBUG: [main.py] Including auth router...", flush=True)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

# 2. Targets Router
print("DEBUG: [main.py] Importing targets router...", flush=True)
from app.api import targets
print("DEBUG: [main.py] Including targets router...", flush=True)
app.include_router(targets.router, prefix="/api/targets", tags=["Targets"])

# 3. Experiments Router
print("DEBUG: [main.py] Importing experiments router...", flush=True)
from app.api import experiments
print("DEBUG: [main.py] Including experiments router...", flush=True)
app.include_router(experiments.router, prefix="/api/experiments", tags=["Experiments"])

# 4. Screening Router
print("DEBUG: [main.py] Importing screening router...", flush=True)
from app.api import screening
print("DEBUG: [main.py] Including screening router...", flush=True)
app.include_router(screening.router, prefix="/api/screening", tags=["Screening"])

# 5. Optimization Router
print("DEBUG: [main.py] Importing optimization router...", flush=True)
from app.api import optimization
print("DEBUG: [main.py] Including optimization router...", flush=True)
app.include_router(optimization.router, prefix="/api/optimization", tags=["Optimization"])

# 6. Docking Router
print("DEBUG: [main.py] Importing docking router...", flush=True)
from app.api import docking
print("DEBUG: [main.py] Including docking router...", flush=True)
app.include_router(docking.router, prefix="/api/docking", tags=["Docking"])

# 7. ADMET Router
print("DEBUG: [main.py] Importing admet router...", flush=True)
from app.api import admet
print("DEBUG: [main.py] Including admet router...", flush=True)
app.include_router(admet.router, prefix="/api/admet", tags=["ADMET"])

# 8. Robot Router
print("DEBUG: [main.py] Importing robot router...", flush=True)
from app.api import robot
print("DEBUG: [main.py] Including robot router...", flush=True)
app.include_router(robot.router, prefix="/api/robot", tags=["Robot"])

# 9. Admin Router
print("DEBUG: [main.py] Importing admin router...", flush=True)
from app.api import admin
print("DEBUG: [main.py] Including admin router...", flush=True)
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# 10. Chatbot Router
print("DEBUG: [main.py] Importing chatbot router...", flush=True)
from app.api import chatbot
print("DEBUG: [main.py] Including chatbot router...", flush=True)
app.include_router(chatbot.router, prefix="/api/chat", tags=["Chatbot"])

# 11. Reports Router
print("DEBUG: [main.py] Importing reports router...", flush=True)
from app.api import reports
print("DEBUG: [main.py] Including reports router...", flush=True)
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])

# 12. Monitoring Router
print("DEBUG: [main.py] Importing monitoring router...", flush=True)
from app.api import monitoring
print("DEBUG: [main.py] Including monitoring router...", flush=True)
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])

# 13. Preformulation Router
print("DEBUG: [main.py] Importing preformulation router...", flush=True)
from app.api import preformulation
print("DEBUG: [main.py] Including preformulation router...", flush=True)
app.include_router(preformulation.router, prefix="/api/preformulation", tags=["Preformulation"])

# 14. Formulation Router
print("DEBUG: [main.py] Importing formulation router...", flush=True)
from app.api import formulation
print("DEBUG: [main.py] Including formulation router...", flush=True)
app.include_router(formulation.router, prefix="/api/formulation", tags=["Formulation"])

# 15. Pockets Router
print("DEBUG: [main.py] Importing pockets router...", flush=True)
from app.api import pockets
print("DEBUG: [main.py] Including pockets router...", flush=True)
app.include_router(pockets.router, prefix="/api/pockets", tags=["Pockets"])

# 16. Logs Router
print("DEBUG: [main.py] Importing logs router...", flush=True)
from app.api import logs
print("DEBUG: [main.py] Including logs router...", flush=True)
app.include_router(logs.router, prefix="/api/devops", tags=["DevOps Logs"])

print("DEBUG: [main.py] All routers imported and included successfully.", flush=True)

# CORS Configuration
import os

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000", 
    "http://localhost:8080", 
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://black-sky-0e9160600.7.azurestaticapps.net",
    "https://www.genesysquantis.com",
]

env_origins = os.environ.get("ALLOWED_ORIGINS")
if env_origins:
    for origin in env_origins.split(","):
        cleaned = origin.strip()
        if cleaned and cleaned not in origins:
            origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Logging Middleware (after CORS) ──────────────────────────
from app.middleware.logging_middleware import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# Configure Paths robustly to handle various local and cloud deployment folder layouts
possible_roots = [
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), # parallel to backend
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), # nested inside backend
    os.path.dirname(os.path.abspath(__file__)) # next to main.py
]

FRONTEND_DIR = None
for r in possible_roots:
    potential_path = os.path.join(r, "frontend")
    if os.path.exists(potential_path):
        FRONTEND_DIR = potential_path
        break

if not FRONTEND_DIR:
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend_fallback")

TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

# Ensure target directories exist to prevent StaticFiles from throwing a startup RuntimeError
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def open_browser():
    """Opens the browser to the landing page after a short delay."""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")
print("DEBUG: IMPORTING DB ENGINE", flush=True)
from app.db.engine import init_db
print("DEBUG: DB ENGINE IMPORTED", flush=True)
@app.on_event("startup")
async def start_db():
    print("DEBUG: STARTUP EVENT RUNNING", flush=True)
    system_logger.info("🚀 GenQuantis Platform Starting Up...", extra={
        "extra_data": {"event": "APP_STARTUP", "version": "0.1.0"}
    })
    
    db_connected = False
    try:
        print("DEBUG: BEFORE INIT_DB", flush=True)
        await init_db()
        system_logger.info("✅ Database Connected", extra={
            "extra_data": {"event": "DB_CONNECTED"}
        })
        print("DEBUG: AFTER INIT_DB", flush=True)
        db_connected = True
    except Exception as e:
        system_logger.critical(f"❌ Database Connection Failed: {e}", exc_info=True, extra={
            "extra_data": {"event": "DB_CONNECTION_FAILED"}
        })
        print(f"DEBUG: DATABASE CONNECTION FAILED: {e}", flush=True)
        
    if db_connected:
        try:
            # Init Admin
            from app.models.user import User
            email = "admin@genesysquantis.com"
            existing = await User.find_one(User.email == email)
            if not existing:
                print(f"Creating default admin: {email}", flush=True)
                await User(
                    email=email,
                    hashed_password=f"hashed_admin", # Matches auth.py logic
                    full_name="System Admin",
                    is_superuser=True,
                    is_active=True,
                    is_verified=True
                ).insert()
            else:
                updated = False
                if not existing.is_verified:
                    existing.is_verified = True
                    updated = True
                if not existing.is_superuser:
                    existing.is_superuser = True
                    updated = True
                if updated:
                    print(f"Ensuring default admin is verified and superuser: {email}", flush=True)
                    await existing.save()
        except Exception as e:
            system_logger.error(f"❌ Default admin initialization failed: {e}", exc_info=True)
            print(f"DEBUG: ADMIN INITIALIZATION FAILED: {e}", flush=True)
    
    # Automatically open browser if not disabled
    # if os.environ.get("AUTO_OPEN_BROWSER", "true").lower() == "true":
    #     # Only open if this is the main worker (not the reloader process window)
    #     # Uvicorn reload works by starting a main process and then a worker process.
    #     # This will still trigger on reloads, which is what the user asked for.
    #     threading.Thread(target=open_browser, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the login page by default."""
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/{page}.html", response_class=HTMLResponse)
async def serve_html_page(request: Request, page: str):
    """Serve other HTML templates by name."""
    try:
        return templates.TemplateResponse(request=request, name=f"{page}.html")
    except Exception:
        return HTMLResponse(content="Page not found", status_code=404)

@app.get("/api/status")
def read_root_api():
    return {"message": "Biologics Discovery Platform API is running", "version": "0.1.0"}

@app.post("/api/auth/profile")
async def update_profile_direct():
    return {"message": "Direct sync successful"}

# ... existing code ...



from fastapi import WebSocket, WebSocketDisconnect
from app.utils.websockets import manager

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket, job_id)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)

