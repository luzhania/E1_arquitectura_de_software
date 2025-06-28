FROM python:3.11-slim

WORKDIR .

COPY requirements.txt .
COPY . .
COPY newrelic.ini /app/newrelic.ini
# Asumiendo que el archivo newrelic.ini ya está en el directorio raíz del proyecto
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

#CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["sh", "-c", "NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program uvicorn main:app --host 0.0.0.0 --port 8000"]

# Se asume que newrelic.ini ya fue generado y está junto al código


