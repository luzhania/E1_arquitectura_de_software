from fastapi import FastAPI, Query, Depends
from typing import Optional
from datetime import datetime
from database import get_db
from buy_requests.buy_requests import mqtt_manager
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
from datetime import datetime
from auth import verify_token, admin_required, is_admin
from typing import Dict
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi import Request
import utils.transbank as tx
import utils.purchase_receip as purchase_receip
import uuid
import base64
import httpx
from fastapi import Body



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

db = get_db()
collection = db["current_stocks"]
transactions_collection = db["transactions"]

admin_transactions_collection = db["admin_transactions"]

users_db = get_db()
users_collection = users_db["users"]
collection_event_log = db["event_log"]
#ESTO ES NUEVO
estimations_collection = db["estimations"]

# Inicializar el cliente de Transbank
# tx_client = tx.get_tx()


@app.get("/")
def read_root():
    return {"message": "API for stocks"}

def build_stocks_query(symbol=None, price=None, longName=None, timestamp=None, quantity=None):
    from datetime import datetime
    query = {}
    # Symbol filter
    if symbol:
        query["symbol"] = {"$regex": f"^{symbol}", "$options": "i"}
    # Price range filter (format: min-max)
    if price:
        price_parts = price.split('-')
        if len(price_parts) == 2:
            min_price, max_price = price_parts
            query["price"] = {}
            if min_price:
                query["price"]["$gte"] = float(min_price)
            if max_price:
                query["price"]["$lte"] = float(max_price)
            if not query["price"]:
                del query["price"]
    # Name filter
    if longName:
        query["longName"] = {"$regex": longName, "$options": "i"}
    # Timestamp range filter (format: YYYY-MM-DD-YYYY-MM-DD)
    if timestamp:
        parts = timestamp.split('-')
        if len(parts) == 6:
            from_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
            to_str   = f"{parts[3]}-{parts[4]}-{parts[5]}"
        else:
            mid = len(parts) // 2
            from_str = '-'.join(parts[:mid])
            to_str   = '-'.join(parts[mid:])
        try:
            dt_from = datetime.fromisoformat(from_str)
            dt_to   = datetime.fromisoformat(to_str)
            start = datetime(dt_from.year, dt_from.month, dt_from.day, 0, 0, 0)
            end   = datetime(dt_to.year,   dt_to.month,   dt_to.day,   23, 59, 59)
            query["timestamp"] = {"$gte": start, "$lte": end}
        except ValueError:
            pass
    # Quantity range filter (format: min-max)
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
            if not query["quantity"]:
                del query["quantity"]
        else:
            try:
                query["quantity"] = {"$gte": int(quantity)}
            except ValueError:
                pass
    return query

@app.get("/admin/stocks")
def get_stocks(
    symbol: Optional[str] = None, 
    price: Optional[str] = None,
    longName: Optional[str] = None,
    timestamp: Optional[str] = None,
    quantity: Optional[str] = None,  # Modificado para aceptar un rango en formato "min-max"
    page: int = Query(1, ge=1), 
    count: int = Query(25, ge=1),
    user=Depends(admin_required)
):
    # Verifica si el usuario es un administrador
    if not user:
        return JSONResponse(status_code=403, content={"error": "Acceso denegado. Usuario no autorizado."})
    skip = (page - 1) * count
    query = build_stocks_query(symbol, price, longName, timestamp, quantity)
    print(f"MongoDB query: {query}")
    if collection is not None:
        stocks = list(collection.find(query, {"_id": 0}).skip(skip).limit(count))
        total_count = collection.count_documents(query)
        return {"stocks": stocks, "page": page, "count": total_count}
    else:
        return {"error": "No hay stocks disponibles."}
    
