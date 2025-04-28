from fastapi import FastAPI, Query, Depends
from typing import Optional
from datetime import datetime
from database import get_db
from buy_requests.buy_requests import mqtt_manager 
from routes import router
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
from datetime import datetime
from auth import verify_token
from typing import Dict

import os
from dotenv import load_dotenv
load_dotenv()

URL_FRONTEND = os.getenv("URL_FRONTEND")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[URL_FRONTEND] if URL_FRONTEND else ["*"],  # URL del frontend desde .env
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos
    allow_headers=["*"],  # Permite todos los headers
)

app.include_router(router)

db = get_db()
collection = db["current_stocks"]
transactions_collection = db["transactions"]
users_db = get_db()
users_collection = users_db["users"]
collection_event_log = db["event_log"]


@app.get("/")
def read_root():
    return {"message": "API for stocks"}

@app.get("/stocks")
def get_stocks(
    symbol: Optional[str] = None, 
    price: Optional[str] = None,
    longName: Optional[str] = None,
    timestamp: Optional[str] = None,
    quantity: Optional[str] = None,  # Modificado para aceptar un rango en formato "min-max"
    page: int = Query(1, ge=1), 
    count: int = Query(25, ge=1)
):
    skip = (page - 1) * count
    query = {}
    
    # Add filters to the query
    if symbol:
        query["symbol"] = {"$regex": f"^{symbol}", "$options": "i"}
    
    # Handle price range (format: min-max)
    if price:
        price_parts = price.split('-')
        if len(price_parts) == 2:
            min_price, max_price = price_parts
            query["price"] = {}
            if min_price:
                query["price"]["$gte"] = float(min_price)
            if max_price:
                query["price"]["$lte"] = float(max_price)
    
    # Handle stock name
    if longName:
        query["longName"] = {"$regex": longName, "$options": "i"}
    
    # Handle date range (format: YYYY-MM-DD-YYYY-MM-DD)
    if timestamp:
        parts = timestamp.split('-')
        # Armamos las dos fechas
        if len(parts) == 6:
            from_str = f"{parts[0]}-{parts[1]}-{parts[2]}"  # "YYYY-MM-DD"
            to_str   = f"{parts[3]}-{parts[4]}-{parts[5]}"
        else:
            mid = len(parts) // 2
            from_str = '-'.join(parts[:mid])
            to_str   = '-'.join(parts[mid:])

        # Parseamos a datetime
        try:
            dt_from = datetime.fromisoformat(from_str)
            dt_to   = datetime.fromisoformat(to_str)

            # Normalizamos a rango full days
            start = datetime(dt_from.year, dt_from.month, dt_from.day, 0, 0, 0)
            end   = datetime(dt_to.year,   dt_to.month,   dt_to.day,   23, 59, 59)

            query["timestamp"] = {
                "$gte": start,
                "$lte": end
            }
            print(f"From date: {start}")
            print(f"To date:   {end}")
        except ValueError as e:
            print("Fecha inválida en timestamp:", e)
    
    # Handle quantity filter (format: min-max)
    if quantity:
        quantity_parts = quantity.split('-')
        if len(quantity_parts) == 2:
            min_quantity, max_quantity = quantity_parts
            query["quantity"] = {}
            if min_quantity:
                try:
                    query["quantity"]["$gte"] = int(min_quantity)
                except ValueError:
                    pass
            if max_quantity:
                try:
                    query["quantity"]["$lte"] = int(max_quantity)
                except ValueError:
                    pass
        else:
            # Mantener compatibilidad con la versión anterior
            try:
                query["quantity"] = {"$gte": int(quantity)}
            except ValueError:
                pass
    
    # For debugging
    print(f"MongoDB query: {query}")
    
    # Execute the filtered query
    if collection is not None:
        stocks = list(collection.find(query, {"_id": 0}).skip(skip).limit(count))
        total_count = collection.count_documents(query)
        return {"stocks": stocks, "page": page, "count": total_count}
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
def buy_stock(symbol: str, quantity: int, user=Depends(verify_token)):
    user_email = user["sub"]
    print(f"User email: {user_email}")
    if quantity <= 0:
        return {"error": "La cantidad debe ser mayor que cero."} #quizas que las acciones que se quieran/puedan se vean en el frontend
    stock = collection.find_one({"symbol": symbol})
    if not stock:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}
    if stock["quantity"] < quantity:
        return {"error": "No hay suficientes acciones disponibles."}
    # user = users_collection.find_one({"correo": user_email})
    # if not user:
    #     return {"error": "Usuario no encontrado."}
    # if user["saldo"] < stock["price"] * quantity:
    #     return {"error": "Saldo insuficiente."}

    my_request_id = mqtt_manager.publish_buy_request(symbol, quantity)
    transaction = {
        "request_id": my_request_id,
        "symbol": symbol,
        "quantity": quantity,
        "user_email": user_email,
        "timestamp": datetime.utcnow(),
        "status": "PENDING"
    }
    result = transactions_collection.insert_one(transaction)
    transaction["_id"] = str(result.inserted_id)
    return {"message": "Solicitud de compra exitosa.", "transaction": transaction}
    # return {"message": "Solicitud de compra exitosa."}

class RegisterUserRequest(BaseModel):
    correo: str
    password: str
    telefono: str
    nombre: str

class LoginRequest(BaseModel):
    correo: str
    password: str

class WalletRequest(BaseModel):
    # correo: str
    monto: float

class BuyStockRequest(BaseModel):
    quantity: int
    user_email: str

