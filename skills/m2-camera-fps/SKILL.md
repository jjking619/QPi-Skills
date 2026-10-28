---
name: m2-camera-fps
description: "Raise camera frame rate on Quectel Pi M2 (RK3576) with IMX219/IMX477 CSI sensors by writing Sony sensor timing registers (VTS / EXPO) over I2C while streaming: 22.64 to 36.42 fps with no kernel rebuild and automatic restore when the stream stops. Also covers honest frame-rate measurement, hardware H.264 recording, smooth digital zoom with detection-box follow, lens-shading correction, and MJPEG remote preview over an SSH tunnel. Use when increasing, measuring or verifying camera frame rate on the M2, or troubleshooting IMX219 I2C access, V4L2 negotiation and GStreamer streaming on Rockchip boards."
version: 0.1.0
author: "Quectel Pi"
license: MIT
platforms: [linux]
---

# M2 Camera Frame-Rate Tuning (register-level, no kernel rebuild)

Everything here is measured on a **Quectel Pi M2 (RK3576) + IMX219** board. The frame-rate gain comes from writing the Sony sensor's own timing registers over I2C while the stream is running — no `boot.img`, no partition, no driver rebuild. Sensor values are rewritten by the driver from its built-in mode table on the next stream start, so a stop/start is the rollback.

> **Provenance**: distilled from hands-on experience with the board. Every figure below was measured on real hardware — none of it comes from a spec sheet — and each "don't do this" is a dead end that was actually walked into first.

**Three facts to remember first**

1. **Frame-rate formula**: `fps = pixel_rate / (HTS × VTS)`, with `pixel_rate = 137.6 MHz` (`link-frequencies = 344 MHz/lane × 2 lanes`, read-only). Stock `HTS=3448`, `VTS=1763` → **22.64 fps**.
2. **VTS is only the ceiling; exposure decides the actual rate.** Lower VTS alone gets the exposure stretched by AE and pins you at ~25 fps.
3. **Best-working configuration**: `VTS=1096` + `EXPO=640`, `HTS` untouched → **36.42 fps (+60.9%)**.

## When to Use

- Raising capture frame rate on an M2 with an IMX219 / IMX477 CSI sensor
- Measuring or verifying the real frame rate instead of trusting the container's nominal value
- Watching the live picture remotely (SSH tunnel + MJPEG)
- Recording with the hardware encoder (`mpph264enc`)
- Smooth digital zoom, or "detection box drives the zoom"
- Diagnosing IMX219 I2C failures, V4L2 negotiation failures, GStreamer hangs
- Not for: other SoCs or other sensors — the register map and the driver limits below are board-specific

## Prerequisites

| Item | Requirement | Check |
|---|---|---|
| Board | Quectel Pi M2 (RK3576) | `cat /proc/device-tree/compatible` |
| Kernel | 6.1.118-rt36 or compatible | `uname -a` |
| Camera | IMX219 bound to `/dev/video51` (camera1) | `v4l2-ctl -d /dev/video51 --list-formats-ext` |
| Tools | `i2ctransfer`, `v4l2-ctl`, `python3-opencv`, GStreamer 1.26+ with Qt5 bindings | `which i2ctransfer v4l2-ctl gst-launch-1.0` |
| Privilege | `i2ctransfer` needs root → the scripts use `sudo -S` with the password from `SUDO_PW` | — |

```bash
sudo apt install -y build-essential v4l-utils i2c-tools python3-opencv \
     gstreamer1.0-tools gstreamer1.0-plugins-good python3-gi
```

Copy the scripts to the board first (see **Assets**):

```bash
cp scripts/*.py ~/
export SUDO_PW='<your sudo password>'   # never write it into a file
```

## Procedure

**① Environment self-check — the three variables nobody documents**

