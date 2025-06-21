import os
import json
import paho.mqtt.client as mqtt
from dateutil import parser
from pymongo import MongoClient
from dotenv import load_dotenv
import time

load_dotenv()

BROKER_HOST = os.getenv("MQTT_BROKER")
BROKER_PORT = int(os.getenv("MQTT_PORT", "9000"))
REQUEST_TOPIC = "stocks/requests"
VALIDATION_TOPIC = "stocks/validation"
AUCTION_TOPIC = "stocks/auctions"
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")

# Detect if running in CI environment
IS_CI = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
print(f"[BROKER_REQUESTS] Running in CI environment: {IS_CI}")

# Only connect to MongoDB if not in CI
if IS_CI:
    print("[BROKER_REQUESTS] Running in CI environment, skipping database connection")
    client_mongo = None
    db = None
    collection_requests = None
    collection_stocks = None
    collection_transactions = None
    collection_users = None
    collection_event_log = None
    collection_auction_offers = None
    admin_transactions_collection = None
else:
    print("[BROKER_REQUESTS] Iniciando cliente MQTT")
    try:
        client_mongo = MongoClient(MONGO_URI)
        db = client_mongo["stocks_db"] 
        collection_requests = db["requests"]
        collection_stocks = db["current_stocks"]
        collection_transactions = db["transactions"]
        collection_users = db["users"]
        collection_event_log = db["event_log"]
        collection_auction_offers = db["auction_offers"]
        admin_transactions_collection = db["admin_transactions"]
        print("[BROKER_REQUESTS] Connected to MongoDB")
    except Exception as e:
        print(f"[BROKER_REQUESTS] Failed to connect to MongoDB: {e}")
        client_mongo = None

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Conectado al broker con código de resultado: {rc}")
    print(f"[DEBUG] Conectado con código: {rc}")
    client.subscribe(REQUEST_TOPIC)
    print(f"[DEBUG] Suscrito a: {REQUEST_TOPIC}")
    client.subscribe(VALIDATION_TOPIC)
    print(f"[DEBUG] Suscrito a: {VALIDATION_TOPIC}")
    client.subscribe(AUCTION_TOPIC)
    print(f"[DEBUG] Suscrito a: {AUCTION_TOPIC}")

