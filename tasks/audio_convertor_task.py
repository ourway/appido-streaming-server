#!/usr/bin/env python
import subprocess
import time
import os
import sys
import uuid
import glob
import copy
from lxml import etree
import shutil
from utils import store, restore, md5_for_file, Status
import config
from config import app
import requests
from requests.exceptions import ConnectionError
from utils import download_file
import re
#import ipdb
r = config.REDIS


def execute(command):
    popen = psutil.Popen(command, stdout=subprocess.PIPE, bufsize=16)
    lines_iterator = iter(popen.stdout.readline, b"")
    for line in lines_iterator:
        print(line)  # yield line


def fragment_file(src_dir):
    for i in os.listdir(src_dir):

        cmd = [os.path.join(config.bento4_path, 'bin', "mp4fragment"),
               os.path.join(src_dir, i), os.path.join(src_dir, 'fragged_%s' % i)]
        # print(cmd)
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode == 0:
            pass
        else:
            return None
    return src_dir


def hls_segments(src, out_dir):
    out_dir = os.path.join(out_dir, 'hls')
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.mkdir(out_dir)
    files = glob.glob(src + '/frag*mp4')
    m3u8 = ['#EXTM3U']
    fmt_ = '#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH={bw}'

    for f in files:
        filename = os.path.basename(f)
        speed = filename.replace('.mp4', '').replace('fragged_', '')
        fin_dir = os.path.join(out_dir, speed)
        wdir = os.getcwd()
        os.mkdir(fin_dir)
        os.chdir(fin_dir)
        cmd = ['nice', '-n', '20',
               os.path.join(config.bento4_path, 'bin', 'mp42hls'), f]
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


def create_different_resulations(src, fmd5, min_bw=64, max_bw=1024, bw_count=10):
    bw_ranges = [min_bw + i * (min_bw + max_bw) /
                 bw_count for i in range(bw_count)]
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-resulations'%fmd5)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.mkdir(out_dir)
    cmd = ['ffmpeg', '-i', src]
    for i in [['-vn', '-b:a', '%sk' % x, "{out_dir}/{filename}.mp4".format(out_dir=out_dir, filename=x)] for x in bw_ranges]:
        cmd.extend(i)
    print("call execute-------")
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        return None


def create_segments(src_dir, fmd5):
    #import ipdb
    # ipdb.set_trace()
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name='%s-segments'%fmd5)
    for i in glob.glob(os.path.join(src_dir, 'frag*mp4')):
        cmd = ["python2", os.path.join(config.bento4_path, "utils", "mp4-dash.py"),
               "--exec-dir=%s/bin" % config.bento4_path, i, '-o', i + '_out']
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode == 0:
            pass
        else:
            return None

    return src_dir


@app.task
def audio_convert(filename, ticket, min_bw=64, max_bw=1024, bw_count=10,
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
    status.status = 'STARTED'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    r.set(ticket, 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw))
    res = create_different_resulations(fullfilename, fmd5, min_bw, max_bw, bw_count)
    print(("+" * 20))
    print(("different resulation dir :", res))
    print(("+" * 20))
    if res == None:
        status.status = 'FAILED - RESULATION STEP '
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        return
    status.status = 'FRAGMENTATION STARTED'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    frag = fragment_file(res)

    if frag == None:
        status.status = 'FAILED - FRAGMENTATION STEP'
        store(ticket, status)
        return
    status.status = 'SEGMENTATION STARTED'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    seg = create_segments(frag, fmd5)
    # ipdb.set_trace()
    if not seg:
        status.status = 'FAILED - SEGMENTATION FAILED'
        store(ticket, status)
        return

    fin_folder = os.path.join(config.work_folder_tmp, '%s-stream'%fmd5)

    if os.path.isdir(fin_folder):
        shutil.rmtree(fin_folder)
    os.mkdir(fin_folder)
    bw_ranges = list(set([min_bw + i * (min_bw + max_bw) /
                          bw_count for i in range(bw_count)]))
    mpd_file = []
    status.status = 'AGRIGATION STARTED'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))

    for i in bw_ranges:
        _tmp = os.path.join(fin_folder, str(i))
        # if not os.path.isdir(_tmp):
        #    os.mkdir(_tmp)
        os.rename(os.path.join(
            seg, 'fragged_{bitrate}.mp4_out'.format(bitrate=i)), _tmp)
        with open(os.path.join(_tmp, 'stream.mpd')) as f:
            mpd_file.append([i, f.read()])
        # shutil.rmtree(_tmp)
    final_xml = etree.fromstring(mpd_file[0][1])
    repr_sec = final_xml[1][1][1]
    repr_sec.attrib['id'] = os.path.join(
        str(mpd_file[0][0]), repr_sec.attrib['id'])
    for i in range(1, len(mpd_file)):
        _tmpxml = etree.fromstring(mpd_file[i][1])
        rpsec = _tmpxml[1][1][1]
        rpsec.attrib['id'] = os.path.join(
            str(mpd_file[i][0]), rpsec.attrib['id'])
        (final_xml[1][1]).append(rpsec)

    final_xml.remove(final_xml[0])

    with open(os.path.join(fin_folder, 'rashavas.mpd'), 'wb') as g:
        g.write(etree.tostring(final_xml))

    # ipdb.set_trace()
    status.status = 'HLS Stream creation Started'
    store(ticket, status)
    if hls_segments(frag, fin_folder) is None:
        status.status = 'creation HLS Stream Failed'
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status))
        exit(1)

    status.status = 'TRANSFER ASSETS TO STREAMER SERVER'
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    shutil.move(fin_folder, os.path.join(config.out_folder, '%s-stream'%fmd5))

    # shutil.rmtree(res)
    # os.remove(frag)

    status.status = 'SUCCESS'
    status.info = dict(
        mpd='/storage/streaming/{file}-stream/rashavas.mpd'.format(file=fmd5),
        m3u8='/storage/streaming/{file}-stream/hls/rashavas.m3u8'.format(file=fmd5),
    )
    store(ticket, status)
    store(fmd5, dict(ticket=ticket, status=status))
    if webhook:
        try:
            requests.post(webhook)
        except ConnectionError:
            pass
    return 'OK'


# audio_convert('2mp3',bw_count=2,min_bw=256,max_bw=512);