```bash
ls -l /dev/video* /dev/v4l-subdev*
v4l2-ctl -d /dev/video51 --list-formats-ext

export GST_V4L2_FORCE_LIBV4L2=0
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/run/user/1000

gst-launch-1.0 v4l2src device=/dev/video51 ! video/x-raw,format=NV12,width=1280,height=720 ! fakesink
```

All three variables are required; missing `GST_V4L2_FORCE_LIBV4L2` is the usual cause of a silent hang. A `1640×1232 not-negotiated` error is not a bug — this board tops out at 1920×1080.

**② Compute the ceiling before trying anything**

Read `link-frequencies` / `pixel_rate` / `htotal` / `vtotal` from the device tree and `v4l2-ctl --list-ctrls-menus`, then compute the theoretical rate and the **effective pixel-clock utilization**. Stock: `137_600_000 / (3448 × 1763) = 22.64`; vertical blanking (683 of 1763 lines) is **38.7 % of frame time**, horizontal blanking (1528 of 3448 px) is **44.3 % of line time**, combined utilization **34.7 %**. Knowing where the time is wasted is what tells you where to take it from.

**③ Prove register access — the foundation of the whole approach**

```bash
# terminal 1: keep a stream running (the sensor is powered down when idle → I2C returns ENXIO)
gst-launch-1.0 v4l2src device=/dev/video51 ! video/x-raw,format=NV12,width=1280,height=720 ! fakesink

# terminal 2: dump the timing registers
python3 ~/camera_regs.py dump
```

Expected:

```json
{ "mode": 1, "expo": 1596, "gain": 96, "vts": 1763, "hts": 3448 }
current VTS=1763 HTS=3448 -> theoretical 22.64 fps
```

The readback must match the values you computed in ②. If it doesn't, the register map is wrong and everything downstream is wasted.

Two implementation constraints, **do not change them**:
- IMX219 uses **16-bit register addresses** → raw `i2ctransfer` frames (`w2@0x10` + 2 address bytes + `r2`); `i2cget`'s 8-bit addressing cannot read them.
- The binary lives at `/usr/sbin/i2ctransfer` — call it by absolute path (`I2C_TRANSFER` overrides it).

**④ Walk the ladder, keeping the evidence of every step**

`fps_hack.py` attaches a probe to the fakesink pad, records **each frame's arrival time**, converts the **median inter-frame interval** to fps (no nominal container rate, no buffer distortion), and saves one frame before and after the change.

```bash
python3 ~/fps_hack.py --vts 1120 --width 1280 --height 720               # step 1: VTS only
python3 ~/fps_hack.py --vts 1120 --expo 800 --width 1280 --height 720    # step 2: VTS + exposure
python3 ~/fps_hack.py --vts 1096 --expo 640 --width 1280 --height 720    # step 3: final
```

| Step | Registers | Theory | Measured | What it proves |
|---|---|---|---|---|
| Stock | — | 22.64 | **22.64** | baseline |
| VTS only | `vts=1120` | 35.63 | **24.94** | ⚠️ exposure-locked: AE set 1596 lines ≈ 40 ms, longer than the new 28 ms frame |
| VTS + exposure | `vts=1120 expo=800` | 35.65 | **35.65** | model snapped into place (≤0.02 fps) |
| Final | `vts=1096 expo=640` | 36.41 | **36.42** | **+60.9 %** |

**⑤ Two iron rules**

> **① Warm up before timing.** Startup overhead inside the average invents a ~7 % fake loss. Software encoding once "measured 9 % slower than hardware"; re-measured on equal footing, 1080p hardware encoding is **51 % faster**.
>
> **② After touching timing, pull a frame and look at it.** Squeezing HTS to 3328 reports 37.73 fps while the picture is full-screen color bars at 2 MB/12 s instead of the usual 8 MB — **the frame rate is real, the picture is broken.**

HTS boundary, measured: 3448 normal (adopted) · 3360 normal · 3328 picture corrupted · 3296 and below drops the stream. So `HTS` stays untouched.

**⑥ Confirm rollback**

