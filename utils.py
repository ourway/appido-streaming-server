
import ujson as json
import uuid
from config import REDIS as r
from config import salt

class Status(object):
    status = None
    progress = 0
    message = None
    info = None

def store(key, obj):
    """Store a complex object in redis"""
    r.set(salt+key, json.dumps(obj))


def restore(key):
    """Get a complex object from redis"""
    data = r.get(salt+key)
    if data:
        return json.loads(data)
