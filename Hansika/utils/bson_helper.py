"""
utils/bson_helper.py
====================
Helpers for serializing MongoDB BSON types (like ObjectId and datetime).

Research Component: SLSL Recognition System — Objective 4
"""

import json
from datetime import datetime
from bson import ObjectId

from flask.json.provider import DefaultJSONProvider

class MongoJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder for standard json.dumps.
    """
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class MongoJSONProvider(DefaultJSONProvider):
    """
    Flask 2.2+ JSON provider that handles BSON ObjectIds.
    """
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

def object_id_to_str(doc: dict) -> dict:
    """Convert _id ObjectId to string in a document, returning a new dict."""
    if not doc:
        return doc
    new_doc = doc.copy()
    if '_id' in new_doc:
        new_doc['_id'] = str(new_doc['_id'])
    return new_doc

def str_to_object_id(id_str: str) -> ObjectId:
    """Safely convert a string to an ObjectId."""
    try:
        return ObjectId(id_str)
    except Exception:
        return None
