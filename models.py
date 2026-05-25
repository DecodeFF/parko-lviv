# -*- coding: utf-8 -*-
"""
Database layer (Repository pattern).
Encapsulates all MongoDB operations for coordinates.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime


class DatabaseManager:
    """
    Singleton-pattern manager for MongoDB connection.
    Ensures only one client instance exists across the application.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, uri='mongodb://localhost:27017/', db_name='kursova_tracker', timeout_ms=3000):
        if hasattr(self, '_initialized'):
            return
        self._uri = uri
        self._db_name = db_name
        self._timeout_ms = timeout_ms
        self._client = None
        self._initialized = True

    @property
    def client(self):
        """Lazy-initialize the MongoDB client."""
        if self._client is None:
            self._client = MongoClient(self._uri, serverSelectionTimeoutMS=self._timeout_ms)
        return self._client

    @property
    def db(self):
        """Return the database object."""
        return self.client[self._db_name]

    def is_connected(self):
        """Check if MongoDB is reachable."""
        try:
            self.client.admin.command('ping')
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError):
            return False

    def __repr__(self):
        return f"DatabaseManager(uri='{self._uri}', db='{self._db_name}')"


class CoordinateRepository:
    """
    Repository class for coordinate CRUD operations.
    Follows the Repository pattern to separate data access from business logic.
    """

    def __init__(self, db_manager: DatabaseManager, collection_name='coordinates'):
        self._db_manager = db_manager
        self._collection_name = collection_name

    @property
    def _collection(self):
        """Return the MongoDB collection."""
        return self._db_manager.db[self._collection_name]

    def insert(self, latitude: float, longitude: float) -> dict:
        """Insert a new coordinate record and return the created document info."""
        timestamp = datetime.now()
        result = self._collection.insert_one({
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": timestamp
        })
        return {
            "id": str(result.inserted_id),
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": timestamp
        }

    def get_latest(self) -> dict | None:
        """Return the most recent coordinate, or None if empty."""
        doc = self._collection.find_one(sort=[("timestamp", -1)])
        if doc:
            return self._serialize(doc)
        return None

    def get_all(self) -> list[dict]:
        """Return all coordinates ordered by timestamp descending."""
        docs = self._collection.find(sort=[("timestamp", -1)])
        return [self._serialize(doc) for doc in docs]

    def delete_all(self) -> int:
        """Delete all coordinate records. Returns the number deleted."""
        result = self._collection.delete_many({})
        return result.deleted_count

    def count(self) -> int:
        """Return the total number of coordinate records."""
        return self._collection.count_documents({})

    @staticmethod
    def _serialize(doc: dict) -> dict:
        """Convert a MongoDB document to a JSON-friendly dictionary."""
        ts = doc.get("timestamp", "")
        return {
            "id": str(doc["_id"]),
            "latitude": doc["latitude"],
            "longitude": doc["longitude"],
            "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts)
        }

    def __repr__(self):
        return f"CoordinateRepository(collection='{self._collection_name}')"
