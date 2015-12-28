import redis
from celery import Celery
import os

REDIS_HOST = '192.168.99.100'
BROKER_URL = 'redis://%s:6379/1' % REDIS_HOST
app = Celery('tasks', broker=BROKER_URL)
REDIS = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0)
work_folder_tmp = os.path.abspath("video_tmp")
input_folder = os.path.abspath("video_tmp")
out_folder = os.path.abspath("videos")
bento4_path = os.path.abspath(os.path.join(os.getenv('HOME'), 'Bento4'))
admin_user = 'admin'
admin_password = 'why_321'
salt = 'Do_of_09m'
