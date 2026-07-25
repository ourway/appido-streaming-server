# Issue #1 — Audit and fix all bugs in appido-streaming-server

## EARS SPEC

- When the user submits a media_add_path request, the API shall return a Created response with ticket, webhook, and task id for both video and audio formats.
- If the request body is missing both url and filepath, then the API shall return 400.
- If the request specifies an unknown format, then the API shall return 400 instead of returning None implicitly.
- The system shall report encode progress and final mpd/m3u8 paths through the GET /streaming/api/key/<key> endpoint.
- When two encode jobs for the same source file run concurrently, the system shall deduplicate them via the md5 lock instead of corrupting shared state.
- When an encode step (fragmentation, resolutions, segmentation, HLS) fails, then the system shall mark the ticket FAILED, release the lock, and not leave partial state on disk.
- When a download or HTTP request fails, then utils.download_file shall raise a proper exception instead of calling bottle.abort inside a celery task (where abort is undefined).
- The system shall clean up the md5 lock on all exit paths, including exceptions and failures.
- When the celery worker restarts mid-encode, then the system shall not deadlock the md5 lock for 4 hours.
- The system shall expose the CORS headers on all responses including error responses.
- The system shall not log secrets (admin_password, salt, AUTH_SECRET) in source control or logs.
- When a webhook callback fails, then the system shall retry with backoff instead of silently printing 'connection erorr'.
- The Dockerfile and config shall agree on the bento4 path (/Bento4 in containers, configurable for local).
- The celery config shall use the lowercase setting names that the installed celery version understands, with consistent naming (CELERY_ENABLE_utc typo).
- The requirements.txt shall pin versions so the build is reproducible.

## Scope

The running system is the root-level files: `server.py`, `config.py`, `utils.py`,
`tasks/__init__.py`, `tasks/video_convertor_task.py`, `tasks/audio_convertor_task.py`,
plus deployment files (`Dockerfile.*`, `docker-compose.yml`, `requirements.txt`,
`run-streaming-*`, `tasksConfig.py`, `Makefile`).

The `revision/` directory is a separate in-progress rewrite with its own git
repository and is explicitly out of scope.