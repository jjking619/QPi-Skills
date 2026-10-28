#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure a 2D lens-shading (LSC) gain map from a uniform field.

Why this works without knowing the scene colour:
  the map is built as  (ratio at centre) / (ratio in block), so any uniform
  colour cast of the scene cancels out. What remains is purely the radial /
  spatial non-uniformity of the optical + ISP chain.

Output:
  ~/lsc_map.npz   gain maps (block grid) for R and B relative to G
  ~/lsc_map.png   visual preview of the maps
  stdout          radial colour ratios before vs after, and suggested global WB

Usage: lsc_calib.py [frames] [blocks_x]
"""
import subprocess
import sys

import cv2
import numpy as np

W, H = 1920, 1080
FB = W * H * 3 // 2
N = int(sys.argv[1]) if len(sys.argv) > 1 else 9
BX = int(sys.argv[2]) if len(sys.argv) > 2 else 64
BY = max(2, BX * H // W)


def capture(n=N):
    cmd = ['gst-launch-1.0', '-q', 'v4l2src', 'device=' + __import__('os').environ.get('CAM_DEV','/dev/video51'), 'num-buffers=%d' % n,
           '!', 'video/x-raw,format=NV12,width=%d,height=%d' % (W, H), '!', 'fdsink', 'fd=1']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    out = []
    for _ in range(n):
        buf = b''
        while len(buf) < FB:
            c = p.stdout.read(FB - len(buf))
            if not c:
                break
            buf += c
        if len(buf) == FB:
            nv = np.frombuffer(buf, np.uint8).reshape(H * 3 // 2, W)
            out.append(cv2.cvtColor(nv, cv2.COLOR_YUV2BGR_NV12))
    p.terminate()
    if not out:
        raise SystemExit('capture failed')
    return np.median(np.stack(out).astype(np.float32), axis=0)


def block_means(img, bx=BX, by=BY):
    """Downsample to a block grid -> (by, bx, 3) means in BGR order."""
    small = cv2.resize(img, (bx, by), interpolation=cv2.INTER_AREA)
    return small.astype(np.float64)


def radial_bins(ratio_map, bins=6):
    h, w = ratio_map.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    idx = np.clip((r * bins).astype(int), 0, bins - 1)
    return [ratio_map[idx == k].mean() if (idx == k).any() else np.nan for k in range(bins)]


img = capture()
gray = img.mean(axis=2)
sat = float((gray > 250).mean() * 100)
dark = float((gray < 12).mean() * 100)
print('capture ok: mean=%.1f  over=%.2f%%  under=%.2f%%  uniformity std/mean=%.3f'
      % (gray.mean(), sat, dark, gray.std() / max(gray.mean(), 1e-6)))
if sat > 3 or dark > 3:
    print('!! WARNING: the frame is over- or underexposed, so the calibration is unreliable'
          ' -> adjust exposure / lighting and rerun')

blk = block_means(img)
B, G, R = blk[..., 0], blk[..., 1], blk[..., 2]
G = np.maximum(G, 1.0)
rg = R / G
bg = B / G

# centre reference: average of the central 4x4 blocks
cy, cx = BY // 2, BX // 2
ref_rg = rg[cy - 2:cy + 2, cx - 2:cx + 2].mean()
ref_bg = bg[cy - 2:cy + 2, cx - 2:cx + 2].mean()
print('centre reference: R/G=%.4f  B/G=%.4f' % (ref_rg, ref_bg))

gain_r = np.clip(ref_rg / np.maximum(rg, 1e-6), 0.4, 2.5)
gain_b = np.clip(ref_bg / np.maximum(bg, 1e-6), 0.4, 2.5)
gain_r = np.clip(cv2.GaussianBlur(gain_r.astype(np.float32), (0, 0), 2.0), 0.4, 2.5)
gain_b = np.clip(cv2.GaussianBlur(gain_b.astype(np.float32), (0, 0), 2.0), 0.4, 2.5)

print('gain map  R: min=%.3f max=%.3f   B: min=%.3f max=%.3f'
      % (gain_r.min(), gain_r.max(), gain_b.min(), gain_b.max()))

# apply to the calibration frame itself, to show the residual
mr = cv2.resize(gain_r, (W, H), interpolation=cv2.INTER_LINEAR)
mb = cv2.resize(gain_b, (W, H), interpolation=cv2.INTER_LINEAR)
corr = img.copy()
corr[..., 0] = np.clip(img[..., 0] * mb, 0, 255)
corr[..., 2] = np.clip(img[..., 2] * mr, 0, 255)


def stats(im, tag):
    b, g, r = [im[..., i].astype(np.float64) for i in range(3)]
    g = np.maximum(g, 1e-6)
    rr, bb = r / g, b / g
    rb, bb_ = radial_bins(rr), radial_bins(bb)
    print('  %s R/G: %s' % (tag, ' '.join('%6.3f' % v for v in rb)))
    print('  %s B/G: %s' % (tag, ' '.join('%6.3f' % v for v in bb_)))
    return rr.mean(), bb.mean(), (max(rb) - min(rb)), (max(bb_) - min(bb_))


print()
print('=== radial profile: centre -> corner ===')
g0 = stats(img, 'before')
g1 = stats(corr, 'after ')
print()
print('  radial spread  R/G: %.3f -> %.3f' % (g0[2], g1[2]))
print('  radial spread  B/G: %.3f -> %.3f' % (g0[3], g1[3]))

# suggested global WB, expressed as multipliers on R and B
rr, bb, _, _ = g1
print()
print('  global after correction R/G=%.3f  B/G=%.3f' % (rr, bb))
print('  suggested global white-balance gains: R x %.3f   B x %.3f   (assuming a neutral centre)'
      % (1.0 / rr, 1.0 / bb))

np.savez(__import__('os').path.join(__import__('os').path.expanduser('~'), 'lsc_map.npz'), gain_r=gain_r, gain_b=gain_b, bx=BX, by=BY,
         ref_rg=ref_rg, ref_bg=ref_bg,
         wb_r=1.0 / rr, wb_b=1.0 / bb)

# preview: scale maps to 0..255 for viewing
def to_u8(m):
    return np.clip((m - 0.8) / 0.4 * 255, 0, 255).astype(np.uint8)

prev_r = cv2.applyColorMap(to_u8(gain_r), cv2.COLORMAP_TURBO)
prev_b = cv2.applyColorMap(to_u8(gain_b), cv2.COLORMAP_TURBO)
prev_r = cv2.resize(prev_r, (W // 2, H // 2), interpolation=cv2.INTER_NEAREST)
prev_b = cv2.resize(prev_b, (W // 2, H // 2), interpolation=cv2.INTER_NEAREST)
cv2.putText(prev_r, 'gain R', (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
cv2.putText(prev_b, 'gain B', (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
cv2.imwrite(__import__('os').path.join(__import__('os').path.expanduser('~'), 'lsc_map.png'), np.vstack([prev_r, prev_b]))
cv2.imwrite(__import__('os').path.join(__import__('os').path.expanduser('~'), 'lsc_before.jpg'), img.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
cv2.imwrite(__import__('os').path.join(__import__('os').path.expanduser('~'), 'lsc_after.jpg'), corr.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
print()
print('saved: ~/lsc_map.npz  ~/lsc_map.png  ~/lsc_before.jpg  ~/lsc_after.jpg')
