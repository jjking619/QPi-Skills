#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Timing-register tool for IMX219 (Quectel Pi M2 / RK3576)

Why this exists:
    The stock driver only exposes pixel_rate / hblank as read-only and clamps
    vblank at 1763, so the frame rate cannot be changed through V4L2. The
    sensor's own frame-length / line-length registers can, however, be written
    from user space.

Facts established by measurement (don't re-learn them the hard way):
    1. The sensor sits on i2c-5 @0x10 and uses 16-bit register addresses -> raw
       i2ctransfer messages are required; i2cget's 8-bit addressing reads nothing.
    2. The driver powers the sensor down when it is idle and I2C then returns
       ENXIO. The stream must be running before any access.
    3. The driver does not know about the values written here; when the stream
       stops it rewrites its own mode table -> the change is undone by itself.

Usage:
    camera_regs.py dump [--out f.json]           # read a snapshot
    camera_regs.py set --vts 1120 [--hts 2800]   # change one or both
    camera_regs.py restore FILE                  # write a snapshot back
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

BUS = int(os.environ.get('IMX219_I2C_BUS', '5'))
ADDR = int(os.environ.get('IMX219_I2C_ADDR', '0x10'), 0)
I2C = os.environ.get('I2C_TRANSFER', '/usr/sbin/i2ctransfer')

# IMX219 registers (Sony 10-bit family, 16-bit addresses)
REG = {
    'mode': 0x0100,   # 1 byte  0x01 = streaming
    'expo': 0x015A,   # 2 bytes coarse integration time (lines)
    'gain': 0x0157,   # 1 byte  analogue gain
    'vts':  0x0160,   # 2 bytes frame length (incl. blanking)
    'hts':  0x0162,   # 2 bytes line length (incl. blanking)
}
WIDTH = {'mode': 1, 'gain': 1, 'expo': 2, 'vts': 2, 'hts': 2}


def _sudo(args, pw, timeout=8):
    """Run a command through sudo -S; returns (rc, stdout, stderr)."""
    pw = pw or os.environ.get('SUDO_PW', '')
    p = subprocess.run(['sudo', '-S'] + args, input=(pw + '\n').encode(),
                       capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'ignore'), p.stderr.decode('utf-8', 'ignore')


def read_reg(name, pw=None):
    reg = REG[name]
    n = WIDTH[name]
    cmd = [I2C, '-y', '-f', str(BUS),
           'w2@0x%02x' % ADDR, '0x%02x' % (reg >> 8), '0x%02x' % (reg & 0xFF),
           'r%d' % n]
    rc, out, err = _sudo(cmd, pw)
    if rc != 0 or 'Error' in out:
        raise IOError('%s read failed: %s%s' % (name, out.strip(), err.strip()[-80:]))
    vals = [int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', out)]
    if len(vals) < n:
        raise IOError('%s parse failed: %r' % (name, out))
    v = 0
    for b in vals[:n]:
        v = (v << 8) | b
    return v


def write_reg(name, value, pw=None):
    reg = REG[name]
    n = WIDTH[name]
    if n == 2:
        payload = ['0x%02x' % (reg >> 8), '0x%02x' % (reg & 0xFF),
                   '0x%02x' % ((value >> 8) & 0xFF), '0x%02x' % (value & 0xFF)]
        wlen = 4
    else:
        payload = ['0x%02x' % (reg >> 8), '0x%02x' % (reg & 0xFF), '0x%02x' % (value & 0xFF)]
        wlen = 3
    cmd = [I2C, '-y', '-f', str(BUS), 'w%d@0x%02x' % (wlen, ADDR)] + payload
    rc, out, err = _sudo(cmd, pw)
    if rc != 0 or 'Error' in out:
        raise IOError('%s write failed: %s%s' % (name, out.strip(), err.strip()[-80:]))
    return True


def dump(pw=None, retries=3):
    out = {}
    for name in REG:
        for i in range(retries):
            try:
                out[name] = read_reg(name, pw)
                break
            except IOError:
                if i == retries - 1:
                    out[name] = None
                time.sleep(0.15)
    return out


def fps_from(vts, hts, pixel_rate=137_600_000):
    return pixel_rate / float(hts * vts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['dump', 'set', 'restore'])
    ap.add_argument('file', nargs='?')
    ap.add_argument('--vts', type=int)
    ap.add_argument('--hts', type=int)
    ap.add_argument('--out')
    ap.add_argument('--sudo-pw', default=os.environ.get('SUDO_PW', ''),
                    help='sudo password; prefer passing it via the SUDO_PW environment variable')
    a = ap.parse_args()

    if a.cmd == 'dump':
        d = dump(a.sudo_pw)
        print(json.dumps(d, indent=2))
        if d.get('vts') and d.get('hts'):
            print('current VTS=%d HTS=%d -> theoretical %.2f fps'
                  % (d['vts'], d['hts'], fps_from(d['vts'], d['hts'])))
        path = a.out or a.file
        if path:
            with open(path, 'w') as f:
                json.dump(d, f, indent=2)
            print('snapshot saved: %s' % path)
        return 0

    if a.cmd == 'set':
        before = dump(a.sudo_pw)
        print('before:', before)
        try:
            if a.vts:
                write_reg('vts', a.vts, a.sudo_pw)
            if a.hts:
                write_reg('hts', a.hts, a.sudo_pw)
        except IOError as e:
            print('write failed:', e)
            return 2
        after = dump(a.sudo_pw)
        print('after:', after)
        if after.get('vts') and after.get('hts'):
            print('theoretical fps = %.2f (was %.2f)'
                  % (fps_from(after['vts'], after['hts']),
                     fps_from(before['vts'], before['hts'])))
        print('rollback: stop the stream (the driver rewrites its mode table), or '
              'camera_regs.py set --vts %s --hts %s' % (before.get('vts'), before.get('hts')))
        return 0

    if a.cmd == 'restore':
        if not a.file:
            sys.exit('restore needs a snapshot file')
        d = json.load(open(a.file))
        for k in ('vts', 'hts'):
            if d.get(k):
                write_reg(k, d[k], a.sudo_pw)
        print('restored from snapshot:', dump(a.sudo_pw))
        return 0


if __name__ == '__main__':
    sys.exit(main())
