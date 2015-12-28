#!/usr/bin/env python
import subprocess
import time
import os
import sys
import uuid
import glob
from lxml import etree
import shutil
#import redis

import config
from config import app

r = config.REDIS


def execute(command):
    popen = psutil.Popen(command, stdout=subprocess.PIPE, bufsize=16)
    lines_iterator = iter(popen.stdout.readline, b"")
    for line in lines_iterator:
        print(line)  # yield line


def fragment_file(src):
    tmp_file = uuid.uuid4().hex
    fullpath = "{tmp}/{file}.mp4".format(
        tmp=config.work_folder_tmp, file=tmp_file)
    cmd = [os.path.join(config.bento4_path, 'bin',
                        "mp4fragment"), src, fullpath]
    print cmd
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return fullpath
    else:
        return None


def create_different_resulations(src, min_bw=64, max_bw=1024, bw_count=5):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name=uuid.uuid4().hex)
    cmd = ['python2.7', os.path.join(config.bento4_path, 'utils', 'mp4-dash-encode.py'), '-v',
           '-b', str(bw_count), '-m', str(min_bw), '-n', str(max_bw), src, '-o', out_dir]
    print "\n Creating Different Resulations \n"
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        return None


def create_segments(src):
    out_dir = "{tmp}/{dir_name}".format(tmp=config.work_folder_tmp,
                                        dir_name=uuid.uuid4().hex)
    mpd_file = 'rashavas.mpd'
    cmd = ["python2.7",  os.path.join(config.bento4_path, 'utils', 'mp4-dash.py'),
           "--mpd-name=" + mpd_file, "--exec-dir=%s/bin" % config.bento4_path]
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
    fullfilename = "{dir}/{file}".format(
        dir=config.input_folder, file=filename)
    r.set(ticket, 'STARTED')
    r.set(ticket, 'FRAGMENTATION')
    frag = fragment_file(fullfilename)
    if frag == None:
        r.set(ticket, 'FAILED - FRAGMENTATION FAILED')
        return
    r.set(ticket, 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw))
    res = create_different_resulations(frag, min_bw, max_bw, bw_count)
    if res == None:
        r.set(ticket, 'FAILED - RESULATION STEP ')
        return
    r.set(ticket, 'SEGMENTATION STARTED')
    seg = create_segments(res)
    if not seg:
        r.set(ticket, 'FAILED - SEGMENTATION FAILED')
        return

    ## cleanup
    shutil.rmtree(res)
    os.remove(frag)

    fin_folder = "{dir}/{file}".format(dir=config.out_folder, file=ticket)
    try:

        r.set(ticket, 'Move Result To Final path')
        shutil.move(seg, fin_folder)
    except:
        r.set(ticket, 'FAILED - move result to final destionation problem')
        return
    r.set(ticket, 'SUCCESS - ' + fin_folder)