Stop the stream, start it again, dump the registers: `vts` is back to **1763** and `hts` to **3448** (the driver rewrote its mode table). Nothing touched the boot image, partitions or kernel — the worst case is a power cycle.

**⑦ Optional capabilities** — recording, zoom, color correction, remote preview: see **Assets** and **Capabilities** below.

## Assets

| Script | Purpose | Extra deps |
|---|---|---|
| `camera_regs.py` | Dump / write / restore the timing registers (`dump`, `set --vts … --hts …`, `restore FILE`) | `i2ctransfer` + sudo |
| `fps_hack.py` | Change registers mid-stream and measure the real fps from a pad probe; saves before/after frames | PyGObject, GStreamer |
| `rec_hw.py` | Hardware H.264 recording (`mpph264enc`), optional fps HUD burned into the frame | PyGObject, GStreamer, OpenCV |
| `cam_zoom.py` | Smooth software zoom (`push`) and detection-box follow (`follow`) | GStreamer, OpenCV |
| `cam_lsc.py` | Capture module: static LSC gain map + per-frame global white balance | OpenCV, NumPy |
| `lsc_calib.py` | Calibrate the LSC map against a uniform white/gray surface → `~/lsc_map.npz` | OpenCV, NumPy |
| `lsc_stream.py` | Corrected MJPEG preview over HTTP, optional sharpness / fps HUD, software mirror | OpenCV, NumPy |

All scripts read the same environment overrides, so one board's path doesn't harden into another's:

| Variable | Default | Meaning |
|---|---|---|
| `SUDO_PW` | empty | sudo password (`i2ctransfer` needs root) |
| `CAM_DEV` | `/dev/video51` | camera device node |
| `IMX219_I2C_BUS` | `5` | sensor I2C bus |
| `IMX219_I2C_ADDR` | `0x10` | sensor I2C address |
| `I2C_TRANSFER` | `/usr/sbin/i2ctransfer` | `i2ctransfer` path |
| `LSC_MAP` | `~/lsc_map.npz` | LSC calibration map |

## Capabilities

**Hardware recording — `rec_hw.py`.** Pipeline `CameraLSC → appsrc → mpph264enc → h264parse → mp4mux`. **PTS comes from the wall clock**, not frame index ÷ nominal fps, so the mp4 duration equals real time and any player can verify it independently.

```bash
python3 ~/rec_hw.py --seconds 10 --hud     # --hud burns the frame rate into the picture
python3 ~/rec_hw.py --raw --seconds 10     # no correction, as a comparison baseline
ffprobe -v error -show_entries stream=nb_frames,avg_frame_rate -of default=nw=1 out.mp4
```

**Smooth zoom and box follow — `cam_zoom.py`.** Hardware `VIDIOC_S_CROP` **only takes effect when the stream starts** (changing it mid-stream neither errors nor changes the picture, though it reads back the new value), so smooth zoom has to be software. Both the magnification and the center point use **exponential approach** (`alpha = 0.18`): the target is a command, the picture is a state, it never jumps.

```bash
python3 ~/cam_zoom.py --mode push   --seconds 12   # 1× → 3× → 1×, no black frames
python3 ~/cam_zoom.py --mode follow --seconds 12   # a simulated box circles, the lens follows
```

`follow_box(x, y, w, h, fill=0.62)` keeps the box at a stable 62 % of the frame; **box coordinates must go through `to_screen()` first** because cropping changes the canvas size. Feeding a real detector means replacing the simulated box with the YOLO output. Frame-rate cost: 32.41 (no zoom) · 31.28 push (−3.5 %) · 30.13 follow (−5.6 %). Practical limit: **720p ≤ 2×, 1080p ≤ 3×** (≥ 640×360 of real pixels).

**Color correction — `cam_lsc.py` / `lsc_calib.py`.** The split is: **LSC is a fixed physical quantity** (calibrate once, store a static gain map, multiply per frame), **white balance is estimated per frame**.

