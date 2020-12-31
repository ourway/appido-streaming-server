from celery.result import AsyncResult

import config
from config import Celery, app
from tasks.audio_convertor_task import audio_convert
from tasks.video_convertor_task import video_convert
