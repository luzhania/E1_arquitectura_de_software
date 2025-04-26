from fastapi import FastAPI, Query
from typing import Optional
from datetime import datetime
from database import get_db
from buy_requests.buy_requests import mqtt_manager 
from routes import router

app = FastAPI()
app.include_router(router)


db = get_db()
collection = db["current_stocks"]
users_collection = db["users"]
transactions_collection = db["transactions"]


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
def get_stock_detail(symbol: str, price: Optional[float] = None, quantity: Optional[int] = None, date: Optional[str] = None, longName: Optional[str] = None,shortName: Optional[str] = None, page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
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
    if longName:
        query["longName"] = {"$regex": longName, "$options": "i"} 
    if shortName:
        query["shortName"] = {"$regex": shortName, "$options": "i"}

    stocks = list(collection.find(query, {"_id": 0}).skip(skip).limit(count))
    
    if stocks:
        return {"symbol": symbol, "stock": stocks, "page": page, "count": count}
    else:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}

@app.post("/stocks/{symbol}/buy")
def buy_stock(symbol: str, quantity: int, user_email: str):
    if quantity <= 0:
        return {"error": "La cantidad debe ser mayor que cero."} #quizas que las acciones que se quieran/puedan se vean en el frontend
    stock = collection.find_one({"symbol": symbol})
    if not stock:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}
    if stock["quantity"] < quantity:
        return {"error": "No hay suficientes acciones disponibles."}

    collection.update_one({"symbol": symbol}, {"$set": {"quantity": stock["quantity"]}})

    #pregutar si es necesario esto, duda de cuando se tiene la confirmacion, como se actualiza y como se guarda con el id de usuario para actulizar sus acciones
    transaction = {
        "symbol": symbol,
        "quantity": quantity,
        "user_email": user_email,
        "timestamp": datetime.utcnow()
    }
    transactions_collection.insert_one(transaction)
    mqtt_manager.publish_buy_request(symbol, quantity)
    return {"message": "Solicitud de compra exitosa.", "transaction": transaction}


@app.post("/register")
def register_user(correo: str, password: str,telefono:str,nombre:str):
    if users_collection.find_one({"correo": correo}):
        return {"error": "El correo ya está registrado."}
    
    elif not correo or not password or not telefono or not nombre: #esto puede modificare directamente en el frontend
        return {"error": "Todos los campos son obligatorios."}
    user = {
        "correo": correo,
        "password": password,
        "telefono": telefono,
        "nombre": nombre,
        "saldo": 0.0,
        "transactions": [],
        "stocks": [],
        "updated_at": datetime.utcnow()}
    users_collection.insert_one(user)
    return {"message": "Usuario registrado exitosamente.", "user": {"correo": correo, "nombre": nombre}}
@app.post("/login")

def login_user(correo: str, password: str):
    user = users_collection.find_one({"correo": correo, "password": password})
    if user:
        return {"message": "Inicio de sesión exitoso.", "user": {"correo": correo, "nombre": user["nombre"]}}
    else:
        return {"error": "Credenciales incorrectas."}
    
#usuario carga su billetera
@app.post("/wallet")
def add_funds(correo: str, monto: float):
    if monto <= 0:
        return {"error": "El monto debe ser mayor que cero."}
    
    user = users_collection.find_one({"correo": correo})
    if not user:
        return {"error": "Usuario no encontrado."}
    users_collection.update_one({"correo": correo}, {"$set": {"saldo": user["saldo"] + monto}})
    return {"message": "Fondos añadidos exitosamente.", "new_balance": user["saldo"] + monto}