```bash
python3 ~/lsc_calib.py   # aim at a uniform white/gray surface → ~/lsc_map.npz + before/after jpgs
```

`wb=False` leaves LSC only and hands white balance back to the ISP's AWB — use that when the scene has large colored areas.

> **White balance must be estimated after LSC.** Otherwise the R/G shift introduced by LSC is missing from the estimate; measured residual 0.90 instead of 1.00.

**Remote preview — `lsc_stream.py`.** The board serves HTTP on `127.0.0.1:8090`; the tunnel is opened **on the PC**, not on the board:

```bash
# on the PC
ssh -L 8090:127.0.0.1:8090 board
# browser → http://127.0.0.1:8090/

# on the board (python3 -u, otherwise output is buffered and the readings lag)
python3 -u ~/lsc_stream.py --port 8090 --width 1280 --height 720 --quality 60 --sharp --flip --fps-hud
```

`--sharp` overlays a Laplacian-variance sharpness HUD (center 50 % plus a peak bar), `--flip` mirrors in software, `--fps-hud` shows the rate. MJPEG compresses every frame independently — **measured bandwidth**: 720p q85 = 30.0 Mbps, q60 = 16.9 Mbps, 640×360 q60 = 6.1 Mbps. **For remote viewing, bandwidth matters more than quality.**

## Measured Reference

| Path | Resolution | fps |
|---|---|---|
| Capture only (raw) | 720p | **36.42** (ceiling) |
| Recording with correction, software `mp4v` | 720p | 22.60 |
| Recording with correction, hardware `mpph264enc` | 720p | 22.65 (encoder ceiling) |
| Capture only | 1080p | 16.00 |
| Software encode, 1080p | 1080p | 11.71 |
| Hardware encode (BGR path), 1080p | 1080p | **17.70** (+51 %) |
| Hardware encode + YUV-domain LSC fast path | 1080p | **28.19** (white balance inaccurate) |

1080p software path segment cost (49.4 ms total): pipe read 18.55 · NV12→BGR 2.24 · white balance 1.61 · **LSC 26.23 ms**. The LSC cost is `cv2.multiply(uint8, uint16, scale)` — a mixed-dtype multiply that OpenCV routes through a floating-point slow path.

Color: stock `R/G ≈ 1.30` (global magenta cast), radial `0.838` center → `1.074` corner, lens vignetting itself only ~13 %; ISP output `R/G = 0.998` (AWB is fine, so the cast is not missing LSC); after correction `R/G = B/G = 1.000`. In the YUV domain white balance lands at `R/G = 1.24` — usable for speed, not for accuracy.

Remote-development before/after: board-side Firefox rendering a local web UI burned 1.18 GB + 184 % CPU; moving rendering to the PC over `ssh -L` took memory 3.26 → 1.34 GB and CPU idle 42.6 % → 96.1 %.

## Board and Driver Facts

| Item | State |
|---|---|
| SoC / OS | RK3576 (4×Cortex-A72 + 4×Cortex-A53), Debian, kernel 6.1.118-rt36 |
| Network | Wi-Fi only, no Ethernet; stock listens only on TCP 22 → every remote approach is an SSH tunnel or a self-hosted service |
| Camera nodes | `/dev/video51` = camera1 = `m01_b_imx219` (i2c-5, in use); `/dev/video33` = camera0, no sensor bound, unusable |
| `pixel_rate` / `htotal` | **read-only** 137,600,000 / 3448 |
| `vblank` | larger works, smaller is clamped back to 1763 |
| `S_PARM` / `G_PARM` | **not implemented** (`Inappropriate ioctl`); `ENUM_FRAME_SIZE` empty; no frame-rate control |
| `horizontal_flip` | **locked at 1** (writing 0 while idle → 0 frames; mid-stream → EBUSY) → software `cv2.flip` only |
| Sensor controls | no focus, no sharpness (fixed-focus IMX219) |
| Exposure ceiling | 1759 lines ≈ 44 ms |
| Bayer depth | 10-bit, no 8-bit path |
| OpenCV | 4.10.0 with NEON FP16; `cv2.data` missing → Haar cascades unusable, use RKNN |
| 3A service | `rkaiq_3A` — **must keep running** (stopping it collapses the picture, mean 12.9) |

