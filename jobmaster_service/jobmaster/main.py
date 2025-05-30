from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
from celery import Celery
from fastapi.middleware.cors import CORSMiddleware 

app = FastAPI()

# ⬇️ CORS middleware aquí
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

celery_app = Celery("jobmaster", broker="redis://redis:6379/0")

class JobData(BaseModel):
    user_id: str
    stock_symbol: str
    quantity: int

@app.post("/job")
def create_job(data: JobData):
    job_id = str(uuid.uuid4())
    celery_app.send_task("tasks.estimate_stock", args=[job_id, data.dict()])
    return {"job_id": job_id}

@app.get("/heartbeat")
def heartbeat():
    return True
