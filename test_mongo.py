# test_mongo.py  — save this in your 4G-main folder and run it
import certifi
import pymongo
from dotenv import load_dotenv
import os

load_dotenv()

url = os.getenv("MONGODB_URL")
print("Connecting to:", url[:50], "...")

try:
    client = pymongo.MongoClient(url, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
    client.admin.command('ping')
    print("✅ Connected successfully!")
    print("Databases:", client.list_database_names())
except Exception as e:
    print("❌ Failed:", e)