22.64 fps is the **driver configuration's ceiling on this board, not the sensor's limit** — the same IMX219 on a Raspberry Pi reaches 1080p 47.57 fps.

## Approaches Already Disproved (don't repeat them)

| Approach | Measured result | Verdict |
|---|---|---|
| `cam fast` — rewrite exposure every 0.25 s | brightness flickers, frame rate drops back to 25 | removed |
| HTS to 3328 | 37.73 fps but full-screen color bars, 2 MB/12 s | rejected |
| IQ `calibdb.tableAll` (28 real calibration records) | center cell 1024→1400 (+36.7 %) → output 0.986, no response | dead end |
| IQ `stMan.dyn.meshGain` + `opMode=MANUAL` | 155.61 → 154.83 | dead end |
| Stopping `rkaiq_3A` | picture collapses, mean 12.9 | must not stop |
| Hardware `horizontal_flip` | idle write → 0 frames; mid-stream → EBUSY | software flip only |
| Raspberry Pi 5V/5A supply to fix a dark HDMI | still dark | not a power problem |

The IQ experiments were judged with `v4l2-ctl -d /dev/v4l-subdev9 -c test_pattern=1` (color bars) plus **pixel-by-pixel ratios over a 17×17 grid** — a completely static pattern cancels AE/AWB/scene changes, measured noise exactly 0 (289 cells all 1.000), so a 1 % change cannot hide. Reset with `test_pattern=0` afterwards. Judge brightness distributions only with the pattern in place; on live scenes they are dominated by content.

## Pitfalls

- **Exposure, not VTS, gates the rate.** If the frame rate refuses to move after lowering VTS, lower `expo` in the same step.
- **Read registers only while streaming.** The sensor is powered down when idle and I2C returns ENXIO.
- **8-bit `i2cget` cannot read IMX219.** 16-bit register addresses require raw `i2ctransfer` frames.
- **Never squeeze `HTS`** for extra fps: the numbers go up, the picture dies. Frame rate and picture quality must both be checked after every timing change.
- **Warm up before timing anything**, otherwise startup overhead shows up as a fake performance difference.
- **Hardware `VIDIOC_S_CROP` is a stream-start parameter.** Mid-stream changes read back as applied and do nothing.
- **Estimate white balance after LSC**, never before.
- **Don't rewrite exposure periodically** — it fights AE's per-frame writes.
- **Hardware flip is unreachable**; mirror in software and accept the cost.
- **PTS from the wall clock only.** Frame index ÷ nominal fps produces recordings whose duration depends on the serializer.
- **The SSH tunnel runs on the PC.** Running `ssh -L …` on the board is a no-op that looks like success.
- **`python3 -u` for anything long-running**, or every reading arrives in a batch at exit.
- **Don't hardcode `/home/<user>`** in wrapper scripts — the board may run as root with a different `HOME`.

## Verification

- [ ] `vts` / `hts` read back while streaming match the computed values (22.64 fps baseline)
- [ ] Final configuration measures ~36.4 fps by median inter-frame interval, in 720p
- [ ] A pulled frame after the change shows a normal picture, not color bars; recording bitrate is in the usual range
- [ ] Stop → start the stream returns `vts=1763` / `hts=3448` (rollback proven)
- [ ] Recorded mp4 duration from `ffprobe` equals the wall-clock recording time
- [ ] Remote preview reachable through the PC-side tunnel only
- [ ] `rkaiq_3A` still running; `test_pattern` reset to 0 if the pattern was used
