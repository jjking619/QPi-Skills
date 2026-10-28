#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record the corrected picture with the GStreamer hardware encoder (mpph264enc).

The earlier rec_lsc.py used cv2.VideoWriter('mp4v'), i.e. **software encoding**,
which tops out at 20.7 fps in 720p. This script pushes the frames already
processed by CameraLSC back into a GStreamer pipeline through appsrc and lets the
VPU encode them, taking that CPU cost away so the capture rate can be saturated.

Two deliberate design choices:
  1. PTS is stamped from the **wall clock**, not from "frame index / nominal fps".
     The mp4 duration therefore equals the real recording time and the average
     rate equals frames / duration, so ffprobe or any player can verify it
     independently - no need to trust what the script reports.
  2. --hud burns the rolling frame rate into the picture, so the recording itself
     shows the rate moving.

Usage:
    python3 rec_hw.py --seconds 10
    python3 rec_hw.py --seconds 10 --hud
    python3 rec_hw.py --width 1920 --height 1080 --bitrate 8000
    python3 rec_hw.py --raw --out ~/hw_raw.mp4     # no correction, as a baseline
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib  # noqa: E402

from cam_lsc import CameraLSC  # noqa: E402

PIXFMT_BYTES = {'NV12': 1.5, 'I420': 1.5, 'BGR': 3.0, 'RGB': 3.0}


def bgr_to_nv12(bgr):
    """BGR -> NV12 (Y plane + interleaved UV plane)."""
    h, w = bgr.shape[:2]
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420)
    y = yuv[:h, :]
    # In I420 the U/V planes are stored row-contiguously: an (h/2, w/2) block is
    # flattened into (h/4, w) rows
    u = yuv[h:h + h // 4, :].reshape(h // 2, w // 2)
    v = yuv[h + h // 4:, :].reshape(h // 2, w // 2)
    uv = np.empty((h // 2, w), np.uint8)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    return np.vstack([y, uv])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=720)
    ap.add_argument('--fps', type=int, default=30, help='nominal pipeline frame rate (caps)')
    ap.add_argument('--bitrate', type=int, default=6000, help='kbps')
    ap.add_argument('--pixfmt', default='NV12', choices=list(PIXFMT_BYTES))
    ap.add_argument('--raw', action='store_true', help='no correction')
    ap.add_argument('--hud', action='store_true', help='burn frame rate / frame index into the picture')
    ap.add_argument('--vts', type=int, help='write the sensor VTS register after the stream starts')
    ap.add_argument('--hts', type=int, help='write the sensor HTS register after the stream starts')
    ap.add_argument('--expo', type=int,
                    help='exposure in lines written after the stream starts; must stay below VTS')
    ap.add_argument('--pw', default=os.environ.get('SUDO_PW', ''),
                    help='sudo password; prefer passing it via the SUDO_PW environment variable')
    ap.add_argument('--flip', action='store_true',
                    help='software horizontal flip (the sensor horizontal_flip is locked at 1; '
                         'changing it in hardware fails negotiation when the stream starts)')
    a = ap.parse_args()

    out = a.out or os.path.join(os.path.expanduser('~'), time.strftime('hw_%H%M%S.mp4'))
    use = not a.raw
    W, H = a.width, a.height

    Gst.init(None)
    desc = (
        'appsrc name=src format=time is-live=false block=true max-bytes=8000000 '
        'caps=video/x-raw,format=%s,width=%d,height=%d,framerate=%d/1 '
        '! mpph264enc rc-mode=cbr bps=%d gop=-1 header-mode=1 '
        '! h264parse ! mp4mux ! filesink location=%s'
        % (a.pixfmt, W, H, a.fps, a.bitrate * 1000, out)
    )
    pipe = Gst.parse_launch(desc)
    src = pipe.get_by_name('src')

    pipe.set_state(Gst.State.PLAYING)
    t_start = time.time()
    n = 0
    fps_now = 0.0
    fps_t0 = 0.0
    with CameraLSC(width=W, height=H, lsc=use, wb=use) as cam:
        # Warm up: let the capture pipeline and the encoder come up first, otherwise
        # the startup cost is averaged into the frame rate
        for _ in range(10):
            cam.read()
        if a.vts or a.hts or a.expo:
            try:
                import camera_regs as cr
                if a.expo:
                    cr.write_reg('expo', a.expo, a.pw)
                if a.vts:
                    cr.write_reg('vts', a.vts, a.pw)
                if a.hts:
                    cr.write_reg('hts', a.hts, a.pw)
                print('sensor registers written: VTS=%s HTS=%s EXPO=%s'
                      % (a.vts, a.hts, a.expo))
            except Exception as e:
                print('register write failed: %s' % e)
        t0 = time.time()
        fps_t0 = t0
        startup = t0 - t_start
        while True:
            el = time.time() - t0
            if el >= a.seconds:
                break
            ok, frame = cam.read()
            if not ok:
                break
            n += 1

            if a.flip:
                frame = cv2.flip(frame, 1)

            if n % 10 == 0:
                now = time.time()
                fps_now = 10.0 / max(now - fps_t0, 1e-6)
                fps_t0 = now

            if a.hud:
                txt = 'FPS %.1f  F%05d  %s' % (
                    fps_now, n, 'RAW' if a.raw else 'LSC+WB')
                cv2.rectangle(frame, (0, 0), (W, 42), (0, 0, 0), -1)
                cv2.putText(frame, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 0), 2, cv2.LINE_AA)

            if a.pixfmt == 'NV12':
                data = bgr_to_nv12(frame)
            elif a.pixfmt == 'I420':
                data = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
            elif a.pixfmt == 'RGB':
                data = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                data = frame
            payload = np.ascontiguousarray(data).tobytes()

            buf = Gst.Buffer.new_allocate(None, len(payload), None)
            buf.fill(0, payload)
            pts = int((time.time() - t0) * Gst.SECOND)
            buf.pts = pts
            buf.dts = pts
            buf.duration = int(Gst.SECOND / a.fps)
            ret = src.emit('push-buffer', buf)
            if ret != Gst.FlowReturn.OK:
                print('push-buffer failed: %s' % ret)
                break

    wall = time.time() - t0
    src.emit('end-of-stream')

    # Wait for EOS, at most 15 seconds
    bus = pipe.get_bus()
    deadline = time.time() + 15
    while time.time() < deadline:
        msg = bus.timed_pop_filtered(100 * Gst.MSECOND,
                                     Gst.MessageType.EOS | Gst.MessageType.ERROR)
        if msg is not None:
            if msg.type == Gst.MessageType.ERROR:
                err, dbg = msg.parse_error()
                print('pipeline error: %s\n%s' % (err.message, dbg))
            break
    pipe.set_state(Gst.State.NULL)

    size = os.path.getsize(out) if os.path.exists(out) else 0
    print('output: %s' % out)
    print('resolution %dx%d  pixel format %s  target bitrate %d kbps' % (W, H, a.pixfmt, a.bitrate))
    print('encoder: mpph264enc (VPU hardware)')
    print('warm-up %.2f s (excluded from the statistics)' % startup)
    print('captured %d frames / steady-state %.2f s = %.2f fps'
          % (n, wall, n / wall if wall else 0))
    print('total including startup %.2f s -> %.2f fps'
          % (wall + startup, n / max(wall + startup, 1e-6)))
    print('file %.2f MB  (%.2f Mbps)' % (size / 1e6, size * 8 / max(wall, 1e-6) / 1e6))
    print('correction: %s' % ('off (--raw)' if a.raw else 'on (LSC + global white balance)'))


if __name__ == '__main__':
    main()
