#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stepless zoom + smooth follow (software implementation)

Why software is mandatory:
    The hardware VIDIOC_S_CROP only takes effect when the stream starts (measured:
    changing it mid-stream does nothing), so "smooth continuous zoom" has to be
    done here: crop a block at the current magnification every frame, then scale
    it back to the output size. The ratio is continuously adjustable, no black
    frames.

Two ways to drive it:
    Manual push:  cam.push(2.5)                 # ease towards 2.5x
    Follow a box: cam.follow_box(x, y, w, h)    # keep the box's share of the frame stable,
                                                # deriving the magnification and the centering

Smoothing strategy:
    Both the magnification and the center point use exponential approach (walk
    alpha every frame), so nothing jumps. Changing the target only changes
    self.tz / self.tcx; the picture slides there by itself.

Usage (demo):
    python3 cam_zoom.py --mode push   --seconds 12   # push in -> hold -> pull out
    python3 cam_zoom.py --mode follow --seconds 12   # a simulated target moves, the lens follows
    python3 cam_zoom.py --mode off    --seconds 8    # correction only, to measure the baseline rate
"""
import argparse
import math
import os
import time

import cv2
import numpy as np

from cam_lsc import CameraLSC


class SmoothZoom:
    """Stepless zoom + smooth follow on an already corrected picture."""

    def __init__(self, out_w, out_h, max_zoom=4.0, alpha=0.18):
        self.ow, self.oh = out_w, out_h
        self.max_zoom = max_zoom
        self.alpha = alpha

        self.zoom = 1.0
        self.tz = 1.0
        self.cx, self.cy = 0.5, 0.5      # normalized center
        self.tcx, self.tcy = 0.5, 0.5

    # ---- control surface ----
    def push(self, target):
        """Set the target magnification; the picture approaches it exponentially."""
        self.tz = float(np.clip(target, 1.0, self.max_zoom))

    def look_at(self, nx, ny):
        """Set the target center (normalized 0-1)."""
        self.tcx = float(np.clip(nx, 0.0, 1.0))
        self.tcy = float(np.clip(ny, 0.0, 1.0))

    def follow_box(self, x, y, w, h, fill=0.75):
        """Follow a target box: make it occupy `fill` of the frame and center it."""
        if w < 8 or h < 8:
            return
        zx = self.ow * fill / float(w)
        zy = self.oh * fill / float(h)
        self.push(min(zx, zy))
        self.look_at((x + w / 2.0) / self.ow, (y + h / 2.0) / self.oh)

    def release(self):
        """Back to 1x, centered."""
        self.push(1.0)
        self.look_at(0.5, 0.5)

    # ---- per-frame work ----
    def apply(self, frame):
        a = self.alpha
        self.zoom += (self.tz - self.zoom) * a
        self.cx += (self.tcx - self.cx) * a
        self.cy += (self.tcy - self.cy) * a

        z = max(1.0, min(self.zoom, self.max_zoom))
        self.last_crop = (0, 0, self.ow, self.oh)
        if z <= 1.001:
            return frame

        cw = int(round(self.ow / z))
        ch = int(round(self.oh / z))
        # keep the crop window inside the frame
        x0 = int(round(self.cx * self.ow - cw / 2.0))
        y0 = int(round(self.cy * self.oh - ch / 2.0))
        x0 = max(0, min(x0, self.ow - cw))
        y0 = max(0, min(y0, self.oh - ch))
        roi = frame[y0:y0 + ch, x0:x0 + cw]
        self.last_crop = (x0, y0, cw, ch)
        return cv2.resize(roi, (self.ow, self.oh), interpolation=cv2.INTER_LINEAR)

    def to_screen(self, x, y, w, h):
        """Map a box from source coordinates to the zoomed output, so overlays land correctly."""
        x0, y0, cw, ch = getattr(self, 'last_crop', (0, 0, self.ow, self.oh))
        k = self.ow / float(cw)
        return (int((x - x0) * k), int((y - y0) * k),
                int(w * k), int(h * k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['off', 'push', 'follow'], default='push')
    ap.add_argument('--seconds', type=float, default=12.0)
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=720)
    ap.add_argument('--out', default=None)
    ap.add_argument('--vts', type=int, default=1096)
    ap.add_argument('--expo', type=int, default=640)
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--hw', action='store_true',
                    help='encode with mpph264enc (same methodology as rec_hw)')
    a = ap.parse_args()

    W, H = a.width, a.height
    out = a.out or os.path.join(os.path.expanduser('~'), time.strftime('zoom_%s_%%H%%M%%S.mp4' % a.mode))

    writer = None
    src = None
    pipe = None
    if a.hw:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        from rec_hw import bgr_to_nv12
        Gst.init(None)
        pipe = Gst.parse_launch(
            'appsrc name=src format=time is-live=false block=true max-bytes=8000000 '
            'caps=video/x-raw,format=NV12,width=%d,height=%d,framerate=30/1 '
            '! mpph264enc rc-mode=cbr bps=8000000 gop=-1 header-mode=1 '
            '! h264parse ! mp4mux ! filesink location=%s' % (W, H, out))
        src = pipe.get_by_name('src')
        pipe.set_state(Gst.State.PLAYING)
    else:
        writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*'mp4v'), 30.0, (W, H))
        if not writer.isOpened():
            raise SystemExit('VideoWriter failed to open')

    use = not a.raw
    zoomer = SmoothZoom(W, H, max_zoom=4.0)

    t_start = time.time()
    n = 0
    fps_now = 0.0
    fps_t0 = 0.0
    t0 = 0.0

    with CameraLSC(width=W, height=H, lsc=use, wb=use) as cam:
        for _ in range(10):
            cam.read()
        if a.vts or a.expo:
            try:
                import camera_regs as cr
                if a.expo:
                    cr.write_reg('expo', a.expo)
                if a.vts:
                    cr.write_reg('vts', a.vts)
            except Exception as e:
                print('register write failed (ignorable, the run becomes a baseline): %s' % e)

        t0 = time.time()
        fps_t0 = t0
        while True:
            el = time.time() - t0
            if el >= a.seconds:
                break
            ok, frame = cam.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)          # the sensor horizontal_flip is locked at 1

            # ---- drive the zoom ----
            if a.mode == 'push':
                # 0-4s push to 3x, 4-8s hold, 8-12s pull back to 1x
                if el < 4:
                    zoomer.push(1.0 + 2.0 * (el / 4.0))
                elif el < 8:
                    zoomer.push(3.0)
                else:
                    zoomer.push(max(1.0, 3.0 - 2.0 * ((el - 8.0) / 4.0)))
            elif a.mode == 'follow':
                # simulate a box circling the frame to exercise smooth follow
                radius = 0.18
                ang = el * 0.8
                bx = int((0.5 + radius * math.cos(ang)) * W) - 90
                by = int((0.5 + radius * math.sin(ang)) * H) - 90
                bw = bh = 180
                zoomer.follow_box(bx, by, bw, bh, fill=0.62)
            frame = zoomer.apply(frame)

            # ---- HUD ----
            if n % 8 == 0:
                now = time.time()
                fps_now = 8.0 / max(now - fps_t0, 1e-6)
                fps_t0 = now
            txt = 'FPS %.1f  ZOOM %.2fx  %s' % (fps_now, zoomer.zoom, a.mode.upper())
            cv2.rectangle(frame, (0, 0), (W, 40), (0, 0, 0), -1)
            cv2.putText(frame, txt, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (0, 255, 0), 2, cv2.LINE_AA)
            if a.mode == 'follow':
                radius = 0.18
                ang = el * 0.8
                bx = int((0.5 + radius * math.cos(ang)) * W)
                by = int((0.5 + radius * math.sin(ang)) * H)
                sx, sy, sw, sh = zoomer.to_screen(bx - 90, by - 90, 180, 180)
                cv2.rectangle(frame, (sx, sy), (sx + sw, sy + sh), (0, 255, 0), 2)

            if src is not None:
                data = np.ascontiguousarray(bgr_to_nv12(frame)).tobytes()
                buf = Gst.Buffer.new_allocate(None, len(data), None)
                buf.fill(0, data)
                pts = int((time.time() - t0) * Gst.SECOND)
                buf.pts = pts
                buf.dts = pts
                buf.duration = int(Gst.SECOND / 30)
                src.emit('push-buffer', buf)
            else:
                writer.write(frame)
            n += 1

    dt = time.time() - t0
    if src is not None:
        src.emit('end-of-stream')
        import time as _t
        deadline = _t.time() + 10
        bus = pipe.get_bus()
        while _t.time() < deadline:
            msg = bus.timed_pop_filtered(100 * Gst.MSECOND, Gst.MessageType.EOS)
            if msg is not None:
                break
        pipe.set_state(Gst.State.NULL)
    else:
        writer.release()
    size = os.path.getsize(out) if os.path.exists(out) else 0
    print('output: %s' % out)
    print('mode %s  %dx%d' % (a.mode, W, H))
    print('captured %d frames / steady-state %.2f s = %.2f fps' % (n, dt, n / dt if dt else 0))
    print('file %.2f MB' % (size / 1e6))


if __name__ == '__main__':
    main()
