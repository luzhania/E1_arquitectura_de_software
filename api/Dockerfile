FROM python:3.11-slim

WORKDIR .

COPY requirements.txt .
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# CMD ["newrelic-admin", "run-program", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
