# Celery 4+ configuration (lowercase setting names).
# 7-day visibility timeout commented out; uncomment to enable.
# broker_transport_options = {
#     'visibility_timeout': 3600 * 24 * 7,
#     'fanout_prefix': True,
#     'fanout_patterns': True,
# }

result_persistent = True
task_send_sent_event = True
# task_ignore_result = False
task_store_errors_even_if_ignored = True
task_track_started = True

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Tehran"
enable_utc = True