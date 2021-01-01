import hashlib
import os
import uuid
from datetime import datetime

import requests
import ujson as json
from dataclasses import dataclass, asdict

from config import REDIS as r
from config import input_folder, salt, TIME_FORMAT


@dataclass
class Status:
    status: str = None
    progress: int = 0
    message: str = None
    info: str = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def store(key, obj):
    """Store a complex object in redis"""
    if isinstance(obj, dict):
        load_ = obj
    else:
        _obj = obj.to_json()
        load_ = json.loads(_obj)
    load_["datetime"] = datetime.strftime(datetime.utcnow(), TIME_FORMAT)
    r.set(salt + key, json.dumps(load_))
    r.expire(salt + key, 24 * 3600)  # expire key


def restore(key):
    """Get a complex object from redis"""
    data = r.get(salt + key)
    if data:
        return json.loads(data)


def remove(key):
    """Get a complex object from redis"""
    r.delete(salt + key)


import os

import requests


def download_file(url, ticket):
    local_filename = os.path.join(input_folder, url.split("/")[-1])
    status = Status()

    status.status = "Start Downloading"

    store(ticket, status)
    # NOTE the stream=True parameter
    h = requests.head(url)
    clength = h.headers["Content-Length"]
    if not clength:
        print("Cant get Content Length")
        status.status = "Failed"
        status.info = "Can not download %s " % url
        store(ticket, status)
        abort(400)
    else:
        print(("Downloading %s" % url))
        clength = int(clength)

    r = requests.get(url, stream=True)
    part = 0
    with open(local_filename, "wb") as f:
        chunk_size = 2 ** 16
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:  # filter out keep-alive new chunks
                percent = ((part * chunk_size) * 100) / clength
                status.status = "Downloading"
                status.info = "%s percent " % percent
                store(ticket, status)
                print(("%s Percent" % percent))
                f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
                part += 1
                # f.flush() commented by recommendation from J.F.Sebastian

    status.status = "Download Finished"
    status.info = ""
    store(ticket, status)
    return local_filename


def md5_for_file(f, block_size=2 ** 20):
    f = open(f, "rb")
    md5 = hashlib.md5()
    while True:
        data = f.read(block_size)
        if not data:
            break
        md5.update(data)
    return md5.hexdigest()
