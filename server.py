#!/usr/bin/env python


__authors = 'Masoud Mazarei and Farsheed Ashouri'

__copyright = 'Rashavas telecom @ 2015-2016'

__description = '''
Thanks for masoud for doing all hard work
'''


import bottle
from bottle import route, run, static_file, post, request, response, abort
import os
import uuid
#from convert_task import convert
import tasks
import config
from utils import restore
import requests

application = application = bottle.Bottle()


@application.hook('after_request')
def after():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


@application.get('/api/key/<key>')
def get_key(key):
    return dict(result=restore(key))


@application.post('/api/video_upload')
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


@application.post('/api/audio_upload')
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




@application.post('/api/video_add_path')
def video_add_path():
        fpath = None
        filepath = request.json.get('filepath', None)
        _format = request.json.get('format', 'video')
        url = request.json.get('url', None)
        webhook = request.json.get('webhook')
        if not (url or filepath):
            abort(400)
        ticket = uuid.uuid4().hex
        if (filepath and os.path.isfile(filepath)) or url:
            if not filepath:
                fpath=url
            else:
                fpath = filepath
            if _format=='video':
                task = tasks.video_convert.delay(fpath, ticket, webhook=webhook,
                            abspath=filepath!=None, url=url!=None)
            elif _format=='audio':
                task = tasks.audio_convert.delay(fpath, ticket, webhook=webhook,
                            abspath=filepath!=None, url=url!=None)
            response.status = 201
            return dict(message='Created', ticket=ticket, webhook=webhook,
                        task=str(task))


#@application.route('<filename:re:.*>')
# def send_image(filename):
#    return static_file(filename, root='.')


@application.route('/static/<filename:path>')
def static_serve(filename):
    return static_file(filename, root='.')


@application.get('/ping')
def hello():
    return dict(message='PONG')


if __name__ == '__main__':
    bottle.run(app=application,
               host='0.0.0.0',
               port=3000)
