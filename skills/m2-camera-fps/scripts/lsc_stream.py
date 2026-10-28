#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrected MJPEG preview stream (Quectel Pi M2 / RK3576)

Binds 127.0.0.1 only - never 0.0.0.0, so the stream is not exposed on the LAN.
To watch it from the PC:

    ssh -L 8090:127.0.0.1:8090 board
    open http://127.0.0.1:8090/ in a browser

Decoding then happens on the PC; the board only encodes and pushes, which costs
no desktop memory and opens no browser on the board (a board-side browser plus a
local web service is a memory black hole).

Usage:
    python3 lsc_stream.py                  # 720p, port 8090
    python3 lsc_stream.py --port 8099 --width 1920 --height 1080
    python3 lsc_stream.py --raw            # no correction, for comparison
"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from cam_lsc import CameraLSC

BOUNDARY = b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n'

INDEX = b"""<!doctype html><meta charset=utf-8>
<title>M2 / IMX219 preview</title>
<style>body{margin:0;background:#111;color:#ccc;font:13px system-ui}
img{width:100%;display:block}
p{margin:6px 10px}</style>
<p>IMX219 corrected preview &mdash; <span id=s>...</span></p>
<img src="/stream">
<script>fetch('/meta').then(r=>r.json()).then(m=>{
document.getElementById('s').textContent =
 m.width+'x'+m.height+'  '+m.fps.toFixed(1)+' fps  jpeg q'+m.quality;});</script>
"""


class Producer:
    def __init__(self, width, height, quality, raw, sharp=False, flip=False):
        self.cam = CameraLSC(width=width, height=height, lsc=not raw, wb=not raw)
        self.quality = quality
        self.width, self.height = width, height
        self.raw = raw
        self.sharp = sharp
        self.flip = flip
        self.metric = 0.0
        self.peak = 0.0
        self.jpeg = None
        self.count = 0
        self.t0 = time.time()
        self.fps = 0.0
        self.lock = threading.Lock()
        self.stop = False
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop:
            ok, frame = self.cam.read()
            if not ok:
                time.sleep(0.05)
                continue
            if self.flip:
                frame = cv2.flip(frame, 1)
            if self.sharp:
                frame = self._draw_sharp(frame)
            ok2, buf = cv2.imencode('.jpg', frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            if not ok2:
                continue
            with self.lock:
                self.jpeg = buf.tobytes()
                self.count += 1
                el = time.time() - self.t0
                if el > 1.0:
                    self.fps = self.count / el
                    self.count = 0
                    self.t0 = time.time()

    def _draw_sharp(self, frame):
        h, w = frame.shape[:2]
        c = frame[h // 4:h * 3 // 4, w // 4:w * 3 // 4]
        g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (320, 180), interpolation=cv2.INTER_AREA)
        v = float(cv2.Laplacian(g, cv2.CV_64F).var())
        self.metric = v
        if v > self.peak:
            self.peak = v
        else:
            self.peak *= 0.999          # let the peak decay slowly so positions stay comparable

        sc = 300.0                       # bar full scale (text scenes measure ~100-200)
        bar_w = int(min(v / sc, 1.0) * (w - 40))
        cv2.rectangle(frame, (0, 0), (w, 92), (0, 0, 0), -1)
        cv2.putText(frame, 'SHARP %.1f   PEAK %.1f' % (v, self.peak),
                    (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.rectangle(frame, (20, 46), (20 + (w - 40), 70), (70, 70, 70), -1)
        cv2.rectangle(frame, (20, 46), (20 + max(2, bar_w), 70), (0, 255, 0), -1)
        cv2.putText(frame, 'center-half Laplacian var', (12, 88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)
        return frame

    def latest(self):
        with self.lock:
            return self.jpeg

    def close(self):
        self.stop = True
        self.cam.close()


def make_handler(prod):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith('/meta'):
                body = ('{"width":%d,"height":%d,"fps":%.2f,"quality":%d,"raw":%s}'
                        % (prod.width, prod.height, prod.fps, prod.quality,
                           'true' if prod.raw else 'false')).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith('/stream'):
                self.send_response(200)
                self.send_header('Content-Type',
                                 'multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    while True:
                        jpg = prod.latest()
                        if jpg:
                            self.wfile.write(BOUNDARY % len(jpg))
                            self.wfile.write(jpg)
                        time.sleep(0.03)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(INDEX)))
            self.end_headers()
            self.wfile.write(INDEX)

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8090)
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=720)
    ap.add_argument('--quality', type=int, default=80)
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--sharp', action='store_true',
                    help='overlay a live sharpness reading, for manual focus')
    ap.add_argument('--flip', action='store_true',
                    help='horizontal flip (the sensor flip is locked at 1)')
    a = ap.parse_args()

    prod = Producer(a.width, a.height, a.quality, a.raw, sharp=a.sharp, flip=a.flip)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(prod))
    srv.daemon_threads = True
    print('preview: http://127.0.0.1:%d/   (%dx%d, correction=%s)'
          % (a.port, a.width, a.height, 'off' if a.raw else 'on'))
    print('on the PC: ssh -L %d:127.0.0.1:%d board' % (a.port, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        prod.close()
        srv.server_close()


if __name__ == '__main__':
    main()
