import os
import json
import uuid
from datetime import datetime, timezone
from dateutil import parser
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import requests  

load_dotenv()

BROKER_HOST    = os.getenv("MQTT_BROKER")
BROKER_PORT    = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_REQUESTS = "stocks/requests"
TOPIC_VALIDATION = "stocks/validation"
MQTT_USER      = os.getenv("MQTT_USER")
MQTT_PASSWORD  = os.getenv("MQTT_PASSWORD")

# Detect if running in CI environment
IS_CI = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

class MQTTManager:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.client = None
        self._connected = False
        
        # Skip MQTT connection in CI environment
        if IS_CI:
            print("[MQTT] Running in CI environment, skipping MQTT connection")
            return
            
        # Only try to connect if we have a broker host
        if BROKER_HOST:
            self._connect()
        else:
            print("[MQTT] No broker configured, running in mock mode")

    def _connect(self):
        """Try to connect to MQTT broker"""
        try:
            self.client = mqtt.Client()
            if MQTT_USER:
                self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
            self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            self.client.loop_start()
            self._connected = True
            print(f"[MQTT] Connected to {BROKER_HOST}:{BROKER_PORT}")
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")
            self._connected = False

    def publish_buy_request(self, transaction_id: str, symbol: str, quantity: int, deposit_token: str = "") -> str:
        if not self._connected:
            print(f"[MQTT] Mock: Would publish BUY request {transaction_id}")
            return
            
        payload = {
            "request_id": transaction_id,
            "group_id": self.group_id,
            "quantity": quantity,
            "symbol": symbol,
            "operation": "BUY",
        }
        self.client.publish(TOPIC_REQUESTS, json.dumps(payload), qos=1)

        print(f"[MQTT] Publicada solicitud BUY: {payload}")

        #aun no se envia al JobMaster, se hace en el momento de la validación de la compra
        #enviar_estimacion_jobmaster(self.group_id, symbol, quantity) 
    
    def publish_validation(self, request_id: str, status_transaction: str, deposit_token: str = "") -> None:
        if not self._connected:
            print(f"[MQTT] Mock: Would publish validation {request_id}")
            return
            
        payload = {
            "request_id": request_id,
            "timestamp": str(datetime.now(timezone.utc).isoformat()),
            "status": status_transaction,
            "reason": "",
            "deposit_token": deposit_token
        }
        self.client.publish(TOPIC_VALIDATION, json.dumps(payload), qos=0)
        print(f"[MQTT] Published validation: {payload}")



    def enviar_estimacion_jobmaster(self,user_id, stock_symbol, quantity, price, request_id):
        try:
            res = requests.post("https://3.130.207.58/job", json={
                "user_id": user_id,
                "stock_symbol": stock_symbol,
                "quantity": quantity,
                "price": price,
                "request_id": request_id
            })
            data = res.json()
            print("[JobMaster] Estimación enviada, job_id:", data["job_id"])
            return data["job_id"]
        except Exception as e:
            print("[JobMaster] Error al enviar estimación:", e)
            return None


mqtt_manager = MQTTManager(group_id="27")
