<div align="center">

# QPi-Skills

**面向日常工作流的技能集**

代码编写 · 仓库审查 · 项目复现 · 发布门禁 · Shell 与脚本健壮化 · 设备联调 · 云文档 API · 文档审计 · 交付物包 · M2 摄像头调优

[![Skills](https://img.shields.io/badge/skills-11-2f81f7?style=flat-square)](#skills)
[![Format](https://img.shields.io/badge/skills-plain%20markdown-8b5cf6?style=flat-square)](#skills)
[![Standard](https://img.shields.io/badge/Agent%20Skills-open%20format-0ea5e9?style=flat-square)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-MIT-16a34a?style=flat-square)](#license)

</div>

> 把日常里**重复且有判断力**的活儿，沉淀成 AI Agent 可直接加载执行的技能。
> 每个技能都是**自包含的 `SKILL.md`**：触发条件、可执行流程、实测坑、验收清单写在一起。当代码本身就是交付物时，技能目录里另带一个 `scripts/`；其余技能仍是单文件。没有隐藏资产、没有构建步骤，复制进 Agent 的技能目录即可使用。

---

<a id="toc"></a>

## 目录（Table of Contents）

| | 章节 |
|---|---|
| 📦 | [技能一览（Skills Overview）](#skills) |
| 🔗 | [交付主链](#build-chain) |
| ✍️ | [code-authoring 代码编写](#authoring) |
| 🔍 | [github-repo-review-and-design 仓库审查与设计](#code-review) |
| 🧪 | [project-reproduction 项目复现](#reproduction) |
| 🚀 | [prepublish-repo-audit 发布前审计](#prepublish) |
| 🪟 | [windows-shell-tooling Windows Shell 工具链](#win-shell) |
| 🔒 | [shell-script-hardening 脚本健壮化](#script-hardening) |
| 📱 | [adb-device-toolkit 设备联调](#adb) |
| 📄 | [feishu-docs-api 云文档 API](#feishu-api) |
| 📐 | [doc-consistency-audit 文档一致性审计](#doc-audit) |
| 🗃️ | [deliverable-pack 交付物包](#deliverable) |
| 🎥 | [m2-camera-fps M2 摄像头帧率调优](#camera) |
| ⚡ | [快速开始](#quickstart) |
| 🗂️ | [仓库结构](#layout) |
| 📐 | [设计约定](#conventions) |
| 📜 | [许可](#license) |

---

<a id="skills"></a>

## 技能一览（Skills Overview）

| 技能 | 包名 / 版本 | 解决什么问题 | 典型触发语 |
|:--|:--|:--|:--|
| ✍️ **代码编写** | `code-authoring`<br>`v0.1.0` | 注释规范（只写 why）+ **最小充分改动**纪律，让 diff 不被顺手改动淹没 | 写新功能、改他人代码之前 |
| 🔍 **仓库审查与设计** | `github-repo-review-and-design`<br>`v0.1.0` | **整仓分级审查**（评估档 / 发布档）+ 为新项目**设计目录结构** | 「看下这个仓库值不值得用」 |
| 🧪 **项目复现** | `project-reproduction`<br>`v0.1.0` | 按 README / 教程 / `install.sh` 逐步复现，报错按最优路径修复并**固化进文件** | 「按这份教程复现、部署、跑通」 |
| 🚀 **发布前审计** | `prepublish-repo-audit`<br>`v0.1.0` | 开源或交付前的**门禁**：可见性、密钥、内部标识、仓库卫生、历史残留 | 「这个仓能公开吗」 |
| 🪟 **Windows Shell** | `windows-shell-tooling`<br>`v0.1.0` | Windows + git-bash 的路径 / 换行 / 编码 / 落盘坑 | 命令在 git-bash 里行为不对 |
| 🔒 **脚本健壮化** | `shell-script-hardening`<br>`v0.1.0` | `install.sh` / 部署脚本**幂等、失败可诊断、成功不自欺** | 写或改一键安装脚本 |
| 📱 **设备联调** | `adb-device-toolkit`<br>`v0.1.0` | **adb** 认设备、执行身份、传文件校验、长任务脱离会话 | 连板子 / Android 设备调试 |
| 📄 **云文档 API** | `feishu-docs-api`<br>`v0.1.0` | REST 直写 / 同步 / 归档飞书云文档（docx / wiki / bitable） | 「改这篇飞书文档」「把 md 同步上云」 |
| 📐 **文档一致性审计** | `doc-consistency-audit`<br>`v0.1.0` | 一批文档 / 多语言镜像的**一致性检查 + 分级报告** | 「这批文档审一遍」 |
| 🗃️ **交付物包** | `deliverable-pack`<br>`v0.1.0` | 同一件事有三类读者（决策者 / 执行者 / 复核者），用固定五件套一次满足 | 任何需要交付的工作 |
| 🎥 **M2 摄像头调优** | `m2-camera-fps`<br>`v0.1.0` | M2 + IMX219 的**寄存器级帧率提升**（22.64 → 36.42 fps，不重编内核），含实测帧率、硬编录制、平滑变焦、LSC 校正与 SSH 隧道预览 | 「帧率太低」「实测真实帧率」「M2 相机 I2C / GStreamer 不通」 |

---

<a id="build-chain"></a>

## 交付主链

```text
写代码 ─► 审整仓 ─► 复现验收 ─► 发布门禁 ─► 交接留痕
code-authoring → github-repo-review-and-design → project-reproduction → prepublish-repo-audit → deliverable-pack
```

周边但常用：`windows-shell-tooling` 与 `shell-script-hardening`（环境与脚本）、`adb-device-toolkit`（设备）、`m2-camera-fps`（相机硬件）、`feishu-docs-api` 与 `doc-consistency-audit`（文档）。

---

<a id="authoring"></a>

### ✍️ 1. code-authoring —— 代码编写

**定位**：只管「产码阶段」的两件事 —— **注释该写什么**、**改动该有多大**。

**六条规则**：独立成篇、只管产码阶段；触发面覆盖任何生产代码的写或改；注释跟随文件既有语言（新文件默认英文）、只写 **why**；最小充分改动；改他人代码前先建现状快照；交付前自检范围、注释、是否真跑过。

| | 内容 |
|:--|:--|
| ✅ 白名单（必须做） | 输入校验、错误与异常处理、资源释放、被改函数的调用点同步更新、必要测试、格式化工具强制的改动 |
| ⛔ 黑名单（禁止顺手做） | 重新格式化 / 调换行、重命名、调整 import 顺序、加未被要求的日志与开关与抽象层、引入新依赖、改公共接口签名、跨文件大范围重排 |
| 🚫 底线 | 禁止为让测试通过而加特判 / hardcode / 注释掉断言 / 绕过校验 —— 要修根因；根因超范围先说明再动 |

**流程**：建现状快照 → 界定范围（一句话需求 + 验收判据）→ 写代码 → 注释规范 → 自检验证 → 汇报（只给结论与证据）。

---

<a id="code-review"></a>

### 🔍 2. github-repo-review-and-design —— 仓库审查与设计

**定位**：一个技能两条工作流，共享「定位仓库 + 模式判定」前置。

| 工作流 | 做什么 | 模式 |
|:--|:--|:--|
| **A 整仓审查** | 克隆全量分析，输出分级报告（🔴 阻断 / 🟡 警告 / 💡 建议 / ✅ 亮点，条目带 `文件:行`） | **评估档**（第三方只读）／ **发布档**（自家可整改） |
| **B 文件设计** | 为新项目设计目录树 + 文件职责 + 标准文件要点；杂乱旧仓库给重组方案；可选生成骨架 | 四类基座：开源 demo / 应用服务 / 库 SDK / 内部工具 |

**分层扫描**：L1 入口与启动 → L2 核心逻辑 → L3 配置与接口 → L4 工具脚本 → L5 测试与 CI，每层过六维（正确性 / 安全 / 代码质量 / 测试 / 性能 / 文档与工程化），再做自动化扫描（密钥、内网 IP、个人路径、残留标记、大文件、依赖漏洞）与历史敏感信息扫描。
**只读纪律**：评估档绝不改第三方代码。

---

<a id="reproduction"></a>

### 🧪 3. project-reproduction —— 项目复现

**定位**：把「按教程装一遍」做成**过程可预测、结果可复用**的交付 —— 下一次照着「报告 + 修改后文件」能一次通过。

```text
P0 准备 ─► P1 按原文逐步执行（忠实原文，偏差记为「文档偏差」）
        ─► P2 报错 → 最优路径（环境差异 → 配置 → 代码/文档不符 → 平台特有坑）
        ─► P3 收尾（全量重跑 + diff + 报告 + 归档）
```

**核心纪律**：忠实原文；归因按成本从低到高、一次只试一个分支（同分支重试 ≤ 2 次无进展必须换或上报）；每处修复必须**固化进文件**；验收在**目标用户身份**下完成。

**产出**：`README-FIRST-overview.md`（一句话结论 + 文件地图）、`00_复现报告.md`、`01_执行日志.md`（边做边写）、`02_问题与修复记录.md`、`03_fixed-files/`、`04_baseline-snapshot/`。

**精选坑**：脚本打印「All done」不等于成功（子进程可能根本没启动，要验证副作用）；非交互 shell 里用户 `PATH` 常不生效，会把环境问题误判成项目问题；传二进制用 `adb push` 并双边核对校验和；报磁盘满先 `df` 再判定缺包。

---

<a id="prepublish"></a>

### 🚀 4. prepublish-repo-audit —— 发布前审计

**定位**：**公开不可逆** —— 门禁必须排在 push 之前。

```text
① 可见性判定（匿名 HTTP + cache-buster 复测）
      ─► ② 内容扫描（密钥 / 内部标识 / 内部路径 / 内网 IP / 大文件 / 历史残留）
            ─► ③ 处置（命中内部内容 → 停下问用户；脱敏另稿；改私有并复测）
```

**要点**：仓库里只留环境变量名、不留密钥值；已暴露的凭据必须**轮换**；「删文件再提交」不等于清除历史（要重写历史）；raw 走 CDN 缓存，判定私有必须加 cache-buster；脱敏稿在**副本**上做，发布后**回读线上再扫一次**。

---

<a id="win-shell"></a>

### 🪟 5. windows-shell-tooling —— Windows Shell 工具链

**定位**：Windows 上用 git-bash（MSYS）跑命令、写脚本的实测坑，目标是**同一条命令换台机器也能跑**。

**六条规则**：① 路径转换默认关闭（给原生程序传 `C:/...`，别传 `/c/...`；`cd` 是内建所以能进）；② 不用 PowerShell 语法；③ 含空格/中文路径整体加引号；④ 行尾统一 LF（`.gitattributes`）；⑤ 输出显式设 UTF-8（GBK 控制台会崩）；⑥ 交互输入按「回车」提交（只发 `\n` 不生效）。

**落盘**：heredoc 用 `<<'EOF'`；反斜杠保真不可靠 → 用字节检查（`od -c`）；长文整文件写入；写完回读头字节校验。

---

<a id="script-hardening"></a>

### 🔒 6. shell-script-hardening —— 脚本健壮化

**定位**：`install.sh` / 部署脚本的三条底线 —— **重复执行不坏、失败能说清、成功不自欺**。

**六条纪律**：幂等（先探测再装，已满足打印 `[SKIP]`）；引号与数组；`mktemp` + `trap` 清理；每步打印且错误走 stderr 非零退出；不做危险默认（不 `curl|sh`、`rm -rf` 先判空）；结尾**验证副作用**而不是 echo "All done"。

**自检两条**：脚本自述不可信（重定向到不存在的目录会让子进程根本不启动，却仍打印成功）；非交互 shell 的 `PATH` 陷阱（`~/.bashrc` early-return 导致解释器落到别的版本）。

---

<a id="adb"></a>

### 📱 7. adb-device-toolkit —— 设备联调

**定位**：把「连板子 / Android 设备干活」做成可复现流程。

```text
认设备（devices -l，多设备固定 -s / -t）─► 认清执行身份（root 与普通用户是两套环境）
   ─► 传文件（push/pull + 双边 md5）─► 长任务脱离会话（setsid + 轮询日志）
   ─► 端口方向（forward = 主机→设备，reverse = 设备→主机，部分 adbd 不支持）
```

**常见报错对照**：`unauthorized` / `offline` / `error: closed`（reverse、exec-out 不支持）/ 磁盘满（先 `df`）/ 外设枚举不到（adb 与 USB-host 互斥）。

---

<a id="feishu-api"></a>

### 📄 8. feishu-docs-api —— 云文档 API

**定位**：纯 REST 操作飞书云文档，无 CLI 依赖。

```text
取 token ─► 解析目标（wiki token ≠ doc id）─► 读现状 ─► 写内容 ─► md 上云 ─► 归档节点 ─► 写后核对
```

覆盖：块更新 `PATCH …/blocks/{block_id}` + `update_text_elements`；插块/删块走 children 端点；保留样式的 run 级替换；md → 飞书块发布（每批 ≤ 40 块、单表 ≤ 9 行、列宽按内容算）；wiki 节点创建/移动/改名/按天归档；bitable 字段改造与跨库搬迁；权限与错误码速查（131006 / 1770032 / 99991672 / 99992402 / 1254061）；以及必做的写后回读核对。

---

<a id="doc-audit"></a>

### 📐 9. doc-consistency-audit —— 文档一致性审计

**定位**：先机械层扫描（脚本能查的绝不靠肉眼），再语义层抽查，最后按严重级出报告。

```text
定范围与镜像对 ─► 机械层扫描（结构 / 链接 / 代码块 / 占位残留 / 术语 / 版式）
   ─► 语义层抽查（漏章、数字与配置、镜像指纹、图文对应）
   ─► findings（文档 | 位置 | 类型 | 证据 | 严重级）─► 报告（🔴 / 🟡 / 💡）+ 已修正清单
```

**修复纪律**：确定性（错别字、链接编码、占位行、命令粘连）直接改；改一侧必须同步它的镜像版；语义或需业务判断的进「待确认」不擅改。问题类型用固定枚举（`link-encoding`、`code-glue`、`mirror-mismatch` …）便于统计。

---

<a id="deliverable"></a>

### 🗃️ 10. deliverable-pack —— 交付物包

**定位**：同一件事有**三类读者**（决策者 / 执行者 / 复核者），用固定五件套一次满足。

```text
<产物类型>_<对象>_<YYYYMMDD_HHMM>/
├─ README-FIRST-overview.md   # 必出：1-2 屏，一句话结论 + 怎么用 + 文件地图
├─ 00_main-report.md          # 结构化结论 + 证据（命令 + 输出/位置）
├─ 01_execution-log.md        # 边做边写，禁止事后补
├─ 02_problems-and-fixes.md   # 原文 → 归因 → 修复位置 → 验证
├─ 03_artifacts/              # 最终可用文件，保留原相对路径
└─ 04_baseline-snapshot/      # 改动前原文 / commit，供 diff
```

**纪律**：结论先行；日志与总览分开；每条结论可复核；包内引用用相对路径；目录名带时间戳。

<a id="camera"></a>

### 🎥 11. m2-camera-fps —— M2 摄像头帧率调优

**定位**：M2 + IMX219 的帧率由传感器自己的时序寄存器决定，不是驱动定的 —— 出流期间通过 I2C 写 `VTS` / `EXPO` 把 22.64 fps 提到 **36.42 fps**，不重编内核；`HTS` 必须保持不动（压它会让数字好看、画面坏掉）。

| | 内容 |
|:--|:--|
| ✅ 核心结论 | `fps = pixel_rate / (HTS × VTS)`；`VTS=1096` + `EXPO=640` → **36.42 fps（+60.9%）**；停流后驱动自动恢复出厂值 |
| ⛔ 真实限制 | VTS 只是上限，曝光才决定实际帧率 —— 只改 VTS 会被 AE 锁在 ~25 fps |
| 🧪 测量纪律 | 先预热再计时；帧率用 pad probe 的中位帧间隔，不信容器标称；改完时序必须抽帧看画面 |
| 📦 附带脚本 | `scripts/`：寄存器读写、流中测帧率、`mpph264enc` 录制、平滑变焦 + 框跟随、LSC 标定与校正后 MJPEG 预览 |

**另含**：墙钟 PTS 的硬件 H.264 录制、纯软件平滑变焦（硬件 `VIDIOC_S_CROP` 是开流参数）、「白平衡必须在 LSC 之后」的次序，以及 PC 端 SSH 隧道看流与实测带宽（720p 质量 85 = 30 Mbps）。

---

<a id="quickstart"></a>

## 快速开始（Quick Start）

```bash
# 一、克隆后把需要的技能目录复制进你所用 Agent 的技能目录
git clone git@github.com:jjking619/QPi-Skills.git
cp -r QPi-Skills/skills/*  <你的技能目录>/

# 二、客户端支持从 GitHub 安装时
npx skills add jjking619/QPi-Skills

# 三、示例：Hermes Agent（tap 方式）
hermes skills tap add jjking619/QPi-Skills
hermes skills install jjking619/QPi-Skills/project-reproduction
```

- **无需构建**：技能主体是纯 Markdown（其中一个另带可直接运行的 Python `scripts/`），命令按需在运行时执行。
- **如何被加载**：Agent 依据每个 `SKILL.md` frontmatter 的 `description`（含触发词）判断是否加载；显式加载方式随客户端而异，见所使客户端的文档。
- **改回自己的环境**：技能里出现的产出目录（复现报告、审计报告等落盘路径）按自己习惯改 `SKILL.md` 里的路径常量即可。

<a id="layout"></a>

## 仓库结构（Repository Layout）

```text
QPi-Skills/
├── README.md                                   # 英文门面（Agent 与 GitHub 首屏）
├── README.zh.md                                # 本文件：中文版
├── LICENSE                                     # MIT
├── .gitignore
├── .gitattributes
└── skills/                                     # 每个技能一个目录；目录名 = SKILL.md 的 name
    ├── code-authoring/                         #   SKILL.md（英文）+ SKILL.zh.md（中文）
    ├── github-repo-review-and-design/
    ├── project-reproduction/
    ├── prepublish-repo-audit/
    ├── windows-shell-tooling/
    ├── shell-script-hardening/
    ├── adb-device-toolkit/
    ├── feishu-docs-api/
    ├── doc-consistency-audit/
    ├── deliverable-pack/
    └── m2-camera-fps/                # SKILL.md + SKILL.zh.md + scripts/（代码即交付物）
```

目录层级符合 Agent Skills 的 tap 约定（`skills/<技能名>/SKILL.md`），可**整树复制**，无需改名或调整结构。

<a id="conventions"></a>

## 设计约定（Conventions）

- **一个技能一个 `SKILL.md`**：流程、坑位、验收清单写在一起，技能不会因为缺文件而失效。仅当代码本身就是交付物时允许另带 `scripts/`（目前只有 `m2-camera-fps`），且 `SKILL.md` 即使没有脚本也要能独立读得通。
- **触发词面向意图**：描述用中性意图表述，换个人、换个项目依然能命中。
- **结论必须可复核**：审查条目带 `文件:行`，复现步骤带命令与实际输出，API 断言带端点与错误码。
- **修复要固化**：临时命令不算交付，改动必须落进文件本身。
- **坑位只收通用经验**：条目须在他人环境下也成立；环境/团队特有条目不进技能。
- **凭据不进仓库**：密钥、token、内部标识走环境变量，仓库里只留占位符。
- **版本语义化**：每个技能自带 `version`（与上表一致），技能行为变更时同步升版。

<a id="license"></a>

## 许可（License）

本项目采用 [MIT License](LICENSE)。

