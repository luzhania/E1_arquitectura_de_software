import os
import json
import paho.mqtt.client as mqtt
from dateutil import parser
from pymongo import MongoClient
from dotenv import load_dotenv
import time
load_dotenv()


BROKER_HOST = os.getenv("MQTT_BROKER")
BROKER_PORT = int(os.getenv("MQTT_PORT"))
TOPIC = "stocks/requests"
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["stocks_db"] 
collection_requests = db["requests"]
collection_stocks = db["current_stocks"]
collection_transactions = db["transactions"]
collection_users = db["users"]
collection_event_log = db["event_log"]
collection_rough_requests = db["rough_requests"]

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker con código de resultado: {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        handle_timestamp(data)
        collection_rough_requests.insert_one(data)

        if is_purchase_request(data):
            handle_purchase_request(data)
        elif is_response(data):
            handle_response(data)

    except json.JSONDecodeError as e:
        print("Error al decodificar el JSON:", e)


def handle_timestamp(data):
    if data.get("timestamp"):
        data["timestamp"] = parser.isoparse(data["timestamp"])


def is_purchase_request(data):
    return "symbol" in data and data.get("kind") != "response"


def is_response(data):
    return data.get("kind") == "response"


def handle_purchase_request(data):
    request_data = {
        "request_id": data.get("request_id"),
        "group_id": data.get("group_id"),
        "quantity": data.get("quantity", 0),
        "symbol": data.get("symbol"),
        "operation": data.get("operation", "BUY"),
        "status": "PENDING",
        "applied": False,
    }
    collection_requests.insert_one(request_data)
    print(f"Request registrada: {request_data}")


def handle_response(data):
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
        handle_accepted_response(request_result, stock_result, user_transaction, timestamp)
    elif status == "REJECTED":
        handle_rejected_response(request_result, stock_result, user_transaction, timestamp)


def update_request_status(request_id, status, timestamp):
    collection_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": status, "timestamp": timestamp}}
    )
    print(f"Request actualizada: {request_id} | Nuevo estado: {status}")


def update_transaction_status(request_id, status, timestamp):
    transaction = collection_transactions.find_one({"request_id": request_id})
    if transaction:
        collection_transactions.update_one(
            {"request_id": request_id},
            {"$set": {"status": status, "timestamp": timestamp}}
        )
        print(f"Transacción actualizada: {request_id} | Nuevo estado: {status}")


def handle_accepted_response(request, stock, transaction, timestamp):
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

    if transaction:
        update_user_wallet(transaction["user_email"], -request["quantity"] * stock["price"], timestamp)

    log_event("BUY", request, stock["price"], timestamp)


def handle_rejected_response(request, stock, transaction, timestamp):
    if request["applied"]:
        new_quantity = stock["quantity"] + request["quantity"]
        collection_stocks.update_one(
            {"symbol": request["symbol"]},
            {"$set": {"quantity": new_quantity, "timestamp": timestamp}}
        )
        print(f"Stock actualizado: {request['symbol']} | Nueva cantidad: {new_quantity}")

        if transaction:
            update_user_wallet(transaction["user_email"], request["quantity"] * stock["price"], timestamp)
    else:
        collection_requests.update_one(
            {"request_id": request["request_id"]},
            {"$set": {"applied": True}}
        )


def update_user_wallet(user_id, balance_change, timestamp):
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
    client = mqtt.Client()

    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            client.loop_forever()
            # break
        except ConnectionRefusedError:
            print("Conexión rechazada. Reintentando en 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    start_mqtt_client()