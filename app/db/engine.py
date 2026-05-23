from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from app.models import User, Target, Experiment, ScreeningJob, OptimizationJob, UserActivity, DockingJob, ADMETJob, PreformulationReport, FormulationDesign

# Monkey-patch to bypass Beanie/Motor version telemetry incompatibility
AsyncIOMotorClient.append_metadata = lambda self, *args, **kwargs: None

async def init_db():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(database=client[settings.DATABASE_NAME], document_models=[
        User, Target, Experiment, ScreeningJob, OptimizationJob, 
        UserActivity, DockingJob, ADMETJob, PreformulationReport, FormulationDesign
    ])
    print(f"Connected to MongoDB at {settings.MONGODB_URL}")
