from fastapi import FastAPI, Query
from typing import Optional
from datetime import datetime
from database import get_db

app = FastAPI()

db = get_db()
collection = db["stocks"]

@app.get("/")
def read_root():
    return {"message": "API for stocks"}

@app.get("/stocks")
def get_stocks(page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    skip = (page - 1) * count
    if collection is not None:
        stocks = list(collection.find({}, {"_id": 0}).skip(skip).limit(count))
        return {"stocks": stocks, "page": page, "count": count}
    else:
        return {"error": "No hay stocks disponibles."}


@app.get("/stocks/{symbol}")
def get_stock_detail(symbol: str, price: Optional[float] = None, quantity: Optional[int] = None, date: Optional[str] = None, page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    skip = (page - 1) * count
    query = {"symbol": symbol}
    
    if price:
        query["price"] = {"$lt": price}
    if quantity:
        query["quantity"] = {"$lte": quantity}
    if date:
        try:
            date_obj = datetime.fromisoformat(date)
            start = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
            end = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
            query["timestamp"] = {"$gte": start, "$lte": end}
        except ValueError:
            return {"error": "Fecha debe tener el formato 'YYYY-MM-DD'"}

    stocks = list(collection.find(query, {"_id": 0}).skip(skip).limit(count))
    
    if stocks:
        return {"symbol": symbol, "stock": stocks, "page": page, "count": count}
    else:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}