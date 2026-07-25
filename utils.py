"""Persistence and download helpers for the streaming server.

`store`/`restore`/`remove` keep per-ticket encode status in Redis (namespaced by
`config.salt`). `download_file` fetches a URL into the input folder while
reporting progress to the same ticket store. `md5_for_file` hashes a file
without loading it all into memory.
"""

import hashlib
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests
import ujson as json

from config import REDIS as r
from config import TIME_FORMAT, input_folder, salt


class DownloadError(Exception):
    """Raised when a remote download cannot be started or completed."""


@dataclass
class Status:
    status: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None
    info: object = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def store(key, obj):
    """Store a complex object in redis, namespaced by `salt`."""
    if isinstance(obj, dict):
        load_ = dict(obj)
    else:
        load_ = json.loads(obj.to_json())
    load_["datetime"] = datetime.now(timezone.utc).strftime(TIME_FORMAT)
    r.set(salt + key, json.dumps(load_))
    r.expire(salt + key, 24 * 3600)  # expire key after 24h


def restore(key):
    """Get a complex object from redis, or None if absent."""
    data = r.get(salt + key)
    if data is not None:
        return json.loads(data)
    return None


def remove(key):
    """Delete a complex object from redis."""
    r.delete(salt + key)


def download_file(url: str, ticket: str) -> str:
    """Download `url` into the input folder, reporting progress to `ticket`.

    Returns the local filename. Raises DownloadError on any failure (so celery
    can mark the task FAILED instead of calling bottle.abort, which is not
    available outside the web context).
    """
    local_filename = os.path.join(input_folder, os.path.basename(url))
    status = Status(status="Start Downloading")
    store(ticket, status)

    try:
        h = requests.head(url, allow_redirects=True, timeout=30)
        h.raise_for_status()
    except requests.RequestException as exc:
        status.status = "Failed"
        status.info = "Cannot reach %s: %s" % (url, exc)
        store(ticket, status)
        raise DownloadError(status.info)

    clength = h.headers.get("Content-Length")
    if not clength:
        # No Content-Length (e.g. chunked transfer). Download anyway, but flag it.
        print("Warning: no Content-Length for %s" % url)
        clength_int = None
    else:
        clength_int = int(clength)
        print("Downloading %s" % url)

    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        part = 0
        chunk_size = 2 ** 16
        with open(local_filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if not chunk:  # filter keep-alive chunks
                    continue
                if clength_int:
                    percent = (part * chunk_size * 100.0) / clength_int
                    status.status = "Downloading"
                    status.info = "%.2f percent" % percent
                    store(ticket, status)
                f.write(chunk)
                part += 1
    except (requests.RequestException, OSError) as exc:
        status.status = "Failed"
        status.info = "Download error for %s: %s" % (url, exc)
        store(ticket, status)
        # Best-effort cleanup of a partial download.
        try:
            os.remove(local_filename)
        except OSError:
            pass
        raise DownloadError(status.info)

    status.status = "Download Finished"
    status.info = ""
    store(ticket, status)
    return local_filename


def md5_for_file(path, block_size: int = 2 ** 20) -> str:
    """Return the hex md5 of the file at `path` without loading it whole."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            md5.update(block)
    return md5.hexdigest()