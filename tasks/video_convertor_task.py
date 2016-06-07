#!/usr/bin/env python
import subprocess
import time
import os
import sys
import uuid
import glob
from subprocess import Popen, PIPE
from lxml import etree
import shutil
from utils import store, restore, md5_for_file, Status
import requests
from requests.exceptions import ConnectionError
import config
import logging
from config import app, client
import re
import json
from utils import download_file
import hashlib

logger = logging.getLogger(__name__)
#logger.addHandler(config.smtp_handler)



r = config.REDIS


pat = re.compile(
    r'frame= *([\d]+) *fps= *([\d]+) *q=([\d\.]+) +size= *([\d]+[\w]{2}) +time=([\d\.\:]+) *bitrate= *([\d\.]+[\w\/]+)')


class Progress(object):
    frame = None
    fps = None
    quality = None
    size = None
    timecode = None
    bitrate = None


def fragment_file(src, fmd5):
    s = time.time()
    tmp_file =fmd5 + '-fragment.mp4'
    fullpath = "{tmp}/{file}.mp4".format(
        tmp=config.work_folder_tmp, file=tmp_file)
    cmd = ["nice", os.path.join(config.bento4_path, 'bin',
                                "mp4fragment"),
                                #'--index', 
                                #'--fragment-duration', str(fd), 
                                src, fullpath]
    p = subprocess.Popen(cmd)
    p.wait()
    #import ipdb;ipdb.set_trace()
    if p.returncode == 0:
        return fullpath
    else:
        client.captureMessage('ERROR on fragmentation of file: %s' % src)

def create_different_resulations(src, fmd5,  min_bw=64, max_bw=1024, bw_count=10):
    s = time.time()
    #logger.info('Started resulations process of %s' % src)
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-resulations'%fmd5)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    cmd = ['nice', '-n', '20', 'python2', os.path.join(config.bento4_path,
                                                       'utils', 'mp4-dash-encode.py'), '-v', '-f', '-b', str(bw_count), '-d',
                                                       #'--select-streams' , '0',
                                                       '-m', str(min_bw), '-n', str(max_bw),
                                                       src, '-o', out_dir]
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        print(cmd)
        client.captureMessage('ERROR on craete different resulations for file %s' % src)

def hls_segments(src, out_dir):
    s = time.time()
    out_dir = os.path.join(out_dir, 'hls')
    try:
        os.makedirs(out_dir)
    except (FileExistsError) as e:
        client.captureException()
    files = glob.glob(src + '/*mp4')
    m3u8 = ['#EXTM3U']
    fmt_ = '#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH={bw}'
    for f in files:
        filename = os.path.basename(f)
        speed = filename.replace('.mp4', '').replace('video_', '')
        fin_dir = os.path.join(out_dir, speed)
        wdir = os.getcwd()
        try:
            os.mkdir(fin_dir)
        except (FileExistsError) as e:
            client.captureException()
        os.chdir(fin_dir)
        cmd = ['nice', os.path.join(config.bento4_path, 'bin', 'mp42hls'), f]
        p = subprocess.Popen(cmd)
        p.wait()
        m3u8.append(fmt_.format(bw=int(float(speed) * 1024)))
        m3u8.append('{speed}/stream.m3u8'.format(speed=speed))
        if p.returncode != 0:
            return None
    os.chdir(wdir)
    rashavas_m3u8 = open(os.path.join(out_dir, 'rashavas.m3u8'), 'w')
    rashavas_m3u8.write('\r\n'.join(m3u8))
    rashavas_m3u8.close()
    return out_dir


def create_segments(src, fmd5):
    s=time.time()
    out_dir = "{tmp}/{dir_name}".format(tmp=config.out_folder,
                                        dir_name='%s-segments'%fmd5)
    mpd_file = 'rashavas.mpd'
    cmd = ["nice", "python2",  os.path.join(config.bento4_path, 'utils',
                                            'mp4-dash.py'), '-f', '-v', 
                                            '--use-segment-list',
                                            '--use-segment-timeline',
                                            "--mpd-name=" + mpd_file, 
           "--exec-dir=%s/bin" % config.bento4_path]
    cmd.extend(glob.glob(src + "/*mp4"))
    cmd.extend(["-o", out_dir])
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        f = open(out_dir + '/' + mpd_file)
        xmlstr = f.read()
        f.close()
        tree = etree.fromstring(xmlstr)
        comments = tree.xpath('//comment()')
        for c in comments:
            p = c.getparent()
            p.remove(c)
        f = open(out_dir + '/' + mpd_file, 'wb')
        f.write(etree.tostring(tree))
        f.close()
        hls_segments(src, out_dir)
        return out_dir
    else:
        client.captureMessage('ERROR on create segments of %s' % src)

@app.task
def video_convert(filename, ticket, min_bw=64, max_bw=1024, bw_count=10,
                  webhook=None, abspath=False, url=True):
    s=time.time()
    logger.debug('Started streaming process of %s' % filename)
    status = Status()
    if abspath:
        fullfilename = filename
    elif url:
        fullfilename = download_file(filename, ticket)
    else:
        fullfilename = "{dir}/{file}".format(dir=config.input_folder,
                                             file=filename)

    fmd5 = md5_for_file(fullfilename)
    '''Now I need to check hash of file'''


    status.status = 'STARTED'
    store(ticket, status)
    status.status = 'FRAGMENTATION'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    frag = fragment_file(fullfilename, fmd5)
    if frag == None:
        status.status = 'FAILED'
        status.info = 'fragmantation failed'
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        return
    status.status = 'RESULATION PROCESS'
    status.info = 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw)
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    res = create_different_resulations(frag, fmd5,  min_bw, max_bw, bw_count)
    if res == None:
        status.status = 'FAILED'
        status.info = 'resulations steps failed'
        store(ticket, status)
        return
    status.status = 'SEGMENTATION STARTED'
    seg = create_segments(res, fmd5)
    print('segments')
    if not seg:
        status.status = 'FAILED'
        status.info = 'segmentation failed'
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        return

    # cleanup
    shutil.rmtree(res, ignore_errors=True)
    os.remove(frag)

    status.status = 'SUCCESS'
    status.info = dict(
        mpd='{of}/{file}/rashavas.mpd'.format(file='%s-stream'%fmd5, of=config.out_folder),
        m3u8='{of}/{file}/hls/rashavas.m3u8'.format(file='%s-stream'%fmd5, of=config.out_folder),
    )
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    if webhook:
        try:
            requests.post(webhook)
        except ConnectionError:
            client.captureException()

    logger.debug('Straming process of %s ended in %f(3) seconds' % (filename, time.time()-s))
    return 'OK'
