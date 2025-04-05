import os
import json
import paho.mqtt.client as mqtt
from dateutil import parser
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()


BROKER_HOST = os.getenv("MQTT_BROKER")
BROKER_PORT = int(os.getenv("MQTT_PORT"))
TOPIC = "stocks/updates"
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["stocks_db"] 
collection = db["updates"]####

def on_connect(client, userdata, flags, rc):
    print(f"Conectado al broker con código de resultado: {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        data["timestamp"] = parser.isoparse(data["timestamp"])
        collection.insert_one(data)
        print("Datos procesados:", data)
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