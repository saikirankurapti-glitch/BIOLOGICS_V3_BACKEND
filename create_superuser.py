import asyncio
import os
import sys

# Add current directory to path so we can import 'app'
sys.path.append(os.getcwd())

from app.db.engine import init_db
from app.models.user import User

async def create_admin():
    print("Initializing Database connection...")
    try:
        await init_db()
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    email = "admin@genesysquantis.com"
    password = "adminpassword123"
    # Using the simulation hashing from auth.py
    hashed = f"hashed_{password}"
    
    print(f"Checking for existing user: {email}")
    # Check if exists
    try:
        existing = await User.find_one(User.email == email)
        if existing:
            print(f"User {email} already exists. Resetting password.")
            existing.hashed_password = hashed
            existing.is_superuser = True
            await existing.save()
        else:
            print(f"Creating new user {email}")
            user = User(
                email=email,
                hashed_password=hashed,
                full_name="System Admin",
                is_superuser=True
            )
            await user.insert()
        
        print("\n" + "="*40)
        print("SUCCESS: Admin User Ready")
        print(f"Email:    {email}")
        print(f"Password: {password}")
        print("="*40 + "\n")
        
    except Exception as e:
        print(f"Error creating user: {e}")

if __name__ == "__main__":
    asyncio.run(create_admin())
