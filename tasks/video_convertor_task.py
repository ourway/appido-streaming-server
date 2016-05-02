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
from config import app
import re
from utils import download_file
import hashlib

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
    if p.returncode == 0:
        return fullpath
    else:
        raise ValueError('ERROR on fragmentation')


def create_different_resulations(src, fmd5,  min_bw=64, max_bw=1024, bw_count=10):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-resulations'%fmd5)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    cmd = ['nice', '-n', '20', 'python2', os.path.join(config.bento4_path,
                                                       'utils', 'mp4-dash-encode.py'), '-v', '-f', '-b', str(bw_count), 
                                                       '-m', str(min_bw), '-n', str(max_bw),
                                                       src, '-o', out_dir]
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        raise ValueError('ERROR on craete different resulations')


def hls_segments(src, out_dir):
    out_dir = os.path.join(out_dir, 'hls')
    os.mkdir(out_dir)
    files = glob.glob(src + '/*mp4')
    m3u8 = ['#EXTM3U']
    fmt_ = '#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH={bw}'

    for f in files:
        filename = os.path.basename(f)
        speed = filename.replace('.mp4', '').replace('video_', '')
        fin_dir = os.path.join(out_dir, speed)
        wdir = os.getcwd()
        os.mkdir(fin_dir)
        os.chdir(fin_dir)
        cmd = ['nice', os.path.join(config.bento4_path, 'bin', 'mp42hls'), f]
        p = subprocess.Popen(cmd)
        p.wait()
        m3u8.append(fmt_.format(bw=int(float(speed) * 1024)))
        m3u8.append('{speed}/stream.m3u8'.format(speed=speed))
        if p.returncode != 0:
            os.chdir(wdir)
            return None
        else:
            os.chdir(wdir)
    rashavas_m3u8 = open(os.path.join(out_dir, 'rashavas.m3u8'), 'w')
    rashavas_m3u8.write('\r\n'.join(m3u8))
    rashavas_m3u8.close()
    return out_dir


def create_segments(src, fmd5):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-segments'%fmd5)
    mpd_file = 'rashavas.mpd'
    cmd = ["nice", "python2",  os.path.join(config.bento4_path, 'utils',
                                            'mp4-dash.py'), '-f', '-v', "--mpd-name=" + mpd_file, 
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
        raise ValueError('ERROR on create segments')


@app.task
def video_convert(filename, ticket, min_bw=64, max_bw=1024, bw_count=10,
                  webhook=None, abspath=False, url=True):
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
    if not seg:
        status.status = 'FAILED'
        status.info = 'segmentation failed'
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        return

    # cleanup
    shutil.rmtree(res)
    os.remove(frag)

    fin_folder = "{dir}/{file}".format(dir=config.out_folder, file='%s-stream'%fmd5)
    try:
        status.status = 'PREPARING'
        status.info = 'Moving files to final folders'
        store(ticket, status)
        shutil.move(seg, fin_folder)
    except:
        status.status = 'FAILED'
        status.info = 'failed in preparing final folders'
        store(ticket, status)
        return

    status.status = 'SUCCESS'
    status.info = dict(
        mpd='/storage/streaming/{file}/rashavas.mpd'.format(file='%s-stream'%fmd5),
        m3u8='/storage/streaming/{file}/hls/rashavas.m3u8'.format(file='%s-stream'%fmd5),
    )
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    if webhook:
        try:
            requests.post(webhook)
        except ConnectionError:
            pass
    return 'OK'
