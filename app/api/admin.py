from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models.user import User
from app.models.activity import UserActivity
from app.models.activity import UserActivity
from pydantic import BaseModel, EmailStr

class AddTokensRequest(BaseModel):
    amount: int

from app.api.dependencies import get_current_active_superuser

router = APIRouter(dependencies=[Depends(get_current_active_superuser)])

class AdminStats(BaseModel):
    total_users: int
    total_activities: int
    active_users: int

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats():
    total_users = await User.count()
    total_activities = await UserActivity.count()
    active_users = await User.find(User.is_active == True).count()
    return AdminStats(total_users=total_users, total_activities=total_activities, active_users=active_users)

    return AdminStats(total_users=total_users, total_activities=total_activities, active_users=active_users)

class AdminUserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str = None
    is_active: bool
    is_superuser: bool
    tokens: int

@router.get("/users", response_model=List[AdminUserResponse])
async def get_all_users():
    users = await User.find_all().to_list()
    return [
        AdminUserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name or "",
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            tokens=getattr(u, 'tokens', 1000)
        ) for u in users
    ]

@router.get("/users/{user_id}/activity")
async def get_user_activity(user_id: str):
    activities = await UserActivity.find(UserActivity.user_id == user_id).sort("-timestamp").to_list()
    return activities

@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await user.delete()
    return {"message": "User deleted"}

@router.post("/users/{user_id}/add-tokens")
async def add_tokens(user_id: str, request: AddTokensRequest):
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_tokens = getattr(user, 'tokens', None)
    if current_tokens is None:
        current_tokens = 1000
    user.tokens = current_tokens + request.amount
    user.has_purchased = True
    await user.save()

    # Log activity
    await UserActivity(
        user_id=str(user.id),
        user_email=user.email,
        action="ADD_TOKENS",
        details={"amount": request.amount, "new_balance": user.tokens}
    ).insert()

    return {"message": f"Successfully added {request.amount} tokens to {user.email}", "new_balance": user.tokens}

from app.models.transaction import TokenTransaction

@router.get("/transactions")
async def get_all_transactions():
    transactions = await TokenTransaction.find_all().sort("-timestamp").to_list()
    return transactions
