#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMX219 capture module (Quectel Pi M2 / RK3576) - static LSC + global white balance

The division of labour (the core of this module):
    LSC (lens shading) = a fixed physical quantity, a property of the lens/ISP only,
                         independent of the scene
                       -> calibrate once, store a static fixed-point gain map, and
                          merely multiply by it every frame
    Global white balance = depends on the colour temperature of the light, and the
                         ISP's AWB keeps drifting
                       -> estimate one R/B gain pair per frame on the picture that has
                          ALREADY been through LSC. It must be estimated after LSC:
                          otherwise the frame-wide R/G shift introduced by LSC is left out of
                          the estimate and the measurement lands at 0.90 instead of 1.00.

Two white-balance modes:
    wb=True   per-frame gray world; global R/G and B/G are normalized to 1.00 (default)
              cost: a frame dominated by one colour gets washed out to neutral - the
              inherent price of the gray-world assumption
    wb=False  LSC only; leave the global cast to the ISP's AWB
              use this when the scene has large coloured objects, the colours stay truer

Calibration: python3 lsc_calib.py  (aim at a uniform white/gray surface, writes ~/lsc_map.npz)

Usage:
    from cam_lsc import CameraLSC
    with CameraLSC() as cam:
        ok, frame = cam.read()          # BGR ndarray, already corrected

Measurements (1080p): see the __main__ output at the end of this file.
"""

import subprocess

import cv2
import numpy as np

import os as _os
DEV = _os.environ.get('CAM_DEV', '/dev/video51')
W, H = 1920, 1080
MAP_PATH = _os.environ.get('LSC_MAP', _os.path.join(_os.path.expanduser('~'), 'lsc_map.npz'))
FIX = 1024.0
GAIN_MIN, GAIN_MAX = 0.35, 3.5
WB_CLAMP = (0.4, 2.5)


class CameraLSC:
    def __init__(self, dev=DEV, width=W, height=H, map_path=MAP_PATH,
                 lsc=True, wb=True):
        self.width, self.height = width, height
        self.frame_bytes = width * height * 3 // 2
        self.wb_on = wb

        d = np.load(map_path)
        if lsc:
            gr = cv2.resize(d['gain_r'].astype(np.float32), (width, height),
                            interpolation=cv2.INTER_LINEAR)
            gb = cv2.resize(d['gain_b'].astype(np.float32), (width, height),
                            interpolation=cv2.INTER_LINEAR)
        else:
            gr = np.ones((height, width), np.float32)
            gb = np.ones((height, width), np.float32)
        self.gain_r, self.gain_b = gr, gb

        self.map_r = (np.clip(gr, GAIN_MIN, GAIN_MAX) * FIX).astype(np.uint16)
        self.map_b = (np.clip(gb, GAIN_MIN, GAIN_MAX) * FIX).astype(np.uint16)
        self._gr8 = gr[::8, ::8]
        self._gb8 = gb[::8, ::8]

        self.wb_r = self.wb_b = 1.0
        self.frames = 0

        caps = 'video/x-raw,format=NV12,width=%d,height=%d' % (width, height)
        cmd = ['gst-launch-1.0', '-q', 'v4l2src', 'device=%s' % dev,
               '!', caps, '!', 'fdsink', 'fd=1']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, bufsize=0)

    def _read_raw(self):
        buf = b''
        while len(buf) < self.frame_bytes:
            c = self.proc.stdout.read(self.frame_bytes - len(buf))
            if not c:
                return None
            buf += c
        nv = np.frombuffer(buf, np.uint8).reshape(self.height * 3 // 2, self.width)
        return cv2.cvtColor(nv, cv2.COLOR_YUV2BGR_NV12)

    def _estimate_wb(self, frame):
        """Estimate the global gains (gray world) on a subsampled, LSC-ed picture."""
        sub = frame[::8, ::8].astype(np.float32)
        b = sub[..., 0] * self._gb8
        g = sub[..., 1]
        r = sub[..., 2] * self._gr8
        gm = max(float(g.mean()), 1e-3)
        self.wb_r = float(np.clip(gm / max(float(r.mean()), 1e-3), *WB_CLAMP))
        self.wb_b = float(np.clip(gm / max(float(b.mean()), 1e-3), *WB_CLAMP))

    def read(self):
        frame = self._read_raw()
        if frame is None:
            return False, None
        if self.wb_on:
            self._estimate_wb(frame)
        b, g, r = cv2.split(frame)
        b = cv2.multiply(b, self.map_b, scale=1.0 / FIX, dtype=cv2.CV_8U)
        r = cv2.multiply(r, self.map_r, scale=1.0 / FIX, dtype=cv2.CV_8U)
        if self.wb_on:
            b = cv2.convertScaleAbs(b, alpha=self.wb_b)
            r = cv2.convertScaleAbs(r, alpha=self.wb_r)
        frame = cv2.merge([b, g, r])
        self.frames += 1
        return True, frame

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


if __name__ == '__main__':
    import time

    def radial(im, bins=6):
        b, g, r = [im[..., i].astype(np.float64) for i in range(3)]
        g = np.maximum(g, 1e-6)
        h, w = g.shape
        yy, xx = np.mgrid[0:h, 0:w]
        rad = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        idx = np.clip((rad * bins).astype(int), 0, bins - 1)
        out = []
        for m in (r / g, b / g):
            out.append([m[idx == k].mean() if (idx == k).any() else np.nan for k in range(bins)])
        return out

    with CameraLSC() as cam:
        for _ in range(8):
            cam.read()
        t0 = time.time()
        frame, n = None, 0
        for _ in range(40):
            ok, f = cam.read()
            if ok:
                frame, n = f, n + 1
        dt = time.time() - t0
        print('fps = %.2f  (frames=%d)' % (n / dt, n))
        rg, bg = radial(frame)
        print('R/G: ' + ' '.join('%6.3f' % v for v in rg))
        print('B/G: ' + ' '.join('%6.3f' % v for v in bg))
        print('radial spread R/G=%.3f  B/G=%.3f  |  global R/G=%.3f B/G=%.3f'
              % (max(rg) - min(rg), max(bg) - min(bg),
                 sum(rg) / len(rg), sum(bg) / len(bg)))
        cv2.imwrite(_os.path.join(_os.path.expanduser('~'), 'lsc_live_after.jpg'), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print('saved ~/lsc_live_after.jpg')
