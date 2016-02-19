

REDIS_HOST = 'appido-redis'
BROKER_URL = 'redis://%s:6379/10' % REDIS_HOST
C_FORCE_ROOT = True
CELERY_RESULT_BACKEND = 'redis://appido-redis:6379/11'


# 7 days.
BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 3600 *
                            24 * 7, 'fanout_prefix': True, 'fanout_patterns': True}

CELERY_RESULT_PERSISTENT = True
CELERY_IGNORE_RESULT = False

CELERY_TASK_SERIALIZER = 'msgpack'
CELERY_RESULT_SERIALIZER = 'msgpack'
CELERY_ACCEPT_CONTENT = ['msgpack']
CELERY_TIMEZONE = 'Asia/Tehran'
CELERY_ENABLE_UTC = True
