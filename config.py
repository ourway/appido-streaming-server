import redis
from celery import Celery

BROKER_URL = 'redis://localhost:6379/1'

app = Celery('tasks', broker=BROKER_URL)

REDIS = redis.StrictRedis(host='localhost', port=6379, db=0)
work_folder_tmp = "/home/videostreamer/video_tmp"
input_folder = "/home/videostreamer/video_tmp"
out_folder = "/home/videostreamer/videos"
