import redis
from celery import Celery
import os

REDIS_HOST = 'appido-redis'
BROKER_URL = 'redis://%s:6379/2' % REDIS_HOST
C_FORCE_ROOT = True
CELERY_RESULT_BACKEND = 'redis://appido-redis:6379/3'

CELERY_TASK_SERIALIZER = 'msgpack'
CELERY_RESULT_SERIALIZER = 'msgpack'
CELERY_ACCEPT_CONTENT = ['msgpack']
CELERY_TIMEZONE = 'Asia/Tehran'
CELERY_ENABLE_UTC = True
C_FORCE_ROOT = True

app = Celery('tasks', broker=BROKER_URL, backend=CELERY_RESULT_BACKEND)
REDIS = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0)


work_folder_tmp = os.path.abspath("video_tmp")
input_folder = os.path.abspath("video_tmp")
out_folder = '/storage/streaming'
bento4_path = '/Bento4'
admin_user = 'root'
admin_password = 'why_321'
salt = 'Do_of_09m'

if not os.path.isdir(out_folder):
	os.makedirs(out_folder)
