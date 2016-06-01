import redis
import os
from celery import Celery
from celery.result import AsyncResult
from celery import current_task
from kombu import Exchange, Queue
import logging.handlers


BROKER_TRANSPORT_OPTIONS = {'fanout_patterns': True, 'fanout_prefix': True}
REDIS_HOST = 'localhost'
BROKER_URL = 'redis://%s:6379/10' % REDIS_HOST
CELERY_RESULT_BACKEND = 'redis://%s:6379/11' % REDIS_HOST

app = Celery('tasks', broker=BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.config_from_object('tasksConfig')

REDIS = redis.StrictRedis(host=REDIS_HOST, port=6379)

work_folder_tmp = os.path.abspath('video_tmp')
input_folder = os.path.abspath('video_tmp')
out_folder = os.path.abspath('streaming')

for each in [work_folder_tmp, input_folder, out_folder]:
    if not os.path.isdir(each):
        os.makedirs(each)

bento4_path = os.path.abspath('/Users/rodmena/Bento4')
admin_user = 'root'
admin_password = 'why_321'
salt = 'Doo_5b9m'

smtp_handler = logging.handlers.SMTPHandler(mailhost=("mail.rashavas.com", 587),
                                            fromaddr="no-reply@rashavas.com", 
                                            toaddrs="ashouri@rashavas.com",
                                            credentials=('no-reply@rashavas.com','killMyCatPlease'),
                                            subject=u"Streaming Server Error!")

