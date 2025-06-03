import os
import json
import paho.mqtt.client as mqtt
from dateutil import parser
from pymongo import MongoClient
from dotenv import load_dotenv
import time

load_dotenv()

BROKER_HOST = os.getenv("MQTT_BROKER")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))  # Add default value
TOPIC = "stocks/updates"
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")

# Detect if running in CI environment
IS_CI = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

# Only connect to MongoDB if not in CI
if IS_CI:
    print("[BROKER_UPDATES] Running in CI environment, skipping database connection")
    client_mongo = None
    db = None
    collection_stocks = None
    collection_event_log = None
else:
    try:
        client_mongo = MongoClient(MONGO_URI)
        db = client_mongo["stocks_db"] 
        collection_stocks = db["current_stocks"]
        collection_event_log = db["event_log"]
        print("[BROKER_UPDATES] Connected to MongoDB")
    except Exception as e:
        print(f"[BROKER_UPDATES] Failed to connect to MongoDB: {e}")
        client_mongo = None

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker con código de resultado: {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    
    # Skip processing in CI environment
    if IS_CI:
        print("[BROKER_UPDATES] Running in CI, skipping message processing")
        return
        
    if collection_stocks is None:
        print("[BROKER_UPDATES] Database not available")
        return
        
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        if data.get("timestamp"):
            data["timestamp"] = parser.isoparse(data["timestamp"])

        kind = data.get("kind")
        symbol = data.get("symbol")

        if kind == "IPO":
            stock_data = {
                "symbol": data.get("symbol", "SYMBOL"),
                "quantity": data.get("quantity", 0),
                "price": data.get("price", 0),
                "longName": data.get("longName"),
                "timestamp": data.get("timestamp")
            }
            collection_stocks.update_one(
                {"symbol": symbol},
                {"$set": stock_data},
                upsert=True
            )
            print(f"[IPO] Acción registrada/actualizada: {stock_data}")
            event_data = {
                "type": data["kind"],
                "symbol": data["symbol"],
                "quantity": data["quantity"],
                "price": data["price"],
                "longName": data.get("longName", ""),
                "timestamp": data["timestamp"]
            }
            if collection_event_log is not None:
                collection_event_log.insert_one(event_data)
                print(f"[EVENT LOG] Registrada {data['kind']} de {data['symbol']}")

        elif kind == "EMIT":
            emit_quantity = data.get("quantity", 0)
            new_price = data.get("price", 0)
            timestamp = data.get("timestamp")

            result = collection_stocks.find_one({"symbol": symbol})
            if result:
                updated_quantity = result["quantity"] + float(emit_quantity)
                collection_stocks.update_one(
                    {"symbol": symbol},
                    {
                        "$set": {
                            "price": new_price,
                            "timestamp": timestamp
                            },
                        "$inc": {"quantity": emit_quantity}
                    }
                )
                print(f"[EMIT] Acción actualizada: {symbol} | Nuevo precio: {new_price}, Cantidad total: {updated_quantity}")

                event_data = {
                "type": data["kind"],
                "symbol": data["symbol"],
                "quantity": data["quantity"],
                "price": data["price"],
                "longName": data.get("longName", ""),
                "timestamp": data["timestamp"]
                }
                if collection_event_log is not None:
                    collection_event_log.insert_one(event_data)
                    print(f"[EVENT LOG] Registrada {data['kind']} de {data['symbol']}")

            else:
                new_stock = {
                    "symbol": symbol,
                    "quantity": emit_quantity,
                    "price": new_price,
                    "longName": data["longName"],
                    "timestamp": timestamp
                }
                collection_stocks.insert_one(new_stock)
                print(f"[UPDATE] Acción no encontrada. Se insertó con valores: {new_stock}")

        elif kind == "UPDATE":
            new_price = data.get("price", 0)
            result = collection_stocks.find_one({"symbol": symbol})
            if result:
                collection_stocks.update_one(
                    {"symbol": symbol},
                    {"$set": {"price": new_price,
                              "timestamp": data["timestamp"]}}
                )
                print(f"[UPDATE] Precio actualizado para {symbol}: {new_price}")
                event_data = {
                    "type": data["kind"],
                    "symbol": data["symbol"],
                    "quantity": 0,
                    "price": new_price,
                    "longName": "",
                    "timestamp": data["timestamp"]
                }
                if collection_event_log is not None:
                    collection_event_log.insert_one(event_data)
                    print(f"[EVENT LOG] Registrada {data['kind']} de {data['symbol']}")
            else:
                new_stock = {
                    "symbol": symbol,
                    "quantity": 0,
                    "price": new_price,
                    "longName": "",
                    "timestamp": data["timestamp"]
                }
                collection_stocks.insert_one(new_stock)
                print(f"[UPDATE] Acción no encontrada. Se insertó con valores por defecto: {new_stock}")

    except json.JSONDecodeError as e:
        print("Error al decodificar el JSON:", e)

def start_mqtt_client():
    # Skip MQTT connection in CI environment
    if IS_CI:
        print("[BROKER_UPDATES] Running in CI environment, skipping MQTT client")
        return
        
    if not BROKER_HOST:
        print("[BROKER_UPDATES] No MQTT broker configured")
        return
        
    client = mqtt.Client()

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