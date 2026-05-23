from typing import Optional
from beanie import Document
from pydantic import EmailStr
from datetime import datetime

class User(Document):
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    otp: Optional[str] = None
    otp_expiry: Optional[datetime] = None
    created_at: datetime = datetime.now()

    class Settings:
        name = "users"
