# app/api/routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, constr, conint
from buy_requests.buy_requests import mqtt_manager

router = APIRouter(prefix="", tags=["Buy"])

class BuyStockRequest(BaseModel):
    symbol: str
    quantity: int

class BuyStockResponse(BaseModel):
    request_id: str

@router.post("/buy", response_model=BuyStockResponse)
async def buy_stock(req: BuyStockRequest):
    """
    Recibe del frontend { symbol, quantity },
    publica en stocks/requests y devuelve el request_id.
    """
    try:
        request_id = mqtt_manager.publish_buy_request(req.symbol, req.quantity)
        return BuyStockResponse(request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
