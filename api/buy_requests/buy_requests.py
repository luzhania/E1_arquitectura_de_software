import os
import json
import uuid
from datetime import datetime, timezone
from dateutil import parser
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER_HOST    = os.getenv("MQTT_BROKER")
BROKER_PORT    = int(os.getenv("MQTT_PORT"), "9000")
TOPIC_REQUESTS = "stocks/requests"
TOPIC_VALIDATION = "stocks/validation"
MQTT_USER      = os.getenv("MQTT_USER")
MQTT_PASSWORD  = os.getenv("MQTT_PASSWORD")

class MQTTManager:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.client = mqtt.Client()
        if MQTT_USER:
            self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        self.client.loop_start()

    def publish_buy_request(self, transaction_id: str, symbol: str, quantity: int, deposit_token: str = "") -> str:
        """
        Publica una solicitud de compra en stocks/requests y
        devuelve el request_id (UUIDv4).
        """
        payload = {
            "request_id": transaction_id,
            "group_id": self.group_id,
            # "timestamp": str(datetime.now(timezone.utc).isoformat()),
            "quantity": quantity,
            "symbol": symbol,
            # "stock_origin": 0,
            "operation": "BUY",
            # "deposit_token": deposit_token
        }
        self.client.publish(TOPIC_REQUESTS, json.dumps(payload), qos=1)
        print(f"[MQTT] Publicada solicitud BUY: {payload}")
    
    def publish_validation(self, request_id: str, status_transaction: str, deposit_token: str = "") -> None:
        """
        Publica una validación de compra en stocks/validation.
        """
        payload = {
            "request_id": request_id,
            "timestamp": str(datetime.now(timezone.utc).isoformat()),
            "status": status_transaction,
            "reason":"",
            "deposit_token": deposit_token
        }
        self.client.publish(TOPIC_VALIDATION, json.dumps(payload), qos=0)
        print(f"[MQTT] Publicada validación: {payload}")

mqtt_manager = MQTTManager(group_id="27")
