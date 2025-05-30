from celery import Celery
import time

app = Celery("tasks", broker="redis://redis:6379/0")

@app.task(name="tasks.estimate_stock")
def estimate_stock(job_id, data):
    print(f"Estimando para job {job_id} con data: {data}")
    time.sleep(5)  # simula demora
    print(f"Estimación terminada para job {job_id}")
    return True
