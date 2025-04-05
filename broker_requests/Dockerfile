FROM python:3.9-slim

WORKDIR /broker_requests

COPY requirements.txt /broker_requests/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /broker_requests/

CMD ["python", "mqtt_requests.py"]
