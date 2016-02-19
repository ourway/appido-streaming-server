import redis
import os
from celery import Celery
from celery.result import AsyncResult
from celery import current_task
from kombu import Exchange, Queue


REDIS_HOST = 'appido-redis'
BROKER_URL = 'redis://%s:6379/10' % REDIS_HOST
CELERY_RESULT_BACKEND = 'redis://appido-redis:6379/11'

app = Celery('tasks', broker=BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.config_from_object('tasksConfig')

REDIS = redis.StrictRedis(host=REDIS_HOST, port=6379)

work_folder_tmp = os.path.abspath("video_tmp")
input_folder = os.path.abspath("video_tmp")
out_folder = '/storage/streaming'
bento4_path = '/Bento4'
admin_user = 'root'
admin_password = 'why_321'
salt = 'Do_of_09m'

if not os.path.isdir(out_folder):
    os.makedirs(out_folder)
