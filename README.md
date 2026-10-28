<div align="center">

# QPi-Skills

**A skill pack for everyday engineering workflows**

Code authoring · repo review · project reproduction · publish gate · shell & script hardening · device debugging · cloud docs API · document audit · deliverable packs · M2 camera tuning

[![Skills](https://img.shields.io/badge/skills-11-2f81f7?style=flat-square)](#skills)
[![Format](https://img.shields.io/badge/skills-plain%20markdown-8b5cf6?style=flat-square)](#skills)
[![Standard](https://img.shields.io/badge/Agent%20Skills-open%20format-0ea5e9?style=flat-square)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-MIT-16a34a?style=flat-square)](#license)

</div>

> Repetitive work that still needs judgement, distilled into skills an AI agent can load and execute.
> Every skill is **a self-contained `SKILL.md`**: trigger conditions, an executable procedure, verified gotchas, and an acceptance checklist. Where the code itself is the deliverable, the skill carries a `scripts/` folder beside it; otherwise it is one file. No hidden assets, no build step — copy the folder into your agent's skill directory and it works.

---

<a id="toc"></a>

## Table of Contents

| | Section |
|---|---|
| 📦 | [Skills Overview](#skills) |
| 🔗 | [The Build Chain](#build-chain) |
| ✍️ | [code-authoring](#authoring) |
| 🔍 | [github-repo-review-and-design](#code-review) |
| 🧪 | [project-reproduction](#reproduction) |
| 🚀 | [prepublish-repo-audit](#prepublish) |
| 🪟 | [windows-shell-tooling](#win-shell) |
| 🔒 | [shell-script-hardening](#script-hardening) |
| 📱 | [adb-device-toolkit](#adb) |
| 📄 | [feishu-docs-api](#feishu-api) |
| 📐 | [doc-consistency-audit](#doc-audit) |
| 🗃️ | [deliverable-pack](#deliverable) |
| 🎥 | [m2-camera-fps](#camera) |
| ⚡ | [Quick Start](#quickstart) |
| 🗂️ | [Repository Layout](#layout) |
| 📐 | [Conventions](#conventions) |
| 📜 | [License](#license) |

---

<a id="skills"></a>

## Skills Overview

| Skill | Package / version | What it solves | Typical trigger |
|:--|:--|:--|:--|
| ✍️ **Code authoring** | `code-authoring`<br>`v0.1.0` | Comment hygiene (write *why*) plus **minimal sufficient diff** discipline, so a small change stays small | before writing new code or editing code you didn't just create |
| 🔍 **Repo review & design** | `github-repo-review-and-design`<br>`v0.1.0` | **Whole-repo graded review** (assessment / release modes) and **file-structure design** for new projects | "is this repo worth using?", "design the layout for this demo" |
| 🧪 **Project reproduction** | `project-reproduction`<br>`v0.1.0` | Follow the README / tutorial / `install.sh` step by step, fix errors cheapest-path-first, make fixes permanent, deliver a report | "reproduce / deploy / get this project running" |
| 🚀 **Pre-publish audit** | `prepublish-repo-audit`<br>`v0.1.0` | The **gate** before open-sourcing: visibility, secrets, internal identifiers, hygiene, history residue | "can this repo go public?", "audit before publishing" |
| 🪟 **Windows shell** | `windows-shell-tooling`<br>`v0.1.0` | Windows + git-bash traps: path conversion, CRLF/LF, escaping, GBK console, pty line endings | a command misbehaves under git-bash |
| 🔒 **Script hardening** | `shell-script-hardening`<br>`v0.1.0` | `install.sh` / deploy scripts that are **idempotent, diagnosable, and never falsely succeed** | writing or reviewing a one-click installer |
| 📱 **Device debugging** | `adb-device-toolkit`<br>`v0.1.0` | **adb** workflows: identify devices, execution identity, transfer with checksums, detached long tasks | debugging a board or Android device |
| 📄 **Cloud docs API** | `feishu-docs-api`<br>`v0.1.0` | Drive Feishu/Lark docs over REST: block editing, markdown publishing, wiki archiving, permissions | "edit this Feishu doc", "sync this markdown up" |
| 📐 **Document audit** | `doc-consistency-audit`<br>`v0.1.0` | Consistency audit for a doc set or multilingual tree, with a severity-graded report | "audit this batch of documents" |
| 🗃️ **Deliverable pack** | `deliverable-pack`<br>`v0.1.0` | Turn one-off work into a five-part reviewable pack | any work that must be handed over |
| 🎥 **M2 camera tuning** | `m2-camera-fps`<br>`v0.1.0` | Register-level frame-rate gain on Quectel Pi M2 + IMX219 (22.64 → 36.42 fps, no kernel rebuild), plus honest fps measurement, hardware recording, smooth zoom, LSC and SSH-tunneled preview | "camera frame rate is too low", "measure the real fps", "M2 camera I2C / GStreamer fails" |

---

<a id="build-chain"></a>

## The Build Chain

```text
write → review → reproduce → publish → hand over
code-authoring → github-repo-review-and-design → project-reproduction → prepublish-repo-audit → deliverable-pack
```

Peripheral but load-bearing: `windows-shell-tooling` and `shell-script-hardening` (environment and scripts), `adb-device-toolkit` (devices), `m2-camera-fps` (camera hardware), `feishu-docs-api` and `doc-consistency-audit` (documents).

---

<a id="details"></a>

## Skill Details

<a id="authoring"></a>

### ✍️ 1. code-authoring

**Focus**: two things only, at the moment code is produced — **what comments say** and **how big the change is**.

**Six rules**: self-contained and scoped to the authoring phase; trigger surface covers any production-code write or edit; comments follow the file's language (English for new files) and explain **why**; minimal sufficient diff; build a current-state snapshot before editing existing code; self-check scope, comments, and whether you actually ran it before delivering.

| | Content |
|:--|:--|
| ✅ Whitelist (required) | input validation, error handling, resource release, updating call sites, required tests, formatter-forced changes |
| ⛔ Blacklist (no "while you're there") | reformatting, renaming, import reordering, unrequested logging/flags/abstractions, new dependencies, public-signature changes, broad reshuffles |
| 🚫 Bottom line | never special-case, hardcode, comment out assertions, or bypass validation to make tests pass — fix the root cause; if it's out of scope, say so first |

**Procedure**: current-state snapshot → bound the change (one-sentence requirement + acceptance criterion) → write code → comment hygiene → verify (baseline + diff review) → report conclusions and evidence only.

---

<a id="code-review"></a>

### 🔍 2. github-repo-review-and-design

**Focus**: one skill, two workflows sharing the same "locate the repo + decide the mode" preamble.

| Workflow | What it does | Modes |
|:--|:--|:--|
| **A Whole-repo review** | clone, analyse in full, emit a graded report (🔴 blocking / 🟡 warning / 💡 suggestion / ✅ highlights, each with `file:line`) | **assessment** (third-party, read-only advice) · **release** (your repo, fix to publishable) |
| **B File design** | directory tree + file responsibilities + standard-file contents for a new project; reorganisation plan for a legacy repo; optional scaffolding | four bases: open-source demo / application / library / internal tool |

**Layered scan**: L1 entry & startup → L2 core logic → L3 config/interfaces/device access → L4 tooling scripts → L5 tests & CI, each run through six dimensions (correctness · security · code quality · tests · performance · docs & engineering), followed by automated scans (secrets, private IPs, personal path traces, leftover markers, oversized files, dependency audits) and — in release mode — a history scan.
**Read-only discipline**: assessment mode never edits third-party code.

---

<a id="reproduction"></a>

### 🧪 3. project-reproduction

**Focus**: turn "install it by the tutorial" into a predictable process with a reusable result — the next person succeeds in one pass from "report + modified files".

```text
P0 prepare ─► P1 execute the documented steps faithfully (deviations logged, not silently fixed)
         ─► P2 errors → cheapest path (environment → configuration → code/docs mismatch → platform traps)
         ─► P3 wrap up (full re-run + diff + report + archive)
```

**Core discipline**: stay faithful to the document first; root-cause order from cheapest to most expensive, one branch at a time (≤ 2 attempts before switching); every fix must be made **permanent in a file**; accept the result as the target user identity, not as an elevated shell.

**Output**: `README-FIRST-overview.md` (one-sentence conclusion + file map), `00_reproduction-report.md`, `01_execution-log.md` (appended live), `02_problems-and-fixes.md`, `03_fixed-files/`, `04_baseline-snapshot/`.

**Pitfalls worth remembering**: a script printing "All done" is not success (a child process may never have started — verify side effects); a non-interactive shell often skips the user's `PATH`, turning environment problems into apparent project bugs; transfer binaries with `adb push` and compare checksums; run `df` before declaring a dependency "missing" on a small root filesystem.

---

<a id="prepublish"></a>

### 🚀 4. prepublish-repo-audit

**Focus**: **publishing is irreversible** — the gate runs before the push.

```text
① visibility check (anonymous HTTP, re-tested with a cache-buster)
     ─► ② content scan (secrets / internal identifiers / internal paths / private IPs / large files / history residue)
           ─► ③ disposition (internal content found → stop and ask; sanitize a copy; make private and re-test)
```

**Key points**: the repo holds environment-variable *names*, never secret values; an already-exposed credential must be **rotated**; deleting a file in a new commit does not remove it from history; raw content is CDN-cached, so a cache-buster is required to confirm "now private"; sanitize on a copy and **re-scan the published content**.

---

<a id="win-shell"></a>

### 🪟 5. windows-shell-tooling

**Focus**: git-bash (MSYS) on Windows, with the goal that the same command works on someone else's machine.

**Six rules**: ① path conversion is off by default (`C:/...` for native tools; `cd` is a builtin so `/c/...` works for it alone); ② no PowerShell syntax; ③ quote paths with spaces or non-ASCII; ④ LF everywhere (`.gitattributes`); ⑤ set UTF-8 explicitly (GBK consoles break non-ASCII output); ⑥ submit interactive input with a real Enter — a bare `\n` often does nothing.

**File writes**: quoted heredocs; backslash fidelity is not guaranteed, so test with byte checks (`od -c`); write long documents wholesale; read back the first bytes after writing.

---

<a id="script-hardening"></a>

### 🔒 6. shell-script-hardening

**Focus**: three bottom lines — **re-running never breaks anything, failures explain themselves, success never lies**.

**Six disciplines**: idempotency (probe, then print `[SKIP]`); quoting and arrays; `mktemp` + `trap` cleanup; per-step logging with stderr and non-zero exits; no dangerous defaults (no `curl | sh`, guard `rm -rf`); verify **side effects** at the end instead of echoing success.

**Two self-checks**: a script's own narration is not evidence (redirecting into a missing directory means the child never starts); non-interactive shells skip `~/.bashrc`, so interpreters resolve to the wrong version.

---

<a id="adb"></a>

### 📱 7. adb-device-toolkit

**Focus**: connect to a board or Android device and get work done repeatably.

```text
identify (devices -l, pin -s / -t) ─► establish identity (root vs regular user are two environments)
   ─► transfer (push/pull + md5 both sides) ─► long tasks (setsid + poll the log)
   ─► port direction (forward = host→device, reverse = device→host, not supported by every adbd)
```

**Troubleshooting table**: `unauthorized` / `offline` / `error: closed` (reverse or exec-out unsupported) / disk full (run `df` first) / peripherals not enumerated (USB-host and adb can be mutually exclusive).

---

<a id="feishu-api"></a>

### 📄 8. feishu-docs-api

**Focus**: REST-only Feishu document operations, no CLI required.

```text
token ─► resolve target (wiki token ≠ doc id) ─► read state ─► write ─► publish markdown ─► archive nodes ─► verify
```

Covers: block updates via `PATCH …/blocks/{block_id}` + `update_text_elements`; queue-style insert/delete via the children endpoint; style-preserving run-level replacement; markdown → Feishu block publishing (≤ 40 blocks per call, ≤ 9 rows per table, computed column widths); wiki node creation, moves, renames and per-day archive folders; bitable field work and cross-base migration; a permission and error-code table (131006 / 1770032 / 99991672 / 99992402 / 1254061); and mandatory post-write verification by re-reading block and table counts.

---

<a id="doc-audit"></a>

### 📐 9. doc-consistency-audit

**Focus**: mechanical scans first, semantic sampling second, then a severity-graded report with locatable evidence.

```text
define scope + mirror pairs ─► mechanical scan (structure / links / code blocks / placeholders / terminology / layout)
   ─► semantic sampling (missing sections, numbers vs config, mirror fingerprints, figure-text agreement)
   ─► findings (file | location | type | evidence | severity) ─► report (🔴 / 🟡 / 💡) + fixed list
```

**Fix discipline**: unambiguous problems (typos, link encoding, placeholders, glued commands) are fixed directly; whatever changes on one side of a mirror pair gets mirrored; semantic or judgement calls stay listed as "needs confirmation". Findings use a fixed type enum (`link-encoding`, `code-glue`, `mirror-mismatch`, …) so tallies stay countable.

---

<a id="deliverable"></a>

### 🗃️ 10. deliverable-pack

**Focus**: the same work has three readers — decision-maker, operator, auditor — served by a fixed five-part pack.

```text
<artifact-type>_<subject>_<YYYYMMDD_HHMM>/
├─ README-FIRST-overview.md   # required: 1-2 screens, one-sentence conclusion + file map
├─ 00_main-report.md          # structured conclusions + evidence (command + output/location)
├─ 01_execution-log.md        # appended as you go, never reconstructed
├─ 02_problems-and-fixes.md   # raw error → root cause → fix location → verification
├─ 03_artifacts/              # final usable files, original relative paths kept
└─ 04_baseline-snapshot/      # pre-change files / commit, so the diff has a base
```

**Discipline**: conclusions first; keep the log separate from the overview; every conclusion verifiable; relative paths inside the pack; timestamped directories.

<a id="camera"></a>

### 🎥 11. m2-camera-fps

**Focus**: on an M2 + IMX219 the frame rate is decided by the sensor's own timing registers, not by the driver — writing `VTS` / `EXPO` over I2C **while the stream is running** takes 22.64 → 36.42 fps with no kernel rebuild. `HTS` stays untouched: squeezing it makes the numbers look better and the picture worse.

| | Content |
|:--|:--|
| ✅ Core result | `fps = pixel_rate / (HTS × VTS)`; `VTS=1096` + `EXPO=640` → **36.42 fps (+60.9 %)**; stopping the stream restores factory values |
| ⛔ Real limit | VTS only sets the ceiling — exposure decides the actual rate, and AE pins a VTS-only change at ~25 fps |
| 🧪 Measurement discipline | warm up before timing; median inter-frame interval from a pad probe, never the container's nominal rate; pull a frame after every timing change |
| 📦 Ships with | `scripts/`: register read/write, mid-stream fps probe, `mpph264enc` recording, smooth zoom + box follow, LSC calibration and corrected MJPEG preview |

**Also covers**: hardware H.264 recording with wall-clock PTS, software-only smooth zoom (hardware `VIDIOC_S_CROP` is a stream-start parameter), the LSC-before-white-balance ordering, and MJPEG preview over a PC-side SSH tunnel with measured bandwidth (720p q85 = 30 Mbps).

---

<a id="quickstart"></a>

## Quick Start

```bash
# 1. Clone, then copy the skill folders you need into your agent's skill directory
git clone git@github.com:jjking619/QPi-Skills.git
cp -r QPi-Skills/skills/*  <your-agent-skills-dir>/

# 2. Install from the GitHub repo, if your client supports it
npx skills add jjking619/QPi-Skills

# 3. Example: Hermes Agent (tap)
hermes skills tap add jjking619/QPi-Skills
hermes skills install jjking619/QPi-Skills/project-reproduction
```

- **No build step**: each skill is a plain markdown file — one of them adds a `scripts/` folder of ready-to-run Python; commands run at the moment they're needed.
- **How skills load**: your agent reads the `description` in each `SKILL.md` frontmatter (trigger keywords) to decide relevance; how to load one explicitly differs per client — see its docs.
- **Adapt to your environment**: output directories mentioned in a skill (report or audit paths) are plain text — edit the constant in `SKILL.md` to match your habits.

<a id="layout"></a>

## Repository Layout

```text
QPi-Skills/
├── README.md                                   # this file: facade and usage
├── README.zh.md                                # Chinese edition of this file
├── LICENSE                                     # MIT
├── .gitignore
├── .gitattributes
└── skills/                                     # one directory per skill; the directory name equals the SKILL.md `name`
    ├── code-authoring/                         # SKILL.md (English) + SKILL.zh.md (Chinese)
    ├── github-repo-review-and-design/
    ├── project-reproduction/
    ├── prepublish-repo-audit/
    ├── windows-shell-tooling/
    ├── shell-script-hardening/
    ├── adb-device-toolkit/
    ├── feishu-docs-api/
    ├── doc-consistency-audit/
    ├── deliverable-pack/
    └── m2-camera-fps/                # SKILL.md + SKILL.zh.md + scripts/ (the code is the deliverable)
```

The layout follows the Agent Skills tap convention (`skills/<skill-name>/SKILL.md`), so the tree can be copied wholesale without renaming anything.

<a id="conventions"></a>

## Conventions

- **One `SKILL.md` per skill**: the procedure, the gotchas, and the acceptance checklist live together, so a skill never breaks on a missing companion file. A `scripts/` folder is allowed only where the code itself is the deliverable (`m2-camera-fps` today), and the `SKILL.md` still stands on its own without it.
- **Intent-shaped triggers**: descriptions use neutral intent ("reproduce per the tutorial"), not one conversation's phrasing.
- **Verifiable conclusions**: review findings carry `file:line`, reproduction steps carry commands and real output, API claims carry endpoints and error codes.
- **Fixes are permanent**: a one-off command is not a delivery — the change belongs in a file.
- **Generic gotchas only**: an entry must hold in someone else's environment; environment- or team-specific items stay out.
- **No credentials in the repo**: keys, tokens, and internal identifiers come from the environment; the repository holds placeholders.
- **Semantic versions**: every skill carries a `version` in its frontmatter, mirrored in the table above — bump it when a skill's behavior changes.

<a id="license"></a>

## License

Released under the [MIT License](LICENSE).

