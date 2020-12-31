import os

import celery
import redis

#from raven.contrib.celery import register_signal, register_logger_signal
#from raven.handlers.logging import SentryHandler
client = os
#client = raven.Client('https://29b51be9165b4678a16d998c59141c10:e31e0e292ccf41c39251263cb318d202@sentry.appido.ir/6')
#handler = SentryHandler(client)


class Celery(celery.Celery):
    def on_configure(self):
        pass
        # register a custom filter to filter out duplicate logs
        #register_logger_signal(client)
        # hook into the Celery error handler
        #register_signal(client)

from celery import current_task
from celery.result import AsyncResult
from kombu import Exchange, Queue

#import logging.handlers


BROKER_TRANSPORT_OPTIONS = {'fanout_patterns': True, 'fanout_prefix': True}
REDIS_HOST = '127.0.0.1'
BROKER_URL = 'redis://%s:6379/10' % REDIS_HOST
CELERY_RESULT_BACKEND = 'redis://%s:6379/11' % REDIS_HOST

app = Celery('tasks', broker=BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.config_from_object('tasksConfig')

REDIS = redis.StrictRedis(host=REDIS_HOST, port=6379)

work_folder_tmp = os.path.abspath('/storage/video_tmp')
input_folder = os.path.abspath('/storage/video_tmp')
out_folder = os.path.abspath('/storage/streaming')

for each in [work_folder_tmp, input_folder, out_folder]:
    if not os.path.isdir(each):
        os.makedirs(each)

bento4_path = os.path.abspath('/Bento4')
admin_user = 'root'
admin_password = 'why_321'
salt = 'Doo_5b9m'

#smtp_handler = logging.handlers.SMTPHandler(mailhost=("mail.rashavas.com", 587),
#                                            fromaddr="no-reply@rashavas.com", 
#                                            toaddrs="ashouri@rashavas.com",
#                                            credentials=('no-reply@rashavas.com','killMyCatPlease'),
#                                            subject=u"Streaming Server Error!")

