"""Streaming server configuration.

All environment-tunable values read os.environ with safe defaults so the same
code runs locally (host) and inside Docker:

  REDIS_HOST     default "localhost"  (Docker: "redis")
  REDIS_PORT     default 6379
  REDIS_DB_BROKER default 10
  REDIS_DB_BACKEND default 11
  BENTO4_PATH    default "revision/bento4" locally, "/Bento4" in Docker image
  STORAGE_ROOT   default "/storage"

Secrets (admin_password, salt) are legacy placeholders retained only because
utils.store prefixes redis keys with `salt`. They MUST be overridden in
production via ADMIN_PASSWORD and SALT env vars; never rely on the defaults.
"""

import os

import celery
import redis
from celery.result import AsyncResult  # noqa: F401  (re-exported by callers)
from kombu import Exchange, Queue  # noqa: F401  (re-exported by callers)


# --- Storage root and managed subdirectories -------------------------------
STORAGE_ROOT = os.environ.get("STORAGE_ROOT", "/storage")


def _absdir(path: str) -> str:
    p = os.path.abspath(path)
    os.makedirs(p, exist_ok=True)
    return p


work_folder_tmp = _absdir(os.path.join(STORAGE_ROOT, "video_tmp"))
input_folder = work_folder_tmp  # historical alias
out_folder = _absdir(os.path.join(STORAGE_ROOT, "streaming"))
uploads_folder = _absdir(os.path.join(STORAGE_ROOT, "uploads"))


# --- Bento4 / ffmpeg binaries ----------------------------------------------
# Local default points at the vendored bento4 under revision/. Docker images
# set BENTO4_PATH=/Bento4 (see Dockerfile.*).
bento4_path = os.path.abspath(os.environ.get("BENTO4_PATH", "revision/bento4"))


# --- Redis / Celery broker --------------------------------------------------
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB_BROKER = os.environ.get("REDIS_DB_BROKER", "10")
REDIS_DB_BACKEND = os.environ.get("REDIS_DB_BACKEND", "11")

BROKER_URL = os.environ.get(
    "BROKER_URL", "redis://%s:%s/%s" % (REDIS_HOST, REDIS_PORT, REDIS_DB_BROKER)
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    "redis://%s:%s/%s" % (REDIS_HOST, REDIS_PORT, REDIS_DB_BACKEND),
)

BROKER_TRANSPORT_OPTIONS = {"fanout_patterns": True, "fanout_prefix": True}


class Celery(celery.Celery):
    def on_configure(self):
        # Hook kept for any future logging/error-handler registration.
        pass


app = Celery("tasks", broker=BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.config_from_object("tasksConfig")


# Default Redis connection used by utils.store/restore/remove for ticket state.
REDIS_DB_STATE = int(os.environ.get("REDIS_DB_STATE", "0"))
REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_STATE)


# --- Legacy / security ------------------------------------------------------
# These values are placeholder defaults and MUST be overridden via env vars
# in any non-local deployment. They are not committed secrets.
admin_user = os.environ.get("ADMIN_USER", "root")
admin_password = os.environ.get("ADMIN_PASSWORD", "why_321")
salt = os.environ.get("SALT", "Doo_5b9m")

TIME_FORMAT = "%d/%m/%y %H:%M:%S"