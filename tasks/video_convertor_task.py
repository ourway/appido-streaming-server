#!/usr/bin/env python
"""Video -> DASH + HLS conversion task.

Pipeline: download (or copy) -> fragment -> multi-bitrate resolutions -> DASH
segments + HLS -> store status in Redis -> optional webhook.

The md5 dedup lock uses SET NX + TTL so a failed run never blocks re-encodes,
and the lock is always released (try/finally) even on exceptions.
"""

import glob
import logging
import os
import shutil
import subprocess
import sys
import time

import requests
from lxml import etree

import config
from config import app
from utils import Status, download_file, md5_for_file, store

logger = logging.getLogger(__name__)

r = config.REDIS

# ffmpeg/bento4 progress line parser (kept for future progress reporting).
import re  # noqa: E402

_PROGRESS_RE = re.compile(
    r"frame= *([\d]+) *fps= *([\d]+) *q=([\d\.]+) +size= *([\d]+[\w]{2}) "
    r"+time=([\d\.\:]+) *bitrate= *([\d\.]+[\w\/]+)"
)


# --- Lock helpers -----------------------------------------------------------
LOCK_TTL_SECONDS = 4 * 3600  # 4 hours safety net in case a worker dies hard


def _acquire_lock(fmd5: str) -> bool:
    """Atomic NX acquire with TTL. Returns True if we got it."""
    key = "STMSERVER_LOCK_" + fmd5
    return bool(r.set(key, "LOCK", nx=True, ex=LOCK_TTL_SECONDS))


def _release_lock(fmd5: str) -> None:
    r.delete("STMSERVER_LOCK_" + fmd5)


# --- Pipeline steps ---------------------------------------------------------
def fragment_file(src, fmd5):
    tmp_file = fmd5 + "-fragment.mp4"
    fullpath = "{tmp}/{file}.mp4".format(tmp=config.work_folder_tmp, file=tmp_file)
    cmd = [
        "nice",
        os.path.join(config.bento4_path, "bin", "mp4fragment"),
        src,
        fullpath,
    ]
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return fullpath
    logger.error("ERROR on fragmentation of file: %s", src)
    return None


def create_different_resulations(src, fmd5, min_bw=64, max_bw=1024, bw_count=8):
    out_dir = "{tmp}/{dir_name}".format(
        tmp=config.work_folder_tmp, dir_name="%s-resulations" % fmd5
    )
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    cmd = [
        "nice",
        "-n",
        "20",
        sys.executable,
        os.path.join(config.bento4_path, "utils", "mp4-dash-encode.py"),
        "-v",
        "-f",
        "-b",
        str(bw_count),
        "-d",
        "--select-streams",
        "0,1",
        "-e",
        "-pix_fmt yuv420p",
        "-m",
        str(min_bw),
        "-n",
        str(max_bw),
        src,
        "-o",
        out_dir,
    ]
    logger.info("resolutions cmd: %s", " ".join(cmd))
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    logger.error("ERROR on create different resolutions for file %s", src)
    return None


def hls_segments(src, fmd5):
    out_dir = "{tmp}/{dir_name}/hls".format(
        tmp=config.out_folder, dir_name="%s-stream" % fmd5
    )
    os.makedirs(out_dir, exist_ok=True)
    files = glob.glob(os.path.join(src, "*mp4"))
    m3u8 = ["#EXTM3U"]
    fmt_ = "#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH={bw}"
    for f in files:
        filename = os.path.basename(f)
        speed = filename.replace(".mp4", "").replace("video_", "")
        fin_dir = os.path.join(out_dir, speed)
        os.makedirs(fin_dir, exist_ok=True)
        cmd = ["nice", os.path.join(config.bento4_path, "bin", "mp42hls"), f]
        p = subprocess.Popen(cmd, cwd=fin_dir)
        p.wait()
        m3u8.append(fmt_.format(bw=int(float(speed) * 1024)))
        m3u8.append("{speed}/stream.m3u8".format(speed=speed))
        if p.returncode != 0:
            logger.error("HLS segment for %s failed", f)
            return None
    program_m3u8 = open(os.path.join(out_dir, "program.m3u8"), "w")
    program_m3u8.write("\r\n".join(m3u8))
    program_m3u8.close()
    return out_dir


