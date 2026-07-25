from config import app  # re-export so `celery -A tasks worker` finds the app
from tasks.audio_convertor_task import audio_convert
from tasks.video_convertor_task import video_convert

__all__ = ["app", "audio_convert", "video_convert"]