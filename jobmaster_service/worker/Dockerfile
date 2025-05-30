FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install fastapi uvicorn celery redis pydantic
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]

