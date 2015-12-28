#!/usr/bin/env python


__authors = 'Masoud Mazarei and Farsheed Ashouri'

__copyright = 'Rashavas telecom @ 2015-2016'

__description = '''
Thanks for masoud for doing all hard work
'''


import bottle
from bottle import route, run, static_file, post, request, response
import os
import uuid
#from convert_task import convert
import tasks
import config

r = config.REDIS
application = application = bottle.Bottle()


@application.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'


@application.get('/api/key/<key>')
def get_key(key):
    return r.get(key)


@application.post('/api/upload')
def video_upload():
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
        ext = request.forms.flowFilename.split('.')[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + '.' + ext
        os.rename(temp_path, os.path.join(
            config.work_folder_tmp, new_file_name))
        tasks.video_convert.delay(new_file_name, ticket)
        return dict(message='OK', ticket=ticket)
    else:
        response.status = 202
        return dict(message='Partial')


@application.post('/api/audio_upload')
def audio_upload():
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


        ext = request.forms.flowFilename.split('.')[-1]
        ticket = uuid.uuid4().hex
        new_file_name = ticket + '.' + ext
 
        # set name to file
        os.rename(temp_path, os.path.join(
            config.work_folder_tmp, new_file_name))
        tasks.audio_convert.delay(new_file_name, ticket)
        return dict(message='OK', ticket=ticket)
    else:
        response.status = 202
        return dict(message='Partial')


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
