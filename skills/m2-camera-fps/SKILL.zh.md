# M2 摄像头帧率调优（寄存器级，不重编内核）

本文所有数值都在 **Quectel Pi M2（RK3576）+ IMX219** 上实测。收益来自**出流期间**通过 I2C 写 Sony 传感器自身的时序寄存器 —— 不碰 `boot.img`、不碰分区、不重编驱动。停流后驱动按内置模式表重写，所以「停流再开流」就是回退。

**先记住这三条**

1. **帧率公式**：`fps = pixel_rate / (HTS × VTS)`，`pixel_rate = 137.6 MHz`（`link-frequencies = 344 MHz/lane × 2 lane`，只读）。出厂 `HTS=3448`、`VTS=1763` → **22.64 fps**。
2. **VTS 只是帧率上限，曝光（EXPO）才是实际帧率的决定者。** 只降 VTS 而不动曝光，会被 AE 拉长曝光锁在 ~25 fps。
3. **最稳的收益配置**：`VTS=1096` + `EXPO=640`，`HTS` 保持 3448 → **36.42 fps（+60.9%）**。

## 什么时候使用

- 需要提升 M2 上 IMX219 / IMX477 的采集帧率
- 需要测量/验证摄像头实际帧率，而不是相信容器标称
- 需要远程看实时画面（SSH 隧道 + MJPEG）
- 需要用 `mpph264enc` 硬件编码录制
- 需要平滑数字变焦，或「检测框驱动变焦跟随」
- 排查 IMX219 的 I2C 访问失败、V4L2 协商失败、GStreamer 挂起
- 不适用：其它 SoC 或其它传感器 —— 下面的寄存器映射与驱动限制都是本板专属

## 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| 板子 | Quectel Pi M2（RK3576） | `cat /proc/device-tree/compatible` |
| 内核 | 6.1.118-rt36 或兼容 | `uname -a` |
| 摄像头 | IMX219 绑定到 `/dev/video51`（camera1） | `v4l2-ctl -d /dev/video51 --list-formats-ext` |
| 工具 | `i2ctransfer`、`v4l2-ctl`、`python3-opencv`、GStreamer 1.26+ 含 Qt5 绑定 | `which i2ctransfer v4l2-ctl gst-launch-1.0` |
| 权限 | `i2ctransfer` 需要 root → 脚本用 `sudo -S`，密码走 `SUDO_PW` | — |

```bash
sudo apt install -y build-essential v4l-utils i2c-tools python3-opencv \
     gstreamer1.0-tools gstreamer1.0-plugins-good python3-gi
```

先把脚本拷到板端（见「脚本资产」）：

```bash
cp scripts/*.py ~/
export SUDO_PW='<你的 sudo 密码>'   # 不要写进文件
```

## 执行流程

**① 环境自检 —— 三个没人写进文档的变量**

```bash
ls -l /dev/video* /dev/v4l-subdev*
v4l2-ctl -d /dev/video51 --list-formats-ext

export GST_V4L2_FORCE_LIBV4L2=0
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/run/user/1000

gst-launch-1.0 v4l2src device=/dev/video51 ! video/x-raw,format=NV12,width=1280,height=720 ! fakesink
```

三个变量缺一个都可能失败，缺 `GST_V4L2_FORCE_LIBV4L2` 的典型症状是**无声挂起**。报 `1640×1232 not-negotiated` 不是 bug —— 本板上限就是 1920×1080。

**② 先算，别先试**

从设备树与 `v4l2-ctl --list-ctrls-menus` 取出 `link-frequencies` / `pixel_rate` / `htotal` / `vtotal`，算出理论帧率与**有效像素时钟利用率**。出厂：`137_600_000 / (3448 × 1763) = 22.64`；垂直消隐 683 行占**帧时 38.7%**，水平消隐 1528 像素占**行时 44.3%**，综合利用率仅 **34.7%**。先算出「时间亏在哪里」，才知道往哪拿。

**③ 验证寄存器可访问 —— 整个方案的地基**

```bash
# 终端 1：保持出流（传感器空闲时被驱动断电，I2C 直接返回 ENXIO）
gst-launch-1.0 v4l2src device=/dev/video51 ! video/x-raw,format=NV12,width=1280,height=720 ! fakesink

# 终端 2：读时序寄存器
python3 ~/camera_regs.py dump
```

期望输出：

```json
{ "mode": 1, "expo": 1596, "gain": 96, "vts": 1763, "hts": 3448 }
current VTS=1763 HTS=3448 -> theoretical 22.64 fps
```

读回值必须与第 ② 步算出的完全吻合。对不上说明寄存器映射错了，后面全都白搭。

两条实现约束，**不要改**：
- IMX219 是 **16 位寄存器地址** → 必须用 `i2ctransfer` 发原始报文（`w2@0x10` + 2 字节地址 + `r2`），`i2cget` 的 8 位寻址读不到。
- 工具在 `/usr/sbin/i2ctransfer`，脚本用绝对路径调用（可用 `I2C_TRANSFER` 覆盖）。

**④ 逐档实验，保留每一档的证据**

`fps_hack.py` 在 fakesink 的 sink pad 挂 probe，记录**每帧到达时刻**，取**中位帧间隔**换算 fps（不看容器标称、不受缓冲影响），并抓改前/改后各一帧留证。

```bash
python3 ~/fps_hack.py --vts 1120 --width 1280 --height 720               # 第 1 档：只降 VTS
python3 ~/fps_hack.py --vts 1120 --expo 800 --width 1280 --height 720    # 第 2 档：VTS + 压曝光
python3 ~/fps_hack.py --vts 1096 --expo 640 --width 1280 --height 720    # 第 3 档：最终配置
```

| 档位 | 寄存器 | 理论 fps | 实测 fps | 说明了什么 |
|---|---|---|---|---|
| 出厂 | — | 22.64 | **22.64** | 基线 |
| 只降 VTS | `vts=1120` | 35.63 | **24.94** | ⚠️ 被曝光锁死：AE 设 1596 行 ≈ 40 ms，比新帧长（28 ms）还长 |
| VTS + 压曝光 | `vts=1120 expo=800` | 35.65 | **35.65** | 模型首次对齐（偏差 ≤0.02 fps） |
| 最终 | `vts=1096 expo=640` | 36.41 | **36.42** | **+60.9%** |

**⑤ 两条不可违反的铁律**

> **① 先预热再计时。** 启动开销混进平均值能造出约 7% 的假损失 —— 软编曾被误测为「比硬编慢 9%」，同口径重测后 1080p 硬编其实**快 51%**。
>
> **② 调完时序必须抽帧看画面。** HTS 压到 3328 时报 37.73 fps，但画面满屏彩条、码率只有 2 MB/12 s（正常 8 MB）—— **帧率是真的，画面是坏的**。

HTS 边界实测：3448 正常（采用）· 3360 正常 · 3328 画面损坏 · 3296 及以下直接断流。所以 `HTS` 保持不动。

**⑥ 确认可回退**

停流后重新开流，再读寄存器：`vts` 回到 **1763**、`hts` 回到 **3448**（驱动按内置模式表重写了一遍）。全程没有碰 boot 镜像、分区、内核 —— 最坏情况就是断电重启。

**⑦ 配套能力** —— 录制、变焦、色彩校正、远程预览见下文「脚本资产」与「配套能力」。

## 脚本资产

