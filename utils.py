
import ujson as json
import uuid
from config import REDIS as r
from config import salt, input_folder
import os
import requests

class Status(object):
    status = None
    progress = 0
    message = None
    info = None

def store(key, obj):
    """Store a complex object in redis"""
    r.set(salt+key, json.dumps(obj))


def restore(key):
    """Get a complex object from redis"""
    data = r.get(salt+key)
    if data:
        return json.loads(data)



import requests
import os


def download_file(url):
    local_filename = os.path.join(input_folder, url.split('/')[-1])

    # NOTE the stream=True parameter
    h = requests.head(url)
    clength = h.headers['Content-Length']
    if not clength:
        print('Cant get Content Length')
        abort(400)
    else:
        print('Downloading %s' % url)
        clength = int(clength)

    r = requests.get(url, stream=True)
    part = 0
    with open(local_filename, 'wb') as f:
        chunk_size = 2**16
        for chunk in r.iter_content(chunk_size=chunk_size): 
            if chunk: # filter out keep-alive new chunks
                percent = ((part*chunk_size) * 100 ) / clength
                print('%s Percent' % percent)
                f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
                part+=1
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename

