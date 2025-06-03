import os
from pymongo import MongoClient

from dotenv import load_dotenv
load_dotenv()

# If database.py connects to MongoDB on import
IS_CI = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

if IS_CI:
    print("[DB] Running in CI environment, skipping database connection")
    # Set up mock database or skip connection

def get_db():
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mongo_uri)
    return client["stocks_db"]
