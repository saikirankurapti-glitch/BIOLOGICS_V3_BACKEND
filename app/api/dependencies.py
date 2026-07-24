from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from app.models.user import User
# import jwt - Removed unused import
import hmac
import hashlib
import json
import base64
import time
from datetime import datetime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

SECRET_KEY = "super-secret-key-change-this"

def verify_token_manual(token: str):
    try:
        # Add padding if missing
        padding = 4 - (len(token) % 4)
        if padding < 4:
            token += "=" * padding
            
        decoded = base64.urlsafe_b64decode(token).decode()
        payload_str, signature = decoded.rsplit(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        if signature != expected_sig:
            print(f"Signature mismatch! Expected {expected_sig}, got {signature}")
            return None
        payload = json.loads(payload_str)
        if payload["exp"] < time.time():
            print(f"Token expired! Exp: {payload['exp']}, Now: {time.time()}")
            return None
        return payload
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = verify_token_manual(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await User.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_user_optional(token: str = Depends(oauth2_scheme)) -> Optional[User]:
    try:
        payload = verify_token_manual(token)
        if not payload: return None
        return await User.get(payload["sub"])
    except Exception:
        return None

async def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user

def require_tokens(cost: int, module_name: str = "Unknown"):
    async def token_dependency(current_user: User = Depends(get_current_user)) -> User:
        # Check trial expiry
        if current_user.is_trial_active and current_user.trial_ends_at and current_user.trial_ends_at < datetime.utcnow():
            current_user.is_trial_active = False
            # If they never purchased tokens, wipe the free tokens upon trial expiry
            if not getattr(current_user, 'has_purchased', False):
                current_user.tokens = 0
            await current_user.save()

        if current_user.is_superuser:
            return current_user

        if current_user.tokens < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Payment Required: Insufficient tokens for {module_name}. Need {cost} tokens."
            )
        
        current_user.tokens -= cost
        await current_user.save()

        # Log transaction
        from app.models.transaction import TokenTransaction
        await TokenTransaction(
            user_id=str(current_user.id),
            amount=-cost,
            module=module_name,
            description=f"Consumed {cost} tokens for {module_name}"
        ).insert()

        return current_user
    return token_dependency
