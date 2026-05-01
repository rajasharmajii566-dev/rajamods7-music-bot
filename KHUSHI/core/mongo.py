import sys
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI, MONGO_DB_NAME
from KHUSHI.logger_setup import LOGGER

if not MONGO_DB_URI:
    LOGGER(__name__).error("MONGO_DB_URI is not set!")
    sys.exit(1)

if not MONGO_DB_URI.startswith("mongodb"):
    LOGGER(__name__).error("Invalid MONGO_DB_URI! Must start with 'mongodb://' or 'mongodb+srv://'")
    sys.exit(1)

LOGGER(__name__).info("KHUSHI: Connecting to MongoDB...")

try:
    _client = AsyncIOMotorClient(
        MONGO_DB_URI,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        minPoolSize=5,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
    )
    mongodb = _client[MONGO_DB_NAME]
    LOGGER(__name__).info(f"KHUSHI: MongoDB connected. (DB: {MONGO_DB_NAME})")
except Exception as e:
    LOGGER(__name__).error(f"KHUSHI: MongoDB connection failed: {e}")
    sys.exit(1)
