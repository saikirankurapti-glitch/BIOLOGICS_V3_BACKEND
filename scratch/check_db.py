import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

from app.db.engine import init_db
from app.models.screening import ScreeningJob

async def check():
    await init_db()
    count = await ScreeningJob.count()
    print(f"Jobs count: {count}")
    jobs = await ScreeningJob.find_all().to_list()
    for j in jobs:
        print(f"ID: {j.id}, Status: {j.status}, Target: {j.target_id}")

if __name__ == "__main__":
    asyncio.run(check())
