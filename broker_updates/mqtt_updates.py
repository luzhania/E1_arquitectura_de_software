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
TOPIC = "stocks/updates"
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["stocks_db"] 
collection_stocks = db["current_stocks"]####

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker con código de resultado: {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        if data.get("timestamp"):
            data["timestamp"] = parser.isoparse(data["timestamp"])
        kind = data.get("kind")
        symbol = data.get("symbol")

        if kind == "IPO":
            stock_data = {
                "symbol": data["symbol"],
                "quantity": data["quantity"],
                "price": data["price"],
                "longName": data["longName"],
                "timestamp": data["timestamp"]
            }
            collection_stocks.update_one(
                {"symbol": symbol},
                {"$set": stock_data},
                upsert=True
            )
            print(f"[IPO] Acción registrada/actualizada: {stock_data}")

        elif kind == "EMIT":
            emit_quantity = data["quantity"]
            new_price = data["price"]
            timestamp = data["timestamp"]

            result = collection_stocks.find_one({"symbol": symbol})
            if result:
                updated_quantity = result["quantity"] + emit_quantity
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
            new_price = data["price"]
            result = collection_stocks.find_one({"symbol": symbol})
            if result:
                collection_stocks.update_one(
                    {"symbol": symbol},
                    {"$set": {"price": new_price,
                              "timestamp": data["timestamp"]}}
                )
                print(f"[UPDATE] Precio actualizado para {symbol}: {new_price}")
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