| 脚本 | 用途 | 额外依赖 |
|---|---|---|
| `camera_regs.py` | 读 / 写 / 按快照恢复时序寄存器（`dump`、`set --vts … --hts …`、`restore FILE`） | `i2ctransfer` + sudo |
| `fps_hack.py` | 流中改寄存器并用 pad probe 测真实帧率，存改前/改后帧图 | PyGObject、GStreamer |
| `rec_hw.py` | 硬件 H.264 录制（`mpph264enc`），可把帧率烧进画面 | PyGObject、GStreamer、OpenCV |
| `cam_zoom.py` | 软件平滑变焦（`push`）与检测框跟随（`follow`） | GStreamer、OpenCV |
| `cam_lsc.py` | 采集模块：静态 LSC 增益图 + 每帧全局白平衡 | OpenCV、NumPy |
| `lsc_calib.py` | 对着均匀白/灰表面标定 LSC → `~/lsc_map.npz` | OpenCV、NumPy |
| `lsc_stream.py` | 已校正的 MJPEG 预览（HTTP），可选锐度/帧率 HUD 与软件镜像 | OpenCV、NumPy |

所有脚本共用同一组环境变量覆盖，避免把某一块板子的路径写死：

| 变量 | 默认 | 用途 |
|---|---|---|
| `SUDO_PW` | 空 | sudo 密码（`i2ctransfer` 需要 root） |
| `CAM_DEV` | `/dev/video51` | 摄像头设备节点 |
| `IMX219_I2C_BUS` | `5` | 传感器 I2C 总线号 |
| `IMX219_I2C_ADDR` | `0x10` | 传感器 I2C 地址 |
| `I2C_TRANSFER` | `/usr/sbin/i2ctransfer` | `i2ctransfer` 路径 |
| `LSC_MAP` | `~/lsc_map.npz` | LSC 标定图 |

## 配套能力

**硬件编码录制 —— `rec_hw.py`。** 链路 `CameraLSC → appsrc → mpph264enc → h264parse → mp4mux`，**PTS 用墙钟时间**，不用「帧序号 / 标称帧率」，这样 mp4 时长 = 真实时长，任何播放器都能独立核对。

```bash
python3 ~/rec_hw.py --seconds 10 --hud     # --hud 把帧率烧进画面
python3 ~/rec_hw.py --raw --seconds 10     # 不校正，做对比基线
ffprobe -v error -show_entries stream=nb_frames,avg_frame_rate -of default=nw=1 out.mp4
```

**平滑变焦与检测框跟随 —— `cam_zoom.py`。** 硬件 `VIDIOC_S_CROP` **只在开流时生效**（流中改 ioctl 不报错、读回也变，画面纹丝不动），所以平滑变焦只能软件做。倍率与中心点都做**指数逼近**（`alpha = 0.18`）：目标值是「指令」、画面是「状态」，永不跳变。

```bash
python3 ~/cam_zoom.py --mode push   --seconds 12   # 1× → 3× → 1×，无黑屏
python3 ~/cam_zoom.py --mode follow --seconds 12   # 模拟目标框绕圈，镜头跟随
```

`follow_box(x, y, w, h, fill=0.62)` 让框稳定占画面 62%；**框坐标必须先经 `to_screen()` 映射**（crop 后画布尺寸变了）。接真实检测器就是把模拟框换成 YOLO 输出。帧率代价：不变焦 32.41 · 推拉 31.28（−3.5%）· 跟随 30.13（−5.6%）。实用上限：**720p ≤ 2×，1080p ≤ 3×**（有效像素 ≥ 640×360）。

**色彩校正 —— `cam_lsc.py` / `lsc_calib.py`。** 分工是：**LSC 是固定物理量**（标定一次存静态增益图，每帧查表相乘），**白平衡每帧估**。

```bash
python3 ~/lsc_calib.py   # 对着均匀白/灰表面 → ~/lsc_map.npz + 改前/改后 jpg
```

`wb=False` 只留 LSC、白平衡交给 ISP 的 AWB —— 画面有大面积彩色物体时用这个。

> **白平衡必须在 LSC 之后估计。** 否则 LSC 改变的全画面 R/G 均值被算漏，实测残留 0.90 而非 1.00。

