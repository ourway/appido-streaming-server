#!/usr/bin/env python


__author = 'Farsheed Ashouri. Thanks to msd for the original idea'
__copyright = 'Rashavas telecom @ 2015-2016'


#import ipdb
import bottle
from bottle import route, run, static_file, post, request, response, abort
import os
import uuid
#from convert_task import convert
import tasks
import shutil
import config
from utils import store, restore, remove,  md5_for_file
import requests
import logging
logger = logging.getLogger(__name__)


#app = config.app

application = application = bottle.Bottle()


@application.hook('after_request')
def after():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers[
        'Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers[
        'Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


@application.get('/streaming/api/key/<key>')
def get_key(key):
    return dict(result=restore(key))


@application.get('/streaming/api/revoke/<task_id>')
def revoke(task_id):
    config.app.control.revoke(task_id)
    remove(task_id)
    return dict(status(task_id))


@application.get('/streaming/api/status/<task_id>')
def status(task_id):
    res = config.app.AsyncResult(task_id)
    return dict(result=res.status)


@application.post('/streaming/api/video_upload')
def video_upload():
    """ Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize',
    'flowChunkNumber', 'flowIdentifier', 'flowRelativePath', 'flowTotalSize',
    'flowFilename']
    """
    temp_path = os.path.join('uploads', request.forms.flowIdentifier)
    ''' first lets get the file'''
    with open(temp_path, 'ab') as target:
        chunk = request.files.file.file.read(
            int(request.forms.flowCurrentChunkSize))
        target.write(chunk)
    ''' now, lets save it in a good place'''

    if request.forms.flowTotalChunks == request.forms.flowChunkNumber:
        response.status = 201
        webhook = request.forms.get('webhook')
        # set name to file
        ext = request.forms.flowFilename.split('.')[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + '.' + ext
        os.rename(temp_path, os.path.join(
            config.work_folder_tmp, new_file_name))
        task = tasks.video_convert.delay(new_file_name, ticket)
        return dict(message='Created', ticket=ticket, webhook=webhook,
                    task=str(task))
    else:
        response.status = 202
        return dict(message='Accepted')


@application.post('/streaming/api/audio_upload')
def audio_upload():
    """ Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize',
    'flowChunkNumber', 'flowIdentifier', 'flowRelativePath', 'flowTotalSize',
    'flowFilename']
    """
    temp_path = os.path.join('uploads', request.forms.flowIdentifier)
    ''' first lets get the file'''
    with open(temp_path, 'ab') as target:
        chunk = request.files.file.file.read(
            int(request.forms.flowCurrentChunkSize))
        target.write(chunk)
    ''' now, lets save it in a good place'''

    if request.forms.flowTotalChunks == request.forms.flowChunkNumber:
        response.status = 201
        webhook = request.forms.get('webhook')

        ext = request.forms.flowFilename.split('.')[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + '.' + ext
        # set name to file
        os.rename(temp_path, os.path.join(
            config.work_folder_tmp, new_file_name))
        task = tasks.audio_convert.delay(new_file_name, ticket)
        return dict(message='Created', ticket=ticket, webhook=webhook,
                    task=str(task))
    else:
        response.status = 202
        return dict(message='Accepted')


@application.post('/streaming/api/media_add_path')
def media_add_path():
    fpath = None
#        ipdb.set_trace()
    filepath = request.json.get('filepath', None)
    _format = request.json.get('format', 'video')
    url = request.json.get('url', None)
    webhook = request.json.get('webhook')
    logger.error('recived a request on %s'%filepath or url)
    if not (url or filepath):
        abort(400)
    ticket = uuid.uuid4().hex
    if (filepath and os.path.isfile(filepath)) or url:
        if not filepath:
            fpath = url
        else:
            fpath = filepath
            fmd5 = md5_for_file(fpath)
            remd5 = restore(fmd5)
            if remd5:
                old_ticket = remd5.get('ticket')
                if old_ticket and get_key(old_ticket)['result']:
                    logger.error('file with same md5 available. ticket: %s'%old_ticket)
                    return dict(message='Available', info=get_key(old_ticket)['result'], ticket=old_ticket)
        if _format == 'video':
            task = tasks.video_convert.delay(fpath, ticket, webhook=webhook,
                                             abspath=filepath != None, url=url != None)
        elif _format == 'audio':
            task = tasks.audio_convert.delay(fpath, ticket, webhook=webhook,
                                             abspath=filepath != None, url=url != None)
        response.status = 201
        return dict(message='Created', ticket=ticket, webhook=webhook,
                    task=str(task))


#@application.route('<filename:re:.*>')
# def send_image(filename):
#    return static_file(filename, root='.')


#@application.route('/streaming/static/<filename:path>')
#def static_serve(filename):
#    return static_file(filename, root='.')


@application.get('/streaming/ping')
def hello():
    return dict(message='PONG')


if __name__ == '__main__':
    bottle.run(app=application,
               host='0.0.0.0',
               port=3000)
