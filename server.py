#!/usr/bin/env python
"""appido streaming server - HTTP API.

Endpoints:

  GET  /streaming/ping                        -> health check
  GET  /streaming/api/key/<key>                -> read ticket status from redis
  POST /streaming/api/revoke/<task_id>         -> revoke a celery task + drop key
  GET  /streaming/api/status/<task_id>         -> celery task status
  POST /streaming/api/video_upload             -> chunked upload (flow.js) -> video
  POST /streaming/api/audio_upload             -> chunked upload (flow.js) -> audio
  POST /streaming/api/media_add_path           -> enqueue encode from url/filepath
"""

import logging
import os
import uuid

import bottle
from bottle import abort, post, request, response, route, run, static_file

import config
import tasks
from utils import remove, restore, store

logger = logging.getLogger(__name__)

application = bottle.Bottle()
application.catchall = False


@application.hook("after_request")
def after():
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    response.headers[
        "Access-Control-Allow-Headers"
    ] = "Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token"


@application.route("/<:re:.*>", method="OPTIONS")
def cors_preflight():
    """Answer CORS preflight for any path. after_request adds the headers."""
    response.status = 204
    return ""


@application.get("/streaming/api/key/<key>")
def get_key(key):
    return dict(result=restore(key))


@application.post("/streaming/api/revoke/<task_id>")
def revoke(task_id):
    config.app.control.revoke(task_id)
    remove(task_id)
    return dict(status(task_id))


@application.get("/streaming/api/status/<task_id>")
def status(task_id):
    res = config.app.AsyncResult(task_id)
    return dict(result=res.status)


@application.post("/streaming/api/video_upload")
def video_upload():
    """Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize',
    'flowChunkNumber', 'flowIdentifier', 'flowRelativePath', 'flowTotalSize',
    'flowFilename']
    """
    temp_path = os.path.join(config.uploads_folder, request.forms.flowIdentifier)
    # first lets get the file
    with open(temp_path, "ab") as target:
        chunk = request.files.file.file.read(int(request.forms.flowCurrentChunkSize))
        target.write(chunk)

    if request.forms.flowTotalChunks == request.forms.flowChunkNumber:
        response.status = 201
        webhook = request.forms.get("webhook")
        # set name to file
        ext = request.forms.flowFilename.split(".")[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + "." + ext
        os.rename(temp_path, os.path.join(config.work_folder_tmp, new_file_name))
        task = tasks.video_convert.delay(new_file_name, ticket)
        return dict(message="Created", ticket=ticket, webhook=webhook, task=str(task))
    else:
        response.status = 202
        return dict(message="Accepted")


@application.post("/streaming/api/audio_upload")
def audio_upload():
    """Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize',
    'flowChunkNumber', 'flowIdentifier', 'flowRelativePath', 'flowTotalSize',
    'flowFilename']
    """
    temp_path = os.path.join(config.uploads_folder, request.forms.flowIdentifier)
    with open(temp_path, "ab") as target:
        chunk = request.files.file.file.read(int(request.forms.flowCurrentChunkSize))
        target.write(chunk)

    if request.forms.flowTotalChunks == request.forms.flowChunkNumber:
        response.status = 201
        webhook = request.forms.get("webhook")
        ext = request.forms.flowFilename.split(".")[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + "." + ext
        os.rename(temp_path, os.path.join(config.work_folder_tmp, new_file_name))
        task = tasks.audio_convert.delay(new_file_name, ticket)
        return dict(message="Created", ticket=ticket, webhook=webhook, task=str(task))
    else:
        response.status = 202
        return dict(message="Accepted")


@application.post("/streaming/api/media_add_path")
def media_add_path():
    if not request.json:
        abort(400)
    filepath = request.json.get("filepath", None)
    _format = request.json.get("format", "video")
    correlator = request.json.get("correlator")
    url = request.json.get("url", None)
    webhook = request.json.get("webhook")
    # Note: previously `% filepath or url` had wrong precedence and would
    # log `None` when filepath was falsy even if url was set.
    logger.error("received a request on %s", filepath or url)
    if not (url or filepath):
        abort(400)
    ticket = uuid.uuid4().hex
    if (filepath and os.path.isfile(filepath)) or url:
        if not filepath:
            fpath = url
        else:
            fpath = filepath
        if _format == "video":
            task = tasks.video_convert.delay(
                fpath,
                ticket,
                webhook=webhook,
                abspath=filepath is not None,
                url=url is not None,
                correlator=correlator,
            )
        elif _format == "audio":
            task = tasks.audio_convert.delay(
                fpath,
                ticket,
                webhook=webhook,
                abspath=filepath is not None,
                url=url is not None,
                correlator=correlator,
            )
        else:
            abort(400, "unknown format: %s" % _format)
            return  # abort() raises HTTPError; this is defensive
        response.status = 201
        return dict(message="Created", ticket=ticket, webhook=webhook, task=str(task))
    # filepath given but not a real file, and no url
    abort(400)


@application.get("/streaming/ping")
def hello():
    return dict(message="PONG")


if __name__ == "__main__":
    bottle.run(app=application, host="0.0.0.0", port=3000)