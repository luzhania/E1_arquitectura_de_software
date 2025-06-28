FROM python:3.11-slim

# 1. Carpeta de trabajo clara
WORKDIR /app

# 2. Copiar solo requirements para cachear pip
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 3. Copiar todo el código (incluido newrelic.ini)
COPY . .

# (Si prefieres la copia explícita, descomenta la línea siguiente)
# COPY newrelic.ini /app/newrelic.ini

EXPOSE 8000

# 4. Arrancar con New Relic
CMD ["sh", "-c", "NEW_RELIC_CONFIG_FILE=/newrelic.ini newrelic-admin run-program uvicorn main:app --host 0.0.0.0 --port 8000"]
