from fastapi import APIRouter, HTTPException, Depends, status
from app.models.user import User
from app.models.activity import UserActivity
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import json
import hmac
import hashlib
import base64
import time
import random
import resend
from datetime import datetime, timedelta
from app.config import settings

resend.api_key = settings.RESEND_API_KEY

router = APIRouter()
print("DEBUG: [auth.py] APIRouter initialized and routes defined")

SECRET_KEY = "super-secret-key-change-this"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = None
    is_superuser: bool = False # Allow creating admin for demo

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str = None
    is_active: bool
    is_superuser: bool

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str
    full_name: Optional[str] = None

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

def create_token(user_id: str, role: str):
    payload = {
        "sub": user_id,
        "role": role,
        "exp": time.time() + 3600 * 24  # 1 day
    }
    payload_str = json.dumps(payload)
    signature = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload_str}.{signature}".encode()).decode()
    return token

def verify_token(token: str):
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        payload_str, signature = decoded.split(".")
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        if signature != expected_sig:
            return None
        payload = json.loads(payload_str)
        if payload["exp"] < time.time():
            return None
        return payload
    except Exception:
        return None

from app.api.dependencies import get_current_active_superuser, get_current_user

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    existing_user = await User.find_one(User.email == user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Store plain for MVP demo (in real app use bcrypt)
    hashed_fake = f"hashed_{user.password}" 
    
    # Auto-promote specific admin email
    is_admin = user.is_superuser
    if user.email == "admin@genesysquantis.com":
        is_admin = True

    otp = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=5)
    print(f"🔑 [OTP GENERATED] User: {user.email} | OTP: {otp}")

    new_user = User(
        email=user.email, 
        hashed_password=hashed_fake, 
        full_name=user.full_name,
        is_superuser=is_admin,
        is_verified=False,
        otp=otp,
        otp_expiry=expiry
    )
    await new_user.insert()
    
    # Send OTP via Resend
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": user.email,
            "subject": "GenQuantis Verification Code",
            "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; color: #115e59;">
                    <h2>Welcome to GenQuantis!</h2>
                    <p>Please use the following OTP to verify your account:</p>
                    <div style="font-size: 2rem; font-weight: bold; padding: 10px; background: #f0fdfa; border-radius: 8px; text-align: center; color: #10b981;">
                        {otp}
                    </div>
                    <p>This code will expire in <strong>5 minutes</strong>.</p>
                </div>
            """
        })
    except Exception as e:
        print(f"RESEND ERROR: {e}")

    # Log activity
    await UserActivity(
        user_id=str(new_user.id), 
        user_email=new_user.email,
        action="REGISTER",
        details={"email": user.email}
    ).insert()
    
    return UserResponse(
        id=str(new_user.id), 
        email=new_user.email, 
        full_name=new_user.full_name, 
        is_active=new_user.is_active,
        is_superuser=new_user.is_superuser
    )

@router.post("/verify-otp")
async def verify_otp(data: OTPVerify):
    user = await User.find_one(User.email == data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Allow 111222 as master bypass code for developer testing
    if data.otp != "111222" and user.otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if data.otp != "111222":
        if datetime.utcnow() > user.otp_expiry:
            raise HTTPException(status_code=400, detail="OTP expired")
    
    user.is_verified = True
    user.otp = None
    user.otp_expiry = None
    await user.save()
    
    return {"message": "Email verified successfully"}

@router.post("/login", response_model=Token)
async def login(user_in: UserLogin):
    user = await User.find_one(User.email == user_in.email)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not user.is_verified:
        raise HTTPException(status_code=401, detail="Please verify your email first")
    
    # Verify fake hash
    if user.hashed_password != f"hashed_{user_in.password}":
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    role = "admin" if user.is_superuser else "user"
    token = create_token(str(user.id), role)
    
    # Log activity
    await UserActivity(
        user_id=str(user.id), 
        user_email=user.email,
        action="LOGIN",
        details={"role": role}
    ).insert()

    return Token(
        access_token=token, 
        token_type="bearer", 
        user_id=str(user.id), 
        role=role,
        full_name=user.full_name
    )

@router.get("/users", response_model=List[UserResponse])
async def get_users():
    users = await User.find_all().to_list()
    return [
        UserResponse(
            id=str(u.id), 
            email=u.email, 
            full_name=u.full_name, 
            is_active=u.is_active,
            is_superuser=u.is_superuser
        ) for u in users
    ]

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser
    )

@router.post("/profile", response_model=UserResponse)
async def update_user_me(user_update: UserUpdate, current_user: User = Depends(get_current_user)):
    print(f"DEBUG: [auth.py] update_user_me CALLED for user: {current_user.email}")
    
    # Ensure we are updating the latest instance from the database
    db_user = await User.get(current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.full_name is not None:
        print(f"DEBUG: Updating full_name from '{db_user.full_name}' to '{user_update.full_name}'")
        db_user.full_name = user_update.full_name
        
    if user_update.email is not None:
        if user_update.email != db_user.email:
            existing = await User.find_one(User.email == user_update.email)
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            print(f"DEBUG: Updating email from '{db_user.email}' to '{user_update.email}'")
            db_user.email = user_update.email
    
    await db_user.save()
    print(f"DEBUG: Profile successfully persisted to MongoDB for user {db_user.email}")
    
    return UserResponse(
        id=str(db_user.id),
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        is_superuser=db_user.is_superuser
    )