def on_message(client, userdata, msg):
    print(f"Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    # Skip processing in CI environment
    if IS_CI:
        print("[BROKER_REQUESTS] Running in CI, skipping message processing")
        return
        
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        handle_timestamp(data)
        if msg.topic == REQUEST_TOPIC:
            if is_purchase_request(data):
                handle_purchase_request(data)
            elif is_response(data):
                handle_response(data)
        elif msg.topic == VALIDATION_TOPIC:
            handle_validation(data)
        elif msg.topic == AUCTION_TOPIC:
            print("Mensaje de subasta recibido")
            if is_auction_offer(data):
                handle_auction_offer(data)
                print("Oferta de subasta recibida")
            elif is_auction_proposal(data):
                print("Propuesta de subasta recibida")
                handle_auction_proposal(data)
            elif is_auction_response(data):
                operation = data.get("operation")
                if operation == "acceptance":
                    handle_acceptance_response(data)
                else:
                    handle_rejection_response(data)

    except json.JSONDecodeError as e:
        print("Error al decodificar el JSON:", e)

def is_auction_offer(data):
    return data.get("operation") == "offer"

def is_auction_proposal(data):
    return data.get("operation") == "proposal"

def is_auction_response(data):
    return data.get("operation") == "acceptance" or data.get("operation") == "rejection"

def handle_auction_offer(data):
    if collection_auction_offers is None:
        print("[BROKER_REQUESTS] Database not available")
        return
    
    offer_data = {
        "auction_id": data.get("auction_id"),
        "proposals": [],
        "symbol": data.get("symbol"),
        "timestamp": data.get("timestamp"),
        "quantity": data.get("quantity", 0),
        "group_id": data.get("group_id"),
        "status": "OFFERED",
    }
    collection_auction_offers.insert_one(offer_data)
    print(f"Oferta de subasta registrada: {offer_data}")

def handle_auction_proposal(data):
    if collection_auction_offers is None:
        print("[BROKER_REQUESTS] Database not available")
        return
    auction_id = data.get("auction_id")
    #Buscar auction_id en la colección de ofertas
    offer = collection_auction_offers.find_one({"auction_id": auction_id})
    if not offer:
        print(f"Oferta de subasta no encontrada para auction_id: {auction_id}")
        return
    #Añadir proposal_id, symbol, ... a proposals de la collection_auction_offers
    proposal_data = {
        "proposal_id": data.get("proposal_id", ""),
        "symbol": data.get("symbol"),
        "timestamp": data.get("timestamp"),
        "quantity": data.get("quantity", 0),
        "group_id": data.get("group_id"),
        "operation": data.get("operation", "proposal"),
    }
    # Insertar proposal_data al array proposals
    collection_auction_offers.update_one(
        {"auction_id": auction_id},
        {"$push": {"proposals": proposal_data}}
    )
    print(f"Propuesta de subasta registrada: {proposal_data}")

def handle_acceptance_response(data):
    if collection_auction_offers is None:
        print("[BROKER_REQUESTS] Database not available")
        return
        
    auction_id = data.get("auction_id")
    proposal_id = data.get("proposal_id")
    timestamp = data.get("timestamp")

    if not auction_id or not proposal_id:
        print("Ignorando response sin auction_id o proposal_id:", data)
        return

    offer = collection_auction_offers.find_one({"auction_id": auction_id})
    if not offer:
        print(f"Oferta de subasta no encontrada: {auction_id}")
        return
    
    #Buscar propuesta en proposals collection_auction_offers
    proposal = next((p for p in offer.get("proposals", []) if p.get("proposal_id") == proposal_id), None)

    #Buscar si en proposals hay una proposal del grupo 27
    proposal_group_27 = next((p for p in offer.get("proposals", []) if p.get("group_id") == "27"), None)

    if not proposal:
        print(f"Propuesta no encontrada en la oferta {auction_id} para proposal_id: {proposal_id}")
        return

    # Actualizar el estado de la oferta a "ACCEPTED"
    collection_auction_offers.update_one(
        {"auction_id": auction_id},
        {"$set": {"status": "ACCEPTED", "timestamp": timestamp}}
    )
    
    print(f"Respuesta de aceptación registrada para la propuesta {proposal_id} en la oferta {auction_id}")
    #Admin acepta propuesta de otro grupo (Oferta de admin)
    if offer.get("group_id") == "27":
        update_admin_inventary(data)
    #Otro grupo acepta propuesta de admin (Oferta de otro grupo)
    elif proposal.get("group_id") == "27":
        update_admin_inventary(offer)
    #Otro grupo acepta stock a la que admin le hizo una propuesta (Oferta de otro grupo)
    elif proposal_group_27:
        update_admin_inventary(proposal_group_27)
        
def update_admin_inventary(data):
    # Guardar la transacción en la colección de transacciones del administrador
    #Que actualice la transacción aumentando la cantidad de acciones
    admin_transactions_collection.update_one(
        {"symbol": data.get("symbol")},
        {"$inc": {"quantity": data.get("quantity", 0)}, "$set": {"timestamp": data.get("timestamp")}},
        upsert=True
    )

def handle_rejection_response(data):
    #Otro grupo rechaza propuesta de admin, esas stocks vuelven a inventario de grupo
    if collection_auction_offers is None:
        print("[BROKER_REQUESTS] Database not available")
        return
        
    auction_id = data.get("auction_id")
    proposal_id = data.get("proposal_id")
    timestamp = data.get("timestamp")

    if not auction_id or not proposal_id:
        print("Ignorando response sin auction_id o proposal_id:", data)
        return

    offer = collection_auction_offers.find_one({"auction_id": auction_id})
    if not offer:
        print(f"Oferta de subasta no encontrada: {auction_id}")
        return
    
    #Buscar propuesta en proposals collection_auction_offers
    proposal = next((p for p in offer.get("proposals", []) if p.get("proposal_id") == proposal_id), None)
    if not proposal:
        print(f"Propuesta no encontrada en la oferta {auction_id} para proposal_id: {proposal_id}")
        return

    # Actualizar el estado de la oferta a "REJECTED"
    collection_auction_offers.update_one(
        {"auction_id": auction_id},
        {"$set": {"status": "REJECTED", "timestamp": timestamp}}
    )
    
    print(f"Respuesta de rechazo registrada para la propuesta {proposal_id} en la oferta {auction_id}")
    #Otro grupo rechaza propuesta de admin, esas stocks vuelven a inventario de grupo (Oferta de otro grupo)
    if proposal.get("group_id") == "27":
        update_admin_inventary(proposal)
    
def handle_validation(data):
    if collection_requests is None:
        print("[BROKER_REQUESTS] Database not available")
        return
        
    request_id = data.get("request_id")
    status = data.get("status")
    timestamp = data.get("timestamp")

    if not request_id:
        print("Ignorando response sin request_id:", data)
        return

    request_result = collection_requests.find_one({"request_id": request_id})
    if not request_result:
        print(f"Request no encontrada: {request_id}")
        return

    update_request_status(request_id, status, timestamp)
    update_transaction_status(request_id, status, timestamp)
    
    stock_result = collection_stocks.find_one({"symbol": request_result["symbol"]})

    if not stock_result:
        print(f"Stock {request_result['symbol']} no encontrado.")
        return

    if status == "REJECTED":
        handle_rejected_response(request_result, stock_result, timestamp)

def handle_timestamp(data):
    if data.get("timestamp"):
        data["timestamp"] = parser.isoparse(data["timestamp"])

def is_purchase_request(data):
    return "symbol" in data and data.get("kind") != "response"

def is_response(data):
    return data.get("kind") == "response"

def handle_purchase_request(data):
    if collection_requests is None:
        print("[BROKER_REQUESTS] Database not available")
        return
        
    request_data = {
        "request_id": data.get("request_id"),
        "group_id": data.get("group_id"),
        "quantity": data.get("quantity", 0),
        "symbol": data.get("symbol"),
        "operation": data.get("operation", "BUY"),
        "status": "PENDING",
        "applied": False,
        "deposit_token": data.get("deposit_token", ""),
    }
    collection_requests.insert_one(request_data)
    print(f"Request registrada: {request_data}")

def handle_response(data):
    if collection_requests is None:
        print("[BROKER_REQUESTS] Database not available")
        return
        
    request_id = data.get("request_id")
    status = data.get("status")
    timestamp = data["timestamp"]

    if not request_id:
        print("Ignorando response sin request_id:", data)
        return

    request_result = collection_requests.find_one({"request_id": request_id})
    if not request_result:
        print(f"Request no encontrada: {request_id}")
        return

    update_request_status(request_id, status, timestamp)
    update_transaction_status(request_id, status, timestamp)
    
    stock_result = collection_stocks.find_one({"symbol": request_result["symbol"]})
    user_transaction = collection_transactions.find_one({"request_id": request_id})

    if not stock_result:
        print(f"Stock {request_result['symbol']} no encontrado.")
        return

    if status == "ACCEPTED":
        handle_accepted_response(request_result, stock_result, timestamp)
        update_user_wallet(user_transaction, -request_result["quantity"] * stock_result["price"], timestamp)
    elif status == "REJECTED":
        handle_rejected_response(request_result, stock_result, timestamp)
        update_user_wallet(user_transaction, request_result["quantity"] * stock_result["price"], timestamp)

def update_request_status(request_id, status, timestamp):
    if collection_requests is None:
        return
    collection_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": status, "timestamp": timestamp}}
    )
    print(f"Request actualizada: {request_id} | Nuevo estado: {status}")

