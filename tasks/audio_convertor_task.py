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
#import redis

# work_folder_tmp="/home/videostreamer/video_tmp"
# input_folder="/home/videostreamer/video_tmp"
from config import REDIS, work_folder_tmp, input_folder, out_folder, app


def execute(command):
    popen = psutil.Popen(command, stdout=subprocess.PIPE, bufsize=16)
    lines_iterator = iter(popen.stdout.readline, b"")
    for line in lines_iterator:
        print(line)  # yield line


def fragment_file(src_dir):
    for i in os.listdir(src_dir):

        cmd = ["/home/videostreamer/bin/mp4tools/mp4fragment",
               os.path.join(src_dir, i), os.path.join(src_dir, 'fragged_%s' % i)]
        print cmd
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode == 0:
            pass
        else:
            return None
    return src_dir


def create_different_resulations(src, min_bw=64, max_bw=1024, bw_count=5):
    bw_ranges = [min_bw + i * (min_bw + max_bw) /
                 bw_count for i in range(bw_count)]
    out_dir = "{tmp}/{dir_name}".format(tmp=work_folder_tmp,
                                        dir_name=str(uuid.uuid4()))
    os.mkdir(out_dir)
    cmd = ['ffmpeg', '-i', src]
    for i in [['-vn', '-b:a', '%sk' % x, "{out_dir}/{filename}.mp4".format(out_dir=out_dir, filename=x)] for x in bw_ranges]:
        cmd.extend(i)
    print cmd
    print "call execute-------"
    print cmd
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    else:
        return None


def create_segments(src_dir):
    out_dir = "{tmp}/{dir_name}".format(tmp=work_folder_tmp,
                                        dir_name=str(uuid.uuid4()))
    for i in glob.glob(os.path.join(src_dir, 'frag*mp4')):
        cmd = ["python2.7", "/home/videostreamer/bento4/utils/mp4-dash.py",
               "--exec-dir=/home/videostreamer/bin/mp4tools", i, '-o', i + '_out']
        print cmd
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode == 0:
            pass

        else:
            return None
    return src_dir


@app.task
def audio_convert(filename, min_bw=64, max_bw=1024, bw_count=10):
    fullfilename = "{dir}/{file}".format(dir=input_folder, file=filename)
    REDIS.set(filename, 'STARTED')
    REDIS.set(filename, 'MAKE {count} resulations from {min} to {max}'.format(
        count=bw_count, min=min_bw, max=max_bw))
    res = create_different_resulations(fullfilename, min_bw, max_bw, bw_count)
    if res == None:
        REDIS.set(filename, 'FAILED - RESULATION STEP ')
        return
    REDIS.set(filename, 'FRAGMENTATION STARTED')
    frag = fragment_file(res)
    if frag == None:
        REDIS.set(filename, 'FAILED - FRAGMENTATION STEP')
        return
    REDIS.set(filename, 'SEGMENTATION STARTED')
    seg = create_segments(frag)
    if seg == None:
        REDIS.set(filename, 'FAILED - SEGMENTATION FAILED')
        return
    fin_folder = os.path.join(work_folder_tmp, str(uuid.uuid4()))
    os.mkdir(fin_folder)
    print fin_folder
    bw_ranges = [min_bw + i * (min_bw + max_bw) /
                 bw_count for i in range(bw_count)]
    mpd_file = []
    REDIS.set(filename, 'AGRIGATION STARTED')

    for i in bw_ranges:
        _tmp = os.path.join(fin_folder, str(i))
        os.mkdir(_tmp)
        os.rename(os.path.join(
            seg, 'fragged_{bitrate}.mp4_out'.format(bitrate=i)), _tmp)
        with open(os.path.join(_tmp, 'stream.mpd')) as f:
            mpd_file.append([i, f.read()])
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

    with open(os.path.join(fin_folder, 'rashavas.mpd'), 'w') as g:
        g.write(etree.tostring(final_xml))
    REDIS.set(filename, 'TRANSFER ASSETS TO STREAMER SERVER')
    print 'fin_folder', fin_folder
    print 'out_folder', out_folder
    shutil.move(fin_folder, out_folder)
    REDIS.set(filename, 'SUCCESS TO GENERATE %s' % fin_folder)

# audio_convert('2mp3',bw_count=2,min_bw=256,max_bw=512);