def create_segments(src, fmd5):
    out_dir = "{tmp}/{dir_name}".format(
        tmp=config.out_folder, dir_name="%s-stream" % fmd5
    )
    mpd_file = "program.mpd"
    cmd = [
        "nice",
        sys.executable,
        os.path.join(config.bento4_path, "utils", "mp4-dash.py"),
        "-f",
        "-v",
        "--use-segment-list",
        "--use-segment-timeline",
        "--mpd-name=" + mpd_file,
        "--exec-dir=%s/bin" % config.bento4_path,
    ]
    cmd.extend(glob.glob(os.path.join(src, "*mp4")))
    cmd.extend(["-o", out_dir])
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        with open(os.path.join(out_dir, mpd_file)) as f:
            xmlstr = f.read()
        tree = etree.fromstring(xmlstr.encode("utf-8"))
        comments = tree.xpath("//comment()")
        for c in comments:
            p = c.getparent()
            p.remove(c)
        with open(os.path.join(out_dir, mpd_file), "wb") as f:
            f.write(etree.tostring(tree))
        return out_dir
    logger.error("ERROR on create segments of %s", src)
    return None


# --- Task -------------------------------------------------------------------
@app.task
def video_convert(
    filename,
    ticket,
    min_bw=128,
    max_bw=1280,
    bw_count=5,
    webhook=None,
    abspath=False,
    url=True,
    correlator=None,
):

    s = time.time()
    logger.debug("Started streaming process of %s", filename)
    status = Status()
    tmpfilepath = None

    if abspath:
        # copy the file, the original might be deleted by the client
        tmpfilepath = os.path.join(config.work_folder_tmp, "_tmp" + os.path.basename(filename))
        shutil.copyfile(filename, tmpfilepath)
        fullfilename = tmpfilepath
    elif url:
        fullfilename = download_file(filename, ticket)
    else:
        fullfilename = os.path.join(config.input_folder, filename)

    fmd5 = md5_for_file(fullfilename)

    # Public URL paths (served by nginx rooted at out_folder).
    target_mpd = "/{file}/program.mpd".format(file="%s-stream" % fmd5)
    target_m3u8 = "/{file}/hls/program.m3u8".format(file="%s-stream" % fmd5)
    # Filesystem paths used to check existence.
    mpd_fs = os.path.join(config.out_folder, "%s-stream" % fmd5, "program.mpd")
    m3u8_fs = os.path.join(config.out_folder, "%s-stream" % fmd5, "hls", "program.m3u8")

    if not _acquire_lock(fmd5):
        # Another worker owns this exact file; let the caller retry later.
        status.status = "LOCKED"
        status.info = "another encode for this file is in progress"
        store(ticket, status)
        return "LOCK:%s" % fmd5

    try:
        if os.path.isfile(mpd_fs) and os.path.isfile(m3u8_fs):
            status.status = "Ready"
            status.info = dict(mpd=target_mpd, m3u8=target_m3u8)
            if correlator:
                r.set(correlator, status.status)
            store(ticket, status)
            store(fmd5, dict(ticket=ticket, status=status.to_json()))
            return status

        def _set_state(name, info=None):
            status.status = name
            status.info = info
            if correlator:
                r.set(correlator, name)
            store(ticket, status)
            store(fmd5, dict(ticket=ticket, status=status.to_json()))

        _set_state("STARTED")

        _set_state("FRAGMENTATION")
        frag = fragment_file(fullfilename, fmd5)
        if frag is None:
            _set_state("FAILED", info="fragmentation failed")
            return

        _set_state(
            "RESOLUTION PROCESS",
            info="MAKE {count} resolutions from {min} to {max}".format(
                count=bw_count, min=min_bw, max=max_bw
            ),
        )
        res = create_different_resulations(frag, fmd5, min_bw, max_bw, bw_count)
        if res is None:
            _set_state("FAILED", info="resolutions step failed")
            return

        _set_state("SEGMENTATION STARTED")
        if not os.path.isfile(mpd_fs):
            seg = create_segments(res, fmd5)
            if seg is None:
                _set_state("FAILED", info="segmentation failed")
                return
        if not os.path.isfile(m3u8_fs):
            hls = hls_segments(res, fmd5)
            if hls is None:
                _set_state("FAILED", info="hls segment creation failed")
                return

        # cleanup intermediates
        shutil.rmtree(res, ignore_errors=True)
        if frag is not None:
            try:
                os.remove(frag)
            except OSError:
                pass
        if abspath and tmpfilepath is not None:
            try:
                os.remove(tmpfilepath)
            except OSError:
                pass

        status.status = "Ready"
        status.info = dict(mpd=target_mpd, m3u8=target_m3u8)
        if correlator:
            r.set(correlator, status.status)
        store(ticket, status)
        store(fmd5, dict(ticket=ticket, status=status.to_json()))

        if webhook:
            try:
                requests.post(webhook, timeout=30)
            except requests.RequestException as exc:
                logger.warning("webhook %s failed: %s", webhook, exc)

        logger.debug(
            "Streaming process of %s ended in %.3f seconds", filename, time.time() - s
        )
        return "OK"
    finally:
        _release_lock(fmd5)