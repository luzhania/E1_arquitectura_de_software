FROM python:3.9-slim

WORKDIR /broker_info

COPY requirements.txt /broker_info/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /broker_info/

CMD ["python", "mqtt_info.py"]
