import os
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.models.user import User
from app.models.transaction import TokenTransaction
from app.api.dependencies import get_current_user

router = APIRouter()

CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY")
CASHFREE_ENVIRONMENT = os.getenv("CASHFREE_ENVIRONMENT", "SANDBOX")

if CASHFREE_ENVIRONMENT == "PRODUCTION":
    CASHFREE_URL = "https://api.cashfree.com/pg/orders"
else:
    CASHFREE_URL = "https://sandbox.cashfree.com/pg/orders"

class CreateOrderRequest(BaseModel):
    package_name: str # "Starter Pack" or "Pro Pack"

class VerifyOrderRequest(BaseModel):
    order_id: str

PACKAGES = {
    "Starter Pack": {"amount": 999.00, "tokens": 1000, "currency": "USD"},
    "Pro Pack": {"amount": 4999.00, "tokens": 50000, "currency": "USD"}
}

@router.post("/create-order")
async def create_order(request: CreateOrderRequest, current_user: User = Depends(get_current_user)):
    if request.package_name not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package selected")

    package = PACKAGES[request.package_name]
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    customer_id = str(current_user.id)
    customer_email = current_user.email or "customer@example.com"
    customer_phone = "9999999999" # Cashfree requires phone number, placeholder for now

    headers = {
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": "2023-08-01",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "order_amount": package["amount"],
        "order_currency": package["currency"],
        "order_id": order_id,
        "customer_details": {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "customer_phone": customer_phone
        },
        "order_meta": {
            "return_url": "http://localhost:5000/billing.html?order_id={order_id}"
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(CASHFREE_URL, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            payment_session_id = data.get("payment_session_id")
            
            # Save pending transaction
            tx = TokenTransaction(
                user_id=str(current_user.id),
                user_email=current_user.email,
                amount=package["tokens"],
                module="Billing",
                description=f"Purchase {request.package_name}",
                order_id=order_id,
                payment_session_id=payment_session_id,
                status="PENDING",
                amount_paid=package["amount"],
                currency=package["currency"]
            )
            await tx.insert()

            return {"payment_session_id": payment_session_id, "order_id": order_id}

        except httpx.HTTPStatusError as e:
            print(f"Cashfree API Error: {e.response.text}")
            raise HTTPException(status_code=500, detail="Failed to create payment order")
        except Exception as e:
            print(f"Error creating order: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/verify")
async def verify_order(request: VerifyOrderRequest, current_user: User = Depends(get_current_user)):
    order_id = request.order_id
    
    headers = {
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": "2023-08-01",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    verify_url = f"{CASHFREE_URL}/{order_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(verify_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            order_status = data.get("order_status")
            
            tx = await TokenTransaction.find_one({"order_id": order_id})
            if not tx:
                raise HTTPException(status_code=404, detail="Transaction not found")
                
            if tx.status == "SUCCESS":
                return {"message": "Payment already verified", "status": "SUCCESS"}
                
            if order_status == "PAID":
                tx.status = "SUCCESS"
                await tx.save()
                
                # Add tokens to user
                current_tokens = getattr(current_user, 'tokens', 1000)
                current_user.tokens = current_tokens + tx.amount
                current_user.has_purchased = True
                await current_user.save()
                
                return {"message": "Payment successful", "status": "SUCCESS", "new_tokens": current_user.tokens}
            else:
                tx.status = "FAILED"
                await tx.save()
                return {"message": "Payment failed", "status": "FAILED"}
                
        except Exception as e:
            print(f"Error verifying order: {e}")
            raise HTTPException(status_code=500, detail="Failed to verify payment")