@app.get("/stocks")
def get_stocks(
    symbol: Optional[str] = None, 
    price: Optional[str] = None,
    longName: Optional[str] = None,
    timestamp: Optional[str] = None,
    quantity: Optional[str] = None,
    page: int = Query(1, ge=1), 
    count: int = Query(25, ge=1)
):
    if admin_transactions_collection is None or collection is None:
        return {"error": "No hay stocks disponibles."}
    
    print(admin_transactions_collection)
    # Obtener todos los símbolos disponibles en admin_transactions_collection
    available_admin_stocks = list(admin_transactions_collection.find({}, {"_id": 0, "symbol": 1, "quantity": 1}))
    available_symbols = {item["symbol"]: item["quantity"] for item in available_admin_stocks}
    
    if not available_symbols:
        return {"error": "No hay acciones disponibles para compra."}

    # Construir la consulta para obtener los detalles desde la colección principal
    query = {"symbol": {"$in": list(available_symbols.keys())}}

    if symbol:
        query["symbol"] = symbol
    if longName:
        query["longName"] = {"$regex": longName, "$options": "i"}
    if price:
        try:
            min_price, max_price = map(float, price.split("-"))
            query["price"] = {"$gte": min_price, "$lte": max_price}
        except ValueError:
            return {"error": "Formato de precio inválido. Usa 'min-max'."}
    if timestamp:
        query["timestamp"] = timestamp

    skip = (page - 1) * count

    # Buscar en la colección principal
    matching_stocks = list(collection.find(query, {"_id": 0}).skip(skip).limit(count))
    total_count = collection.count_documents(query)

    # Enriquecer con cantidad disponible desde admin_transactions_collection
    for stock in matching_stocks:
        stock["quantity"] = available_symbols.get(stock["symbol"], 0)

    if not matching_stocks:
        return {"error": "No se encontraron acciones que coincidan con los criterios de búsqueda."}

    return {
        "stocks": matching_stocks,
        "page": page,
        "count": total_count
    }

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
    user_id = user["sub"]
    print(f"User email: {user_id}")
    if quantity <= 0:
        return {"error": "La cantidad debe ser mayor que cero."} #quizas que las acciones que se quieran/puedan se vean en el frontend
    stock = collection.find_one({"symbol": symbol})
    if not stock:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}
    if stock["quantity"] < quantity:
        return {"error": "No hay suficientes acciones disponibles."}
    user = users_collection.find_one({"correo": user_id})
    if not user:
        return {"error": "Usuario no encontrado."}
    if user["saldo"] < stock["price"] * quantity:
        return {"error": "Saldo insuficiente."}

    transaction_id = str(uuid.uuid4())
    mqtt_manager.publish_buy_request(transaction_id, symbol, quantity)
    transaction = {
        "request_id": transaction_id,
        "symbol": symbol,
        "quantity": quantity,
        "user_email": user_id,
        "timestamp": datetime.utcnow(),
        "status": "PENDING"
    }
    result = transactions_collection.insert_one(transaction)
    transaction["_id"] = str(result.inserted_id)
    price = stock["price"]
    mqtt_manager.enviar_estimacion_jobmaster(user_id, symbol, quantity, price,transaction_id)
    return {"message": "Solicitud de compra exitosa.", "transaction": transaction}

# Usuario normal compra del administrador
@app.post("/webpay/create")
def iniciar_webpay_user(data: dict, user=Depends(verify_token)):
    user_id = user["sub"]
    user = users_collection.find_one({"correo": user_id})
    if not user:
        return {"error": "Usuario no encontrado."}
    stock = collection.find_one({"symbol": data["symbol"]})
    if not stock:
        return {"error": f"Stock con símbolo {data['symbol']} no encontrado."}
    if stock["quantity"] < data["quantity"]:
        return {"error": "No hay suficientes acciones disponibles."}
    
    id = uuid.uuid4()

    b64 = base64.urlsafe_b64encode(id.bytes).decode('utf-8').rstrip('=')
    transaction_id = b64[:26]

    request_id = str(id)
    amount = round(float(data["amount"]))
    
    # Build the frontend payment URL from the environment variable
    frontend_payment_url = f"{URL_FRONTEND}/payment" if URL_FRONTEND else "https://www.arquitecturadesoftware.me/payment"
    trx_resp = tx.get_tx().create(transaction_id, "stocks_buy", amount, frontend_payment_url)
    
    #Ya no envia la solicitud al broker
    # if data.get("owner_type", False) == "platform":
    #     # Si es una compra a las stocks de la plataforma, envía solicitud de compra al broker
    #     mqtt_manager.publish_buy_request(request_id, data["symbol"], data["quantity"], trx_resp["token"])
    #     mqtt_manager.publish_validation(request_id, "ACCEPTED", trx_resp["token"])

    #Actualizar la colección de las transacciones del administrador
    admin_transactions_collection.update_one(
        {"symbol": data["symbol"]},
        {"$inc": {"quantity": -data["quantity"]}, "$set": {"timestamp": datetime.utcnow()}},
        upsert=True
    )
    
    transaction = {
        "request_id": request_id,
        "transaction_id": transaction_id,
        "token_ws": trx_resp["token"],
        "symbol": data["symbol"],
        "quantity": data["quantity"],
        "user_email": user_id,
        "timestamp": datetime.utcnow(),
        "status": "PENDING",
        "estimated_gain": None,  # Inicializar como None
        "owner_type": data.get("owner_type", "platform")  # Agregar owner_type
    }

    transactions_collection.insert_one(transaction)
    return {"url": trx_resp["url"], "token_ws": trx_resp["token"], "request_id": request_id}

