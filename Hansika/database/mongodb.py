"""
database/mongodb.py
===================
MongoDB PyMongo client initialization and connection management.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from flask import g

from config.settings import get_config

logger = logging.getLogger(__name__)

# Global client to be reused across requests
_mongo_client = None

def init_mongo() -> MongoClient:
    """Initialize the MongoDB client connection."""
    global _mongo_client
    if _mongo_client is None:
        config = get_config()
        try:
            _mongo_client = MongoClient(
                config.MONGODB_URI,
                serverSelectionTimeoutMS=5000  # Fail fast if unavailable
            )
            # Send a ping to confirm a successful connection
            _mongo_client.admin.command('ping')
            logger.info("Successfully connected to MongoDB Atlas!")
        except Exception as e:
            logger.error("Could not connect to MongoDB Atlas: %s", e)
            raise e
    return _mongo_client

def get_db():
    """Get the specific database instance."""
    client = init_mongo()
    return client[get_config().MONGODB_DB_NAME]
