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

# work_folder_tmp="/home/videostreamer/video_tmp"
# input_folder="/home/videostreamer/video_tmp"
from config import REDIS, work_folder_tmp, input_folder, out_folder, app


def execute(command):
    popen = psutil.Popen(command, stdout=subprocess.PIPE, bufsize=16)
    lines_iterator = iter(popen.stdout.readline, b"")
    for line in lines_iterator:
        print(line)  # yield line


def fragment_file(src):
    tmp_file = str(uuid.uuid4())
    fullpath = "{tmp}/{file}.mp4".format(tmp=work_folder_tmp, file=tmp_file)
    cmd = ["/home/videostreamer/bin/mp4tools/mp4fragment", src, fullpath]
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return fullpath
    else:
        return None


def create_different_resulations(src, min_bw=64, max_bw=1024, bw_count=5):
    out_dir = "{tmp}/{dir_name}".format(tmp=work_folder_tmp,
                                        dir_name=str(uuid.uuid4()))
    cmd = ['python2.7', '/home/videostreamer/bento4/utils/mp4-dash-encode.py', '-v',
           '-b', str(bw_count), '-m', str(min_bw), '-n', str(max_bw), src, '-o', out_dir]
    print "call execute-------"
    print cmd
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        return None


def create_segments(src):
    out_dir = "{tmp}/{dir_name}".format(tmp=work_folder_tmp,
                                        dir_name=str(uuid.uuid4()))
    mpd_file = 'rashavas.mpd'
    cmd = ["python2.7", "/home/videostreamer/bento4/utils/mp4-dash.py",
           "--mpd-name=" + mpd_file, "--exec-dir=/home/videostreamer/bin/mp4tools"]
    cmd.extend(glob.glob(src + "/*mp4"))
    cmd.extend(["-o", out_dir])
    print cmd
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
def video_convert(filename, min_bw=64, max_bw=1024, bw_count=10):
    fullfilename = "{dir}/{file}".format(dir=input_folder, file=filename)
    REDIS.set(filename, 'STARTED')
    REDIS.set(filename, 'FRAGMENTATION')
    frag = fragment_file(fullfilename)
    if frag == None:
        REDIS.set(filename, 'FAILED - FRAGMENTATION FAILED')
        return
    REDIS.set(filename, 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw))
    res = create_different_resulations(frag, min_bw, max_bw, bw_count)
    if res == None:
        REDIS.set(filename, 'FAILED - RESULATION STEP ')
        return
    REDIS.set(filename, 'SEGMENTATION STARTED')
    seg = create_segments(res)
    if seg == None:
        REDIS.set(filename, 'FAILED - SEGMENTATION FAILED')
        return

    fin_folder = "{dir}/{file}".format(dir=out_folder, file=filename)
    try:

        REDIS.set(filename, 'Move Result To Final path')
        shutil.move(seg, fin_folder)
    except:
        REDIS.set(filename, 'FAILED - move result to final destionation problem')
        return
    REDIS.set(filename, 'SUCCESS - ' + fin_folder)
