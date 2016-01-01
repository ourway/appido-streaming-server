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
from utils import store, Status

import config
from config import app

r = config.REDIS




def fragment_file(src):
    tmp_file = uuid.uuid4().hex
    fullpath = "{tmp}/{file}.mp4".format(
        tmp=config.work_folder_tmp, file=tmp_file)
    cmd = ["nice", os.path.join(config.bento4_path, 'bin',
                        "mp4fragment"), src, fullpath]
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return fullpath
    else:
        return None


def create_different_resulations(src, min_bw=64, max_bw=1024, bw_count=5):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name=uuid.uuid4().hex)
    cmd = ['nice', '-n', '20', 'python2.7', os.path.join(config.bento4_path,
            'utils', 'mp4-dash-encode.py'), '-v', '-b', str(bw_count), '-m',
           str(min_bw), '-n', str(max_bw), src, '-o', out_dir]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1)
    x = Status()
    with p.stdout:
        for line in iter(p.stdout.readline, b''):
            x.status = line
            #store('FUNNY', x)
            #print line,
    p.wait() # wait for the subprocess to exit

    if p.returncode == 0:
        return out_dir
    else:
        return None


def create_segments(src):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name=uuid.uuid4().hex)
    mpd_file = 'rashavas.mpd'
    cmd = ["nice", "python2.7",  os.path.join(config.bento4_path, 'utils',
            'mp4-dash.py'), "--mpd-name=" + mpd_file,
           "--exec-dir=%s/bin" % config.bento4_path]
    cmd.extend(glob.glob(src + "/*mp4"))
    cmd.extend(["-o", out_dir])
    print "\n Creating Segments \n"
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
        f = open(out_dir + '/' + mpd_file, 'w')
        f.write(etree.tostring(tree))
        f.close()
        return out_dir
    else:
        return None


@app.task
def video_convert(filename, ticket, min_bw=64, max_bw=1024, bw_count=10):
    status = Status()
    fullfilename = "{dir}/{file}".format(
        dir=config.input_folder, file=filename)
    status.status = 'STARTED'
    store(ticket, status)
    status.status = 'FRAGMENTATION'
    store(ticket, status)
    frag = fragment_file(fullfilename)
    if frag == None:
        status.status = 'FAILED'
        status.info = 'fragmantation failed'
        store(ticket, status)
        return
    status.status = 'RESULATION PROCESS'
    status.info = 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw)
    store(ticket, status)
    res = create_different_resulations(frag, min_bw, max_bw, bw_count)
    if res == None:
        status.status = 'FAILED'
        status.info = 'resulations steps failed'
        store(ticket, status)
        return
    status.status = 'SEGMENTATION STARTED'
    seg = create_segments(res)
    if not seg:
        status.status = 'FAILED'
        status.info = 'segmentation failed'
        store(ticket, status)
        return

    ## cleanup
    shutil.rmtree(res)
    os.remove(frag)

    fin_folder = "{dir}/{file}".format(dir=config.out_folder, file=ticket)
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
    status.info = fin_folder
    store(ticket, status)