#historial de transacciones
@app.get("/stocks/{symbol}/event_log")
def get_event_log(symbol: str, page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    skip = (page - 1) * count
    query = {"symbol": symbol}
    
    events = list(collection_event_log.find(query, {"_id": 0}).skip(skip).limit(count))

    if events:
        return {"symbol": symbol, "event_log": events, "page": page, "count": count}
    else:
        return {"error": f"No se encontraron eventos para el símbolo {symbol}."}

@app.get("/events/all")  # Cambio de ruta para evitar conflictos
def get_all_event_logs(
    symbol: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = Query(1, ge=1), 
    count: int = Query(25, ge=1)
):
    skip = (page - 1) * count
    query = {}
    
    # Add optional filters
    if symbol:
        query["symbol"] = {"$regex": f"^{symbol}", "$options": "i"}
    
    # Handle date range filtering
    if from_date or to_date:
        query["timestamp"] = {}
        if from_date:
            try:
                dt_from = datetime.fromisoformat(from_date)
                start = datetime(dt_from.year, dt_from.month, dt_from.day, 0, 0, 0)
                query["timestamp"]["$gte"] = start
            except ValueError:
                return {"error": "from_date debe tener el formato 'YYYY-MM-DD'"}
                
        if to_date:
            try:
                dt_to = datetime.fromisoformat(to_date)
                end = datetime(dt_to.year, dt_to.month, dt_to.day, 23, 59, 59)
                query["timestamp"]["$lte"] = end
            except ValueError:
                return {"error": "to_date debe tener el formato 'YYYY-MM-DD'"}
    
    events = list(collection_event_log.find(query, {"_id": 0}).skip(skip).limit(count))
    total_count = collection_event_log.count_documents(query)
    
    # Cambio en la estructura de respuesta para que sea igual que get_event_log
    if events:
        return {
            "event_log": events,
            "page": page,
            "count": len(events),
            "total": total_count
        }
    else:
        return {"error": "No se encontraron eventos con los filtros especificados."}

@app.post("/register")
def register_user(request: RegisterUserRequest):
    if users_collection.find_one({"correo": request.correo}):
        return {"error": "El correo ya está registrado."}
    elif not request.correo or not request.password or not request.telefono or not request.nombre:
        return {"error": "Todos los campos son obligatorios."}
    
    user = {
        "correo": request.correo,
        "password": request.password,
        "telefono": request.telefono,
        "nombre": request.nombre,
        "saldo": 0.0,
        "updated_at": datetime.utcnow()
    }
    users_collection.insert_one(user)
    return {"message": "Usuario registrado exitosamente.", "user": {"correo": request.correo, "nombre": request.nombre}}


@app.post("/login")
def login_user(request: LoginRequest):
    user = users_collection.find_one({"correo": request.correo, "password": request.password})
    if user:
        return {"message": "Inicio de sesión exitoso.", "user": {"correo": request.correo, "nombre": user["nombre"]}}
    else:
        return {"error": "Credenciales incorrectas."}


@app.post("/wallet")
def add_funds(monto: float, user: Dict = Depends(verify_token)):
    correo = user["sub"]
    if monto <= 0:
        return {"error": "El monto debe ser mayor que cero."}
    
    user_db = users_collection.find_one({"correo": correo})
    if not user_db:
        # Si el usuario no existe, lo creamos
        users_collection.insert_one({
            "correo": correo,
            "saldo": monto
        })
        return {"message": "Usuario creado y fondos añadidos exitosamente.", "new_balance": monto}
    else:
        # Si el usuario existe, actualizamos su saldo
        new_balance = user_db["saldo"] + monto
        users_collection.update_one({"correo": correo}, {"$set": {"saldo": new_balance}})
        return {"message": "Fondos añadidos exitosamente.", "new_balance": new_balance}

@app.get("/wallet")
def get_wallet(user: Dict = Depends(verify_token)):
    correo = user["sub"]
    
    user_db = users_collection.find_one({"correo": correo})
    if user_db:
        return {
            "correo": correo, 
            "saldo": user_db.get("saldo", 0)
        }
    else:
        return {"error": "Usuario no encontrado."}

    
@app.get("/transactions")
def get_transactions(user: Dict = Depends(verify_token), page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    correo = user["sub"]
    print(f"User email: {correo}")
    skip = (page - 1) * count
    transactions = list(
        transactions_collection.find({"user_email": correo}, {"_id": 0})
        .skip(skip)
        .limit(count)
    )
    
    if transactions:
        total_transactions = transactions_collection.count_documents({"user_email": correo})
        return {"stocks": transactions, "page": page, "count": count, "total_transactions": total_transactions}
    else:
        return {"error": f"No se encontraron transacciones para el usuario {correo}."}


@app.get("/transactions/ok")
def get_transactions_ok(user: Dict = Depends(verify_token), page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    correo = user["sub"]
    skip = (page - 1) * count
    transactions = list(
        transactions_collection.find({"user_email": correo, "status": "OK"}, {"_id": 0})
        .skip(skip)
        .limit(count)
    )
    
    if transactions:
        return {"transactions": transactions, "page": page, "count": count}
    else:
        return {"error": f"No se encontraron transacciones OK para el usuario {correo}."}


@app.get("/balance")
def get_user_info(user: Dict = Depends(verify_token)):
    correo = user["sub"]
    user_db = users_collection.find_one({"correo": correo}, {"_id": 0})
    
    if user_db:
        return {"user": user_db}
    else:
        return {"error": "Usuario no encontrado."}