FROM python:3.9-slim

WORKDIR /broker_validation

COPY requirements.txt /broker_validation/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /broker_validation/

CMD ["python", "mqtt_validation.py"]
