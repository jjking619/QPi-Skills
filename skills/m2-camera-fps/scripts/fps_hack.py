#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frame-rate bench: change the IMX219 timing registers mid-stream, measure the
frame rate before and after, and save a frame from each side as evidence.

Why mid-stream:
    The driver powers the sensor down when idle, so I2C does not answer. The
    registers can only be written while the stream is running.

How the rate is measured:
    A probe on the fakesink sink pad records every frame's arrival time and PTS.
    The median inter-frame interval gives the fps - no container nominal rate, no
    buffer distortion.

Usage:
    fps_hack.py --vts 1120                       # 1080p, change at 3s, 10s total
    fps_hack.py --vts 1120 --hts 2800 --at 4
    fps_hack.py --width 1280 --height 720 --vts 1120
"""
import argparse
import os
import statistics
import threading
import time

import cv2
import numpy as np

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib  # noqa: E402

import camera_regs  # noqa: E402


class Probe:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.t = []           # arrival times
        self.pts = []
        self.before_jpg = None
        self.after_jpg = None
        self.t0 = time.time()
        self.grab_before_win = (1.0, 1.4)
        self.grab_after_win = None

    def _nv12_to_bgr(self, data):
        nv = np.frombuffer(data, np.uint8).reshape(self.h * 3 // 2, self.w)
        return cv2.cvtColor(nv, cv2.COLOR_YUV2BGR_NV12)

    def on_buffer(self, _pad, info):
        buf = info.get_buffer()
        if buf is None:
            return Gst.PadProbeReturn.OK
        now = time.time() - self.t0
        self.t.append(now)
        self.pts.append(buf.pts)
        if len(self.t) <= 6000:
            gb = self.grab_before_win
            if self.before_jpg is None and gb[0] <= now <= gb[1]:
                ok, m = buf.map(Gst.MapFlags.READ)
                if ok:
                    self.before_jpg = self._nv12_to_bgr(m.data)
                    buf.unmap(m)
            ga = self.grab_after_win
            if ga and self.after_jpg is None and ga[0] <= now <= ga[1]:
                ok, m = buf.map(Gst.MapFlags.READ)
                if ok:
                    self.after_jpg = self._nv12_to_bgr(m.data)
                    buf.unmap(m)
        return Gst.PadProbeReturn.OK

    def fps_window(self, lo, hi):
        ts = [t for t in self.t if lo <= t <= hi]
        if len(ts) < 8:
            return 0.0, len(ts)
        d = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        d = sorted(x for x in d if x > 1e-6)
        med = d[len(d) // 2]
        return (1.0 / med if med else 0.0), len(ts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--at', type=float, default=3.0, help='second at which to change the registers')
    ap.add_argument('--vts', type=int)
    ap.add_argument('--hts', type=int)
    ap.add_argument('--expo', type=int,
                    help='exposure in lines; must stay below VTS or the frame is stretched')
    ap.add_argument('--gain', type=int, help='analogue gain register value')
    ap.add_argument('--pw', default=os.environ.get('SUDO_PW', ''),
                    help='sudo password; prefer passing it via the SUDO_PW environment variable')
    ap.add_argument('--tag', default='exp')
    a = ap.parse_args()
    W, H = a.width, a.height

    os.environ.setdefault('GST_V4L2_FORCE_LIBV4L2', '0')
    Gst.init(None)
    desc = ('v4l2src device=' + os.environ.get('CAM_DEV', '/dev/video51') + ' io-mode=4 '
            '! video/x-raw,format=NV12,width=%d,height=%d '
            '! fakesink name=sink sync=false' % (W, H))
    pipe = Gst.parse_launch(desc)
    sink = pipe.get_by_name('sink')
    probe = Probe(W, H)
    probe.grab_after_win = (a.at + 1.5, a.at + 1.9)
    sink.get_static_pad('sink').add_probe(Gst.PadProbeType.BUFFER, probe.on_buffer)

    loop = GLib.MainLoop()
    result = {}

    def do_change():
        try:
            before = camera_regs.dump(a.pw)
            if a.expo:
                camera_regs.write_reg('expo', a.expo, a.pw)
            if a.gain:
                camera_regs.write_reg('gain', a.gain, a.pw)
            if a.vts:
                camera_regs.write_reg('vts', a.vts, a.pw)
            if a.hts:
                camera_regs.write_reg('hts', a.hts, a.pw)
            after = camera_regs.dump(a.pw)
            result['before'] = before
            result['after'] = after
            print('[t=%.1fs] written: VTS %s->%s  HTS %s->%s  EXPO %s->%s  GAIN %s->%s'
                  % (a.at, before.get('vts'), after.get('vts'),
                     before.get('hts'), after.get('hts'),
                     before.get('expo'), after.get('expo'),
                     before.get('gain'), after.get('gain')))
        except Exception as e:
            result['err'] = str(e)
            print('[t=%.1fs] write failed: %s' % (a.at, e))
        return False

    def finish():
        loop.quit()
        return False

    pipe.set_state(Gst.State.PLAYING)
    probe.t0 = time.time()
    GLib.timeout_add(int(a.at * 1000), do_change)
    GLib.timeout_add(int(a.seconds * 1000), finish)
    loop.run()
    pipe.set_state(Gst.State.NULL)

    f_before, n_before = probe.fps_window(1.0, max(1.6, a.at - 0.4))
    f_after, n_after = probe.fps_window(a.at + 1.0, a.seconds)
    print()
    print('before: %.2f fps  (%d frames)' % (f_before, n_before))
    print('after:  %.2f fps  (%d frames)' % (f_after, n_after))
    if f_before > 0:
        print('gain:   %+.1f%%' % ((f_after / f_before - 1) * 100))
    if result.get('after', {}).get('vts') and result['after'].get('hts'):
        print('theoretical: %.2f fps'
              % camera_regs.fps_from(result['after']['vts'], result['after']['hts']))
    if probe.before_jpg is not None:
        cv2.imwrite(os.path.join(os.path.expanduser('~'), '%s_before.jpg' % a.tag), probe.before_jpg,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        print('saved %s_before.jpg' % a.tag)
    if probe.after_jpg is not None:
        cv2.imwrite(os.path.join(os.path.expanduser('~'), '%s_after.jpg' % a.tag), probe.after_jpg,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        print('saved %s_after.jpg' % a.tag)
    if result.get('err'):
        print('note: register write reported an error -> %s' % result['err'])


if __name__ == '__main__':
    main()
