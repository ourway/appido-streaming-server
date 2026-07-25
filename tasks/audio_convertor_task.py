#!/usr/bin/env python
"""Audio -> DASH + HLS conversion task.

Same shape as video: download/copy -> resolutions -> fragment -> DASH + HLS.
Uses ffmpeg for bitrate ladder, bento4 for fragment/dash/hls.

The md5 dedup lock uses SET NX + TTL and is released on every exit path.
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

LOCK_TTL_SECONDS = 2 * 3600  # 2 hours safety net


def _acquire_lock(fmd5: str) -> bool:
    key = "STMSERVER_LOCK_" + fmd5
    return bool(r.set(key, "LOCK", nx=True, ex=LOCK_TTL_SECONDS))


def _release_lock(fmd5: str) -> None:
    r.delete("STMSERVER_LOCK_" + fmd5)


def fragment_file(src_dir):
    for i in os.listdir(src_dir):
        cmd = [
            os.path.join(config.bento4_path, "bin", "mp4fragment"),
            os.path.join(src_dir, i),
            os.path.join(src_dir, "fragged_%s" % i),
        ]
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode != 0:
            logger.error("Fragmentation process of %s failed", src_dir)
            return None
    return src_dir


def hls_segments(src, out_dir):
    out_dir = os.path.join(out_dir, "hls")
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)
    files = glob.glob(os.path.join(src, "frag*mp4"))
    m3u8 = ["#EXTM3U"]
    fmt_ = "#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH={bw}"

    for f in files:
        filename = os.path.basename(f)
        speed = filename.replace(".mp4", "").replace("fragged_", "")
        fin_dir = os.path.join(out_dir, speed)
        os.makedirs(fin_dir, exist_ok=True)
        cmd = ["nice", "-n", "20", os.path.join(config.bento4_path, "bin", "mp42hls"), f]
        p = subprocess.Popen(cmd, cwd=fin_dir)
        p.wait()
        m3u8.append(fmt_.format(bw=int(float(speed) * 1024)))
        m3u8.append("{speed}/stream.m3u8".format(speed=speed))
        if p.returncode != 0:
            logger.error("HLS segments process of %s failed", src)
            return None
    program_m3u8 = open(os.path.join(out_dir, "program.m3u8"), "w")
    program_m3u8.write("\r\n".join(m3u8))
    program_m3u8.close()
    return out_dir


def _bw_ranges(min_bw, max_bw, bw_count):
    """Build the list of target bitrates (ints, kbps)."""
    if bw_count <= 0:
        return []
    step = (max_bw - min_bw) / float(bw_count)
    ranges = [int(round(min_bw + i * step)) for i in range(bw_count)]
    # de-duplicate while preserving order
    seen, out = set(), []
    for v in ranges:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def create_different_resolutions(src, fmd5, min_bw=64, max_bw=1024, bw_count=4):
    bw_ranges = _bw_ranges(min_bw, max_bw, bw_count)
    out_dir = "{tmp}/{dir_name}".format(
        tmp=config.work_folder_tmp, dir_name="%s-resulations" % fmd5
    )
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", src]
    for x in bw_ranges:
        cmd.extend(
            ["-vn", "-b:a", "%sk" % x, os.path.join(out_dir, "%s.mp4" % x)]
        )
    logger.info("resolutions cmd: %s", " ".join(cmd))
    p = subprocess.Popen(cmd)
    p.wait()
    if p.returncode == 0:
        return out_dir
    logger.error("Resolutions process of %s failed", src)
    return None


def create_segments(src_dir, fmd5):
    out_dir = "{tmp}/{dir_name}".format(
        tmp=config.work_folder_tmp, dir_name="%s-segments" % fmd5
    )
    for i in glob.glob(os.path.join(src_dir, "frag*mp4")):
        cmd = [
            sys.executable,
            os.path.join(config.bento4_path, "utils", "mp4-dash.py"),
            "--exec-dir=%s/bin" % config.bento4_path,
            i,
            "-o",
            i + "_out",
        ]
        p = subprocess.Popen(cmd)
        p.wait()
        if p.returncode != 0:
            logger.error("Segments process of %s failed", src_dir)
            return None
    return src_dir


@app.task
def audio_convert(
    filename,
    ticket,
    min_bw=64,
    max_bw=1024,
    bw_count=4,
    webhook=None,
    abspath=False,
    url=True,
    correlator=None,
):

    s = time.time()
    logger.debug("Streaming process of %s started", filename)
    status = Status()
    tmpfilepath = None

    if abspath:
        tmpfilepath = os.path.join(config.work_folder_tmp, "_tmp" + os.path.basename(filename))
        shutil.copyfile(filename, tmpfilepath)
        fullfilename = tmpfilepath
    elif url:
        fullfilename = download_file(filename, ticket)
    else:
        fullfilename = os.path.join(config.input_folder, filename)

    fmd5 = md5_for_file(fullfilename)

    # Public URL paths.
    target_mpd = "/{file}/program.mpd".format(file="%s-stream" % fmd5)
    target_m3u8 = "/{file}/hls/program.m3u8".format(file="%s-stream" % fmd5)
    # Filesystem paths used to check existence.
    mpd_fs = os.path.join(config.out_folder, "%s-stream" % fmd5, "program.mpd")
    m3u8_fs = os.path.join(config.out_folder, "%s-stream" % fmd5, "hls", "program.m3u8")

    if not _acquire_lock(fmd5):
        status.status = "LOCKED"
        status.info = "another encode for this file is in progress"
        store(ticket, status)
        return "LOCK"

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
        _set_state(
            "RESOLUTION PROCESS",
            info="MAKE {count} resolutions from {min} to {max}".format(
                count=bw_count, min=min_bw, max=max_bw
            ),
        )

        res = create_different_resolutions(fullfilename, fmd5, min_bw, max_bw, bw_count)
        if res is None:
            _set_state("FAILED", info="resolutions step failed")
            return

        _set_state("FRAGMENTATION STARTED")
        frag = fragment_file(res)
        if frag is None:
            _set_state("FAILED", info="fragmentation step failed")
            return

        _set_state("SEGMENTATION STARTED")
        seg = create_segments(frag, fmd5)
        if not seg:
            _set_state("FAILED", info="segmentation failed")
            return

        fin_folder = os.path.join(config.work_folder_tmp, "%s-stream" % fmd5)
        if os.path.isdir(fin_folder):
            shutil.rmtree(fin_folder, ignore_errors=True)
        os.makedirs(fin_folder, exist_ok=True)

        bw_ranges = _bw_ranges(min_bw, max_bw, bw_count)
        mpd_file_parts = []
        _set_state("AGGREGATION STARTED")

        for i in bw_ranges:
            src_seg = os.path.join(seg, "fragged_%s.mp4_out" % i)
            dst = os.path.join(fin_folder, str(i))
            if not os.path.isdir(src_seg):
                logger.error("Missing segment dir %s", src_seg)
                _set_state("FAILED", info="missing %s" % src_seg)
                return
            os.rename(src_seg, dst)
            with open(os.path.join(dst, "stream.mpd")) as f:
                mpd_file_parts.append([i, f.read()])

        if not mpd_file_parts:
            _set_state("FAILED", info="no segments to aggregate")
            return

        final_xml = etree.fromstring(mpd_file_parts[0][1].encode("utf-8"))
        repr_sec = final_xml[1][1][1]
        repr_sec.attrib["id"] = os.path.join(str(mpd_file_parts[0][0]), repr_sec.attrib["id"])
        for i in range(1, len(mpd_file_parts)):
            _tmpxml = etree.fromstring(mpd_file_parts[i][1].encode("utf-8"))
            rpsec = _tmpxml[1][1][1]
            rpsec.attrib["id"] = os.path.join(
                str(mpd_file_parts[i][0]), rpsec.attrib["id"]
            )
            final_xml[1][1].append(rpsec)

        final_xml.remove(final_xml[0])

        with open(os.path.join(fin_folder, "program.mpd"), "wb") as g:
            g.write(etree.tostring(final_xml))

        _set_state("HLS Stream creation STARTED")
        if hls_segments(frag, fin_folder) is None:
            _set_state("FAILED", info="HLS stream creation failed")
            return

        _set_state("TRANSFER ASSETS TO STREAMER SERVER")
        shutil.move(fin_folder, os.path.join(config.out_folder, "%s-stream" % fmd5))
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