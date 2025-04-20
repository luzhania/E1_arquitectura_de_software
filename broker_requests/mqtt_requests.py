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
collection_requests = db["requests"]####
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
        

        if data.get("symbol"):
            request_data = {
                "request_id": data["request_id"],
                "group_id": data["group_id"], 
                "quantity": data["quantity"],
                "symbol": data["symbol"],
                "operation": data["operation"],
                "status": "PENDING",
                "applied": False,
            }
            collection_requests.insert_one(request_data)
            print(f"Request registrada: {request_data}")

        elif data.get("status"):
            request_id = data["request_id"]
            status = data["status"]
            timestamp = data["timestamp"]
            request_result = collection_requests.find_one({"request_id": request_id})
            if request_result:
                collection_requests.update_one(
                    {"request_id": request_id},
                    {
                        "$set": {
                            "status": status,
                            "timestamp": timestamp
                            },
                    }
                )
                print(f"Request actualizada: {request_id} | Nuevo estado: {status}")
                stock_result = collection_stocks.find_one({"symbol": request_result["symbol"]})
                if status == "ACCEPTED":
                    # // Actualizar stock en la colección de stocks, decrementando la cantidad si es posible
                    if stock_result:
                        new_quantity = stock_result["quantity"] - request_result["quantity"]
                        if new_quantity >= 0:
                            collection_stocks.update_one(
                                {"symbol": request_result["symbol"]},
                                {
                                    "$set": {
                                        "quantity": new_quantity,
                                        "timestamp": timestamp
                                    }
                                }
                            )
                            collection_requests.update_one(
                                {"request_id": request_id},
                                {
                                    "$set": {
                                        "applied": True
                                        },
                                }
                            )
                            print(f"Stock actualizado: {request_result['symbol']} | Nueva cantidad: {new_quantity}")
                        else:
                            print(f"No hay suficiente cantidad de {request_result['symbol']} para completar la solicitud.")
                    else:
                        print(f"Stock {request_result['symbol']} no encontrado.")
                elif status == "REJECTED":
                    # // Actualizar stock en la colección de stocks, incrementando la cantidad
                    if stock_result:
                        if request_result["applied"]:
                            new_quantity = stock_result["quantity"] + request_result["quantity"]
                            collection_stocks.update_one(
                                {"symbol": request_result["symbol"]},
                                {
                                    "$set": {
                                        "quantity": new_quantity,
                                        "timestamp": timestamp
                                    }
                                }
                            )
                            print(f"Stock actualizado: {request_result['symbol']} | Nueva cantidad: {new_quantity}")
                        else:
                            collection_requests.update_one(
                                {"request_id": request_id},
                                {
                                    "$set": {
                                        "applied": True
                                        },
                                }
                            )
                    else:
                        print(f"Stock {request_result['symbol']} no encontrado.")



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