**远程预览 —— `lsc_stream.py`。** 板上跑 HTTP 服务绑 `127.0.0.1:8090`，隧道要在 **PC 端**开（不是板端）：

```bash
# PC 端
ssh -L 8090:127.0.0.1:8090 board
# 浏览器 → http://127.0.0.1:8090/

# 板端（必须 python3 -u，否则输出被缓冲、读数滞后）
python3 -u ~/lsc_stream.py --port 8090 --width 1280 --height 720 --quality 60 --sharp --flip --fps-hud
```

`--sharp` 是锐度 HUD（中央 50% 拉普拉斯方差 + 峰值条），`--flip` 软件镜像，`--fps-hud` 显示帧率。MJPEG 逐帧独立压缩，**带宽实测**：720p 质量 85 = 30.0 Mbps、质量 60 = 16.9 Mbps、640×360 质量 60 = 6.1 Mbps。**远程看流，带宽比画质重要。**

## 实测数据

| 路径 | 分辨率 | fps |
|---|---|---|
| 纯采集（raw） | 720p | **36.42**（上限） |
| 带校正录制，软编 `mp4v` | 720p | 22.60 |
| 带校正录制，硬编 `mpph264enc` | 720p | 22.65（编码到顶） |
| 纯采集 | 1080p | 16.00 |
| 软编录制 | 1080p | 11.71 |
| 硬编录制（BGR 路径） | 1080p | **17.70**（+51%） |
| 硬编 + YUV 域 LSC 快路径 | 1080p | **28.19**（白平衡不准） |

1080p 软件链路分段耗时（合计 49.4 ms）：pipe 读帧 18.55 · NV12→BGR 2.24 · 白平衡 1.61 · **LSC 26.23 ms**。LSC 慢的根因是 `cv2.multiply(uint8, uint16, scale)` 属混类型运算，OpenCV 内部退到浮点慢路径。

色彩：出厂 `R/G ≈ 1.30`（全局偏品红），径向 `0.838`（中心）→ `1.074`（边角），镜头暗角本身仅约 13%；ISP 直出 `R/G = 0.998`（AWB 正常，**证明偏色不是缺 LSC 造成的**）；校正后 `R/G = B/G = 1.000`。YUV 域白平衡偏差 `R/G = 1.24` —— 能换速度，不能换准确度。

远程开发优化前后：板端 Firefox 渲染本地 Web 界面吃 1.18 GB 内存 + 184% CPU；改用 `ssh -L` 让 PC 渲染后，内存 3.26 → 1.34 GB，CPU 空闲率 42.6% → 96.1%。

## 板级与驱动事实

| 项 | 状态 |
|---|---|
| SoC / 系统 | RK3576（4×Cortex-A72 + 4×Cortex-A53），Debian，内核 6.1.118-rt36 |
| 网络 | 只有 Wi-Fi，无以太网口；出厂只监听 TCP 22 → 远程方案只能走 SSH 隧道或自建服务 |
| 摄像头节点 | `/dev/video51` = camera1 = `m01_b_imx219`（i2c-5，在用）；`/dev/video33` = camera0，未绑传感器，不可用 |
| `pixel_rate` / `htotal` | **只读** 137,600,000 / 3448 |
| `vblank` | 往大改有效，往小改被钳位回 1763 |
| `S_PARM` / `G_PARM` | **未实现**（`Inappropriate ioctl`）；`ENUM_FRAME_SIZE` 空；没有帧率控制项 |
| `horizontal_flip` | **锁在 1**（空闲写 0 开流 0 帧；流中写 EBUSY）→ 只能软件 `cv2.flip` |
| 传感器控制项 | 无 focus、无 sharpness（IMX219 定焦硬连接） |
| 曝光上限 | 1759 行 ≈ 44 ms |
| 裸 Bayer 位深 | 10 bit，无 8 bit 通道 |
| OpenCV | 4.10.0，NEON FP16；`cv2.data` 缺失 → Haar 不可用，重推理走 RKNN |
| 3A 服务 | `rkaiq_3A` —— **不能停**（停了画面塌，均值 12.9） |

