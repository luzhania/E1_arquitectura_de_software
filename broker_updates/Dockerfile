FROM python:3.9-slim

WORKDIR /broker_updates

COPY requirements.txt /broker_updates/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /broker_updates/

CMD ["python", "mqtt_updates.py"]