def update_transaction_status(request_id, status, timestamp):
    if collection_transactions is None:
        return
    transaction = collection_transactions.find_one({"request_id": request_id})
    if transaction:
        collection_transactions.update_one(
            {"request_id": request_id},
            {"$set": {"status": status, "timestamp": timestamp}}
        )
        print(f"Transacción actualizada: {request_id} | Nuevo estado: {status}")

def handle_accepted_response(request, stock, timestamp):
    if collection_stocks is None:
        return
    new_quantity = stock["quantity"] - request["quantity"]
    if new_quantity < 0:
        print(f"No hay suficiente cantidad de {request['symbol']} para completar la solicitud.")
        return

    collection_stocks.update_one(
        {"symbol": request["symbol"]},
        {"$set": {"quantity": new_quantity, "timestamp": timestamp}}
    )
    collection_requests.update_one(
        {"request_id": request["request_id"]},
        {"$set": {"applied": True}}
    )
    print(f"Stock actualizado: {request['symbol']} | Nueva cantidad: {new_quantity}")

    log_event("BUY", request, stock["price"], timestamp)

def handle_rejected_response(request, stock, timestamp):
    if collection_stocks is None:
        return
    if request["applied"]:
        new_quantity = stock["quantity"] + request["quantity"]
        collection_stocks.update_one(
            {"symbol": request["symbol"]},
            {"$set": {"quantity": new_quantity, "timestamp": timestamp}}
        )
        print(f"Stock actualizado: {request['symbol']} | Nueva cantidad: {new_quantity}")
    else:
        collection_requests.update_one(
            {"request_id": request["request_id"]},
            {"$set": {"applied": True}}
        )

def update_user_wallet(transaction, balance_change, timestamp):
    if collection_users is None:
        return
    if not transaction:
        print("Transacción no encontrada.")
        return
    
    user_id = transaction.get("user_email")
    user = collection_users.find_one({"correo": user_id})
    if not user:
        print(f"Usuario {user_id} no encontrado.")
        return

    new_balance = user["saldo"] + balance_change
    collection_users.update_one(
        {"correo": user_id},
        {"$set": {"saldo": new_balance, "timestamp": timestamp}}
    )
    print(f"Saldo actualizado para el usuario {user_id} | Nuevo saldo: {new_balance}")

def log_event(event_type, request, price, timestamp):
    if collection_event_log is None:
        return
    event_data = {
        "type": event_type,
        "symbol": request["symbol"],
        "quantity": request["quantity"],
        "group_id": request["group_id"],
        "price": price,
        "timestamp": timestamp
    }
    collection_event_log.insert_one(event_data)
    print(f"Compra exitosa registrada en el event_log: {event_data}")

def start_mqtt_client():
    print("[BROKER_REQUESTS] Entrando a start_mqtt_client")
    # Skip MQTT connection in CI environment
    if IS_CI:
        print("[BROKER_REQUESTS] Running in CI environment, skipping MQTT client")
        return
        
    if not BROKER_HOST:
        print("[BROKER_REQUESTS] No MQTT broker configured")
        return
    print("[BROKER_REQUESTS] Iniciando cliente MQTT")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            client.loop_forever()
        except ConnectionRefusedError:
            print("Conexión rechazada. Reintentando en 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    start_mqtt_client()