#Administrador compra de inventario
@app.post("/admin/webpay/create")
def iniciar_webpay_admin(data: dict, user=Depends(admin_required)):
    user_id = user["sub"]
    user = users_collection.find_one({"correo": user_id})
    if not user:
        return {"error": "Usuario no encontrado."}
    stock = collection.find_one({"symbol": data["symbol"]})
    if not stock:
        return {"error": f"Stock con símbolo {data['symbol']} no encontrado."}
    if stock["quantity"] < data["quantity"]:
        return {"error": "No hay suficientes acciones disponibles."}
    
    id = uuid.uuid4()

    b64 = base64.urlsafe_b64encode(id.bytes).decode('utf-8').rstrip('=')
    transaction_id = b64[:26]

    request_id = str(id)
    amount = round(float(data["amount"]))
    
    # Build the frontend payment URL from the environment variable
    frontend_payment_url = f"{URL_FRONTEND}/payment" if URL_FRONTEND else "https://www.arquitecturadesoftware.me/payment"
    trx_resp = tx.get_tx().create(transaction_id, "stocks_buy", amount, frontend_payment_url)
    
    mqtt_manager.publish_buy_request(request_id, data["symbol"], data["quantity"], trx_resp["token"])
    mqtt_manager.publish_validation(request_id, "ACCEPTED", trx_resp["token"])
    transaction = {
        "request_id": request_id,
        "transaction_id": transaction_id,
        "token_ws": trx_resp["token"],
        "symbol": data["symbol"],
        "quantity": data["quantity"],
        "user_email": user_id,
        "timestamp": datetime.utcnow(),
        "status": "PENDING",
        "estimated_gain": None,  # Inicializar como None
    }

    transactions_collection.insert_one(transaction)
    
    # Guardar la transacción en la colección de transacciones del administrador
    #Que actualice la transacción aumentando la cantidad de acciones
    admin_transactions_collection.update_one(
        {"symbol": data["symbol"]},
        {"$inc": {"quantity": data["quantity"]}, "$set": {"timestamp": datetime.utcnow()}},
        upsert=True
    )
    return {"url": trx_resp["url"], "token_ws": trx_resp["token"], "request_id": request_id}

