#!/usr/bin/env python

import bottle
from bottle import route, run, static_file, post, request, response
import os
import uuid
#from convert_task import convert
import tasks
from config import REDIS
app = application = bottle.Bottle()


@app.get('/api/key/<key>')
def get_key(key):
    return REDIS.get(key)


@app.post('/api/upload')
def upload():
    """ Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize', 'flowChunkNumber', 'flowIdentifier',
    'flowRelativePath', 'flowTotalSize', 'flowFilename']
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
        # set name to file
        new_file_name = str(uuid.uuid4())
        os.rename(temp_path, '/home/videostreamer/video_tmp/' + new_file_name)
        tasks.video_convert.delay(new_file_name)
        return dict(message='OK', ticket=new_file_name)
    else:
        response.status = 202
        return dict(message='Partial')


@app.post('/api/audio_upload')
def upload():
    """ Will get streaming files via flow.js
    ['flowTotalChunks', 'flowChunkSize', 'flowCurrentChunkSize', 'flowChunkNumber', 'flowIdentifier',
    'flowRelativePath', 'flowTotalSize', 'flowFilename']
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
        # set name to file
        new_file_name = str(uuid.uuid4())
        os.rename(temp_path, '/home/videostreamer/video_tmp/' + new_file_name)
        tasks.audio_convert.delay(new_file_name)
        return dict(message='OK', ticket=new_file_name)
    else:
        response.status = 202
        return dict(message='Partial')


@app.route('<filename:re:.*>')
def send_image(filename):
    return static_file(filename, root='.')


@app.route('/hello')
def hello():
    return "Hello World!"


if __name__ == '__main__':
    bottle.run(app=app,
               host='0.0.0.0',
               port=8080)
