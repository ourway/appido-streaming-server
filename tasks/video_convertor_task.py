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
from utils import store, restore, md5_for_file, Status, remove
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

def create_different_resulations(src, fmd5,  min_bw=64, max_bw=1024, bw_count=8):
    s = time.time()
    #logger.info('Started resulations process of %s' % src)
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-resulations'%fmd5)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    cmd = ['nice', '-n', '20', 'python2', os.path.join(config.bento4_path,
                                                       'utils', 'mp4-dash-encode.py'), '-v', '-f', '-b', str(bw_count), '-d',
                                                       '--select-streams' , '0,1',
                                                       '-e', '-pix_fmt yuv420p',
                                                       '-m', str(min_bw), '-n', str(max_bw),
                                                       src, '-o', out_dir]
    print(' '.join(cmd))
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        client.captureMessage('ERROR on craete different resulations for file %s' % src)

def hls_segments(src, fmd5):
    s = time.time()
    out_dir = "{tmp}/{dir_name}/hls".format(tmp=config.out_folder,
                                        dir_name='%s-stream'%fmd5)
 
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
        wdir = os.getcwd()
        fin_dir = os.path.join(out_dir, speed)
        if not os.path.isdir(fin_dir):
            os.makedirs(fin_dir)
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
                                        dir_name='%s-stream'%fmd5)
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
        return out_dir
    else:
        client.captureMessage('ERROR on create segments of %s' % src)

@app.task
def video_convert(filename, ticket, min_bw=64, max_bw=1024, bw_count=8,
                  webhook=None, abspath=False, url=True, correlator=None):

    s=time.time()
    logger.debug('Started streaming process of %s' % filename)
    status = Status()
    if abspath:
        '''I am going to copy the file, cause the original file might be deleted by client'''
        tmpfilepath=os.path.join(config.work_folder_tmp, '_tmp' + os.path.basename(filename))
        shutil.copyfile(filename, tmpfilepath)
        fullfilename = tmpfilepath
    elif url:
        fullfilename = download_file(filename, ticket)
    else:
        fullfilename = "{dir}/{file}".format(dir=config.input_folder,
                                             file=filename)

    fmd5 = md5_for_file(fullfilename)
    lockKey = 'STMSERVER_LOCK_'+ fmd5
    if not r.get(lockKey):
        r.set(lockKey, 'LOCK')
        r.expire(lockKey, 3600*4)  ## 4 hours lock
 
        target_mpd='{of}/{file}/rashavas.mpd'.format(file='%s-stream'%fmd5, of=config.out_folder)
        target_m3u8='{of}/{file}/hls/rashavas.m3u8'.format(file='%s-stream'%fmd5, of=config.out_folder)
     

        if os.path.isfile(target_mpd) and os.path.isfile(target_m3u8):
            status.status = 'Ready'
            if correlator: r.set(correlator, status.status)
            store(ticket, status)
            status.info = dict(
                mpd=target_mpd,
                m3u8=target_m3u8,
            )
     
            store(fmd5, dict(ticket=ticket, status=status))
            return status
     

        status.status = 'STARTED'
        if correlator: r.set(correlator, status.status)

        store(ticket, status)
        status.status = 'FRAGMENTATION'
        if correlator: r.set(correlator, status.status)
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        frag = fragment_file(fullfilename, fmd5)
        if frag == None:
            status.status = 'FAILED'
            if correlator: r.set(correlator, status.status)
            status.info = 'fragmantation failed'
            store(ticket, status)
            store(fmd5, dict(ticket=ticket, status=status))
            return
        status.status = 'RESULATION PROCESS'
        if correlator: r.set(correlator, status.status)
        status.info = 'MAKE {count} resulations from {min} to {max}'.format(
            count=bw_count, min=min_bw, max=max_bw)
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        res = create_different_resulations(frag, fmd5,  min_bw, max_bw, bw_count)
        if res == None:
            status.status = 'FAILED'
            if correlator: r.set(correlator, status.status)
            status.info = 'resulations steps failed'
            store(ticket, status)
            return
        status.status = 'SEGMENTATION STARTED'
        if correlator: r.set(correlator, status.status)
        if not os.path.isfile(target_mpd):
            seg = create_segments(res, fmd5)

        if not os.path.isfile(target_m3u8):
            hls_segments(res, fmd5)
        # cleanup
        shutil.rmtree(res, ignore_errors=True)
        os.remove(frag)
        os.remove(tmpfilepath)

        status.status = 'Ready'
        if correlator: r.set(correlator, status.status)
        status.info = dict(
            mpd=target_mpd,
            m3u8=target_m3u8,
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
    else:
        return 'LOCK:%s'%lockKey
