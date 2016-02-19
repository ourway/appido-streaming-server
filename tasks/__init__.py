import config
from config import app

from celery.result import AsyncResult


from celery import Celery
from tasks.video_convertor_task import video_convert
from tasks.audio_convertor_task import audio_convert
