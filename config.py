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

work_folder_tmp = '/storage/video_tmp'
input_folder = '/storage/video_tmp'
out_folder = '/storage/streaming'

for each in [work_folder_tmp, input_folder, out_folder]:
    if not os.path.isdir(each):
        os.makedirs(each)

bento4_path = '/Bento4'
admin_user = 'root'
admin_password = 'why_321'
salt = 'Doo_5b9m'
