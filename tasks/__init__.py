from config import app
from celery import Celery
from video_convertor_task import video_convert
from audio_convertor_task import audio_convert