@app.post("/webpay/commit")
async def commit_transaction(request: Request, user=Depends(verify_token)):
    body = await request.json()
    token_ws = body.get("token_ws")
    transaction = transactions_collection.find_one({"request_id": body.get("request_id")})

    # TRANSACCIÓN ANULADA POR EL USUARIO
    if not token_ws or token_ws == "":
        if is_admin(user):
            mqtt_manager.publish_validation(body.get("request_id"), "REJECTED", transaction["token_ws"])
        else:
            #Retornar cantidad de acciones al inventario del administrador
            admin_transactions_collection.update_one(
                {"symbol": transaction["symbol"]},
                {"$inc": {"quantity": transaction["quantity"]}, "$set": {"timestamp": datetime.utcnow()}},
                upsert=True
            )
            #Actualizar status de la transaccctions collection
            transactions_collection.update_one(
                {"request_id": body.get("request_id")},
                {"$set": {"status": "CANCEL", "timestamp": datetime.utcnow()}}
            )
        return {"status": "CANCEL",
                "message": "Transacción anulada por el usuario."}

    try:
        response = tx.get_tx().commit(token_ws)

        response_status = "OK" if response["response_code"] == 0 else "REJECTED"
        if is_admin(user):
            mqtt_manager.publish_validation(body.get("request_id"), response_status, transaction["token_ws"])

        # TRANSACCIÓN RECHAZADA
        if response["response_code"] != 0:
            if not is_admin(user):
                # Retornar cantidad de acciones al inventario del administrador
                admin_transactions_collection.update_one(
                    {"symbol": transaction["symbol"]},
                    {"$inc": {"quantity": transaction["quantity"]}, "$set": {"timestamp": datetime.utcnow()}},
                    upsert=True
                )
                # Actualizar status de la transacción en transactions_collection
                transactions_collection.update_one(
                    {"request_id": body.get("request_id")},
                    {"$set": {"status": "REJECTED", "timestamp": datetime.utcnow()}}
                )
            return {"status":"REJECTED",
                    "message": "Transacción ha sido rechazada.",
                    }
        
        # TRANSACCIÓN ACEPTADA
        #Generación de boleta
        receipt_url = purchase_receip.generate_receipt(
            user_data={"email": user["sub"]},
            stock_data={
                "name": transaction["symbol"],
                "quantity": transaction["quantity"],
                "total": response["amount"]
            }
        )
        #ESTO ES NUEVO
        # Si es un usuario normal actualiza su estado aca
        if not is_admin(user):
            # Actualizar el status de la transacción en transactions_collection
            transactions_collection.update_one(
                {"request_id": body.get("request_id")},
                {"$set": {"status": "OK", "timestamp": datetime.utcnow()}}
            )
        # Generar estimación solo si el pago fue exitoso
        #FALTA PROBAR
        print("request_id:", body.get("request_id"))
        stock = collection.find_one({"symbol": transaction["symbol"]})
        price = stock["price"] if stock else response["amount"] / transaction["quantity"]

        mqtt_manager.enviar_estimacion_jobmaster(
            user["sub"],
            transaction["symbol"],
            transaction["quantity"],
            price,
            transaction["request_id"]
        )
        # revisar

        # modificar transaccion con receipt_url
        transactions_collection.update_one(
            {"request_id": body.get("request_id")},
            {"$set": {"receipt_url": receipt_url}}
        )

        # INCLUIR MÁS INFORMACIÓN EN LA RESPUESTA
        return {
            "status": "OK",
            "message": "Transacción ha sido autorizada.",
            "transaction_id": response["buy_order"],
            "receipt_url": receipt_url,
            # AGREGAR ESTOS CAMPOS:
            "symbol": transaction["symbol"],
            "quantity": transaction["quantity"],
            "amount": response["amount"],
            "transaction_data": {
                "symbol": transaction["symbol"],
                "quantity": transaction["quantity"],
                "amount": response["amount"],
                "user_email": transaction["user_email"],
                "timestamp": transaction["timestamp"].isoformat() if transaction.get("timestamp") else None
            }
        }
    
    except Exception as e:
        print("Error en la transacción:", e)
        return {"status": "ERROR",
                "message": "Error en la transacción."}

#historial de transacciones
@app.post("/stocks/{symbol}/buy")
def buy_stock(symbol: str, quantity: int, user=Depends(verify_token)):
    user_id = user["sub"]
    print(f"User email: {user_id}")

    if quantity <= 0:
        return {"error": "La cantidad debe ser mayor que cero."}

    stock = collection.find_one({"symbol": symbol})
    if not stock:
        return {"error": f"Stock con símbolo {symbol} no encontrado."}

    if stock["quantity"] < quantity:
        return {"error": "No hay suficientes acciones disponibles."}

    user_data = users_collection.find_one({"correo": user_id})
    if not user_data:
        return {"error": "Usuario no encontrado."}

    total_price = stock["price"] * quantity
    if user_data["saldo"] < total_price:
        return {"error": "Saldo insuficiente."}

    # Descontar saldo al usuario
    users_collection.update_one(
        {"correo": user_id},
        {"$inc": {"saldo": -total_price}}
    )

    transaction_id = str(uuid.uuid4())

   
   # Publicar compra y enviar estimación
    mqtt_manager.publish_buy_request(transaction_id, symbol, quantity)

    # ✅ Agregar el price al enviar la estimación
    price = stock["price"]
    mqtt_manager.enviar_estimacion_jobmaster(user_id, symbol, quantity, price, transaction_id)


    transaction = {
        "request_id": transaction_id,
        "transaction_id": transaction_id,
        "symbol": symbol,
        "quantity": quantity,
        "user_email": user_id,
        "timestamp": datetime.utcnow(),
        "status": "PENDING",
        "estimated_gain": None
    }

    result = transactions_collection.insert_one(transaction)
    transaction["_id"] = str(result.inserted_id)

    return {"message": "Compra con saldo registrada exitosamente.", "transaction": transaction}


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