22.64 fps 是**这套板子驱动配置的天花板，不是传感器的极限** —— 树莓派同款 IMX219 的 1080p 能到 47.57 fps。

## 已被实测否决的方案（别重蹈）

| 方案 | 实测结果 | 结论 |
|---|---|---|
| `cam fast`（每 0.25 s 重写曝光） | 画面明暗闪烁，帧率反降到 25 | 删除 |
| HTS 压到 3328 | 37.73 fps 但满屏彩条、码率 2 MB/12 s | 否决 |
| 改 IQ `calibdb.tableAll`（28 条真实标定记录） | 中心单格 1024→1400（+36.7%）→ 输出 0.986 无响应 | 路封死 |
| 改 IQ `stMan.dyn.meshGain` + `opMode=MANUAL` | 155.61 → 154.83 | 路封死 |
| 停 `rkaiq_3A` | 画面塌，均值 12.9 | 不可停 |
| 硬件改 `horizontal_flip` | 空闲写 0 开流 0 帧；流中写 EBUSY | 只能软件 `cv2.flip` |
| 用树莓派 5V/5A 电源解决 HDMI 不亮 | 仍不亮 | 不是电源问题 |

IQ 实验的判据是 `v4l2-ctl -d /dev/v4l-subdev9 -c test_pattern=1`（彩条）+ **逐像素求比值、按 17×17 分块统计** —— 输出完全静止的图案把 AE/AWB/场景变化全消掉，实测噪声恰为 0（289 格全 1.000），任何 1% 改动藏不住。用完记得 `test_pattern=0` 复位。判断亮度分布也必须在彩条下做，实拍画面会被内容污染。

## 常见坑

- **曝光才是闸门，不是 VTS。** 降了 VTS 帧率不涨，就在同一步把 `expo` 一起降。
- **只有出流时才能读寄存器。** 传感器空闲被断电，I2C 返回 ENXIO。
- **8 位寻址的 `i2cget` 读不到 IMX219。** 16 位寄存器地址必须用 `i2ctransfer` 原始报文。
- **不要靠压 `HTS` 追帧率**：数字涨了、画面坏了。每次改时序都要同时核对帧率与画面。
- **计时前先预热**，否则启动开销会伪装成性能差异。
- **硬件 `VIDIOC_S_CROP` 是开流参数**，流中改读回「已生效」，实际不动。
- **白平衡要在 LSC 之后估**，不能反过来。
- **不要周期性重写曝光** —— 与 AE 每帧写入冲突。
- **硬件翻转这条路不通**，镜像只能软件做，接受代价。
- **PTS 只能用墙钟时间。** 帧序号 ÷ 标称帧率会让录制时长依赖封装器。
- **SSH 隧道在 PC 端执行。** 在板端敲 `ssh -L …` 是无效的，但看起来像成功了。
- **长跑的东西都加 `python3 -u`**，否则读数在退出时才一次性吐出来。
- **包装脚本里别写死 `/home/<user>`**，板子可能以 root 运行、`HOME` 也不同。

## 验收

- [ ] 出流状态下读回的 `vts` / `hts` 与公式计算值吻合（基线 22.64 fps）
- [ ] 最终配置在 720p 下按中位帧间隔测得约 36.4 fps
- [ ] 改完抽帧看画面正常（不是彩条），录制码率在正常量级
- [ ] 停流 → 再开流后寄存器恢复 `vts=1763` / `hts=3448`（回退已验证）
- [ ] `ffprobe` 读出的 mp4 时长等于墙钟录制时长
- [ ] 远程预览只能经 PC 端隧道访问
- [ ] `rkaiq_3A` 仍在运行；用过彩条则 `test_pattern` 已复位为 0
