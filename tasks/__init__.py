from config import app
from celery.result import AsyncResult

BROKER_URL = 'redis://localhost:6379/0'

CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'

CELERY_TASK_SERIALIZER = 'msgpack'
CELERY_RESULT_SERIALIZER = 'msgpack'
CELERY_ACCEPT_CONTENT=['msgpack']
CELERY_TIMEZONE = 'Asia/Tehran'
CELERY_ENABLE_UTC = True


from celery import Celery
from video_convertor_task import video_convert
from audio_convertor_task import audio_convert