@app.post("/wallet")
def add_funds(monto: float, user: Dict = Depends(verify_token)):
    user_id = user["sub"]
    if monto <= 0:
        return {"error": "El monto debe ser mayor que cero."}
    
    user_db = users_collection.find_one({"correo": user_id})
    if not user_db:
        # Si el usuario no existe, lo creamos
        users_collection.insert_one({
            "correo": user_id,
            "saldo": monto
        })
        return {"message": "Usuario creado y fondos añadidos exitosamente.", "new_balance": monto}
    else:
        # Si el usuario existe, actualizamos su saldo
        new_balance = user_db["saldo"] + monto
        users_collection.update_one({"correo": user_id}, {"$set": {"saldo": new_balance}})
        return {"message": "Fondos añadidos exitosamente.", "new_balance": new_balance}

@app.get("/wallet")
def get_wallet(user: Dict = Depends(verify_token)):
    user_id = user["sub"]
    
    user_db = users_collection.find_one({"correo": user_id})
    if user_db:
        return {
            "correo": user_id, 
            "saldo": user_db.get("saldo", 0)
        }
    else:
        return {"error": "Usuario no encontrado."}

    
@app.get("/transactions")
def get_transactions(user: Dict = Depends(verify_token), page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    user_id = user["sub"]
    skip = (page - 1) * count
    transactions = list(
        transactions_collection.find({"user_email": user_id}, {"_id": 0})
        .skip(skip)
        .limit(count)
    )
    
    # Para cada transacción, agregar la estimación si existe y formatear fechas
    for tx in transactions:
        estimation = estimations_collection.find_one({"transaction_id": tx.get("transaction_id")}, {"_id": 0})
        
        if estimation:
            # Formatear fecha completed_at si existe
            if estimation.get("completed_at"):
                estimation["completed_at"] = estimation["completed_at"].isoformat()
            tx["estimation"] = estimation
        else:
            tx["estimation"] = None
        
        if tx.get("timestamp"):
            tx["timestamp"] = tx["timestamp"].isoformat()

    if transactions:
        total_count = transactions_collection.count_documents({"user_email": user_id})
        return {"stocks": transactions, "page": page, "count": total_count}
    else:
        return {"error": f"No se encontraron transacciones para el usuario {user_id}."}
    


@app.get("/transactions/ok")
def get_transactions_ok(user: Dict = Depends(verify_token), page: int = Query(1, ge=1), count: int = Query(25, ge=1)):
    user_id = user["sub"]
    skip = (page - 1) * count
    transactions = list(
        transactions_collection.find({"user_email": user_id, "status": "OK"}, {"_id": 0})
        .skip(skip)
        .limit(count)
    )
    
    if transactions:
        return {"transactions": transactions, "page": page, "count": count}
    else:
        return {"error": f"No se encontraron transacciones OK para el usuario {user_id}."}
    

# TODO ESTO ES NUEVO
@app.get("/transactions/{request_id}") #FALTA PROBAR
def get_transaction(request_id: str, user=Depends(verify_token)):
    user_email = user["sub"]
    transaction = transactions_collection.find_one({"request_id": request_id, "user_email": user_email})
    if not transaction:
        return {"error": "Transacción no encontrada"}

    estimation = estimations_collection.find_one({"transaction_id": transaction.get("transaction_id")})
 
    if transaction.get("timestamp"):
        transaction["timestamp"] = transaction["timestamp"].isoformat()

    return {
        "transaction": transaction,
        "estimation": estimation
    }
 
@app.get("/heartbeat") #FUNCIONA
async def estado_workers():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://iic2175danielaarp.me/heartbeat")
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"status": "remote error", "code": resp.status_code}
    except Exception as e:
        return {"status": "offline", "error": str(e)}
    
#actualizar estimación de stock


@app.post("/internal/update_job")
def update_job(data: dict = Body(...)):
    job_id = data.get("job_id")
    result = data.get("result")
    request_id = result.get("request_id")

    print("result:", result)
    print("estimated_gain:", result.get("estimated_gain"))
    print("request:_id:", request_id)

    transaction = transactions_collection.find_one({"request_id": request_id})

    if not transaction:
        print(f"⚠️ Request con ID {request_id} no encontrada")
        return {"error": "REQUEST no encontrada"}

    # Actualiza el campo estimated_gain en la transacción
    update_result = transactions_collection.update_one(
        {"request_id": request_id},
        {"$set": {"estimated_gain": result.get("estimated_gain")}}
    )

    print("Mongo update result:", update_result.modified_count)

    # Inserta también en la colección 'estimations'
    estimations_collection.insert_one({
        "transaction_id": transaction.get("transaction_id"),
        "estimated_gain": result.get("estimated_gain"),
        "status": result.get("status"),
        "completed_at": datetime.utcnow()
    })

    return {"status": "updated"}

