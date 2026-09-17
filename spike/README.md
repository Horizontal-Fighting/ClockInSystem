# Spike 工具包 · 快速上手

配合 [`../docs/06-评测精度Spike执行方案.md`](../docs/06-评测精度Spike执行方案.md) 使用。
**详细方法论（样本怎么选、老师怎么评、结论怎么下）请看那份文档，这里只讲命令。**

---

## 在哪里跑

**就在你自己的 Windows 电脑上跑，不用等服务器。** 脚本只是把录音文件发给腾讯云打分，
不需要小程序、不需要后端、不需要云主机。

- 目录：`D:\WorkBuddy\ClockIn‌System\spike`
- 终端：**Git Bash**（下面命令都是 bash 语法，PowerShell 不通用）

---

## 0. 环境准备（一次性）

### 0.1 Python 解释器

用已配好的隔离环境，**不要用系统 Python 3.8**（太老）。每次用这个完整路径：

```bash
PY="C:/Users/Horiz/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" --version        # 应显示 Python 3.13.x
```

嫌路径长就起个别名，之后都用 `py`：

```bash
alias py="C:/Users/Horiz/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
```

### 0.2 装依赖

```bash
"$PY" -m pip install -r requirements.txt
```

> 已在本机装好（tencentcloud-sdk-python-soe 3.0.1459）。换机器时重跑一次即可。

### 0.3 转码能力（已就绪，无需单独装 ffmpeg）

> ⚠️ 不要用 `winget install Gyan.FFmpeg` —— 它从 GitHub 下载，国内直连极慢（真实经历：一晚卡在 113MB）。
> 已改用 **imageio-ffmpeg**（pip 包，wheel 里自带 ffmpeg.exe，走 PyPI 下载，24 秒装完）。

已在本机装好（ffmpeg 7.1）。转码**不用再敲 ffmpeg 命令**，直接用一键脚本：

```bash
"$PY" transcode.py
```

它会：批量转码 → 自动验证 16k/16bit/单声道 → 对照 samples.csv 报告哪几条还没录。
原始音频自动备份到 `raw_audio/`。

### 0.4 配置凭据 ★ 三件套，缺一不可

**本项目用的是「口语评测（新版）」**（产品 1774，WebSocket），它比基础版多要一个 **AppID**。

| 变量 | 在哪找 |
|---|---|
| `TENCENTCLOUD_APPID` | 腾讯云控制台 → 右上角头像 → **账号信息** → APPID（纯数字，如 1306xxxxxx） |
| `TENCENTCLOUD_SECRET_ID` | 控制台 → 访问管理（CAM）→ API 密钥 |
| `TENCENTCLOUD_SECRET_KEY` | 同上，与 SecretId 成对 |

> ⚠️ **AppID 和 SecretId 是两个不同的东西**，新版 SOE 用它拼 WebSocket 路径，漏了直接连不上。

两种方式，**任选其一**，脚本都能读到（优先级：环境变量 > `.env`）。

#### 方式 A：`.env` 文件（推荐，本机已配好）

在 `spike` 目录放一个 `.env`，内容照抄 `.env.example`：

```ini
TENCENTCLOUD_APPID=1306xxxxxx
TENCENTCLOUD_SECRET_ID=AKIDxxxx
TENCENTCLOUD_SECRET_KEY=xxxx
```

> **本机已配好，不用再动。** 该文件已被根目录 `.gitignore` 忽略，不会进版本库。
> 换机器时自己建一个即可。

#### 方式 B：Windows 用户级环境变量

用 PowerShell 执行：

```powershell
[Environment]::SetEnvironmentVariable("TENCENTCLOUD_APPID",       "xxx", "User")
[Environment]::SetEnvironmentVariable("TENCENTCLOUD_SECRET_ID",   "xxx", "User")
[Environment]::SetEnvironmentVariable("TENCENTCLOUD_SECRET_KEY",  "xxx", "User")
```

⚠️ **设完必须把终端窗口整个关掉重开**才生效。原因是环境变量在**进程启动时**就固定了，
已经开着的窗口读不到新值——这是最常见的问题，不是密钥设错了。

验证：

```bash
echo "[${TENCENTCLOUD_APPID}]"    # 应输出你的 AppID，不是空方括号
```

> 密钥用**子账号**的，只授权 SOE + COS，**不要用主账号**。

---

### 凭据与服务自检

跑通后再录音也不迟。用合成音频打一次真实调用（不依赖任何录音文件）：

```bash
"$PY" run_eval.py --check
```

看到 `✔ 新版调用成功` 就表示：**凭据有效 + 口语评测（新版）已开通**，可以开始录音了。

失败时按错误码对症处理：

| code | 含义 | 怎么办 |
|---|---|---|
| `4003` | AppID 未开通新版口语评测 | 去 `console.cloud.tencent.com/soenew` 开通（注意不是 `/soe`，那是基础版） |
| `4002` | 鉴权失败 | 检查 SecretId / SecretKey 是否成对、有无多余空格或只复制了一半 |
| `4004` | 资源包耗尽 | 控制台查看剩余次数，或改按量付费 |
| `4005` | 账号欠费 | 结算中心处理 |

> ⚠️ **最大的坑：买错版本。**
> 「口语评测（基础版）」(884) 与「口语评测（新版）」(1774) 是**两个独立产品**，
> 控制台不同、SDK 不同、**资源包也不通用**。买了新版包却调基础版接口，会一直报
> `AuthFailure.AccountUnavailable`（"账号未开通服务"）——极易误判成服务没开，实际是版本错配。
>
> 另一个易混点：**智聆口语评测 SOE**（给发音打分，我们要的）
> ≠ **语音识别 ASR**（语音转文字，不是这个）。买了 ASR 的包不代表 SOE 已开通。

---

## 5 步跑完

### 1. 转码（★ 最容易踩的坑）

腾讯云要求 **16k 采样率 / 16bit / 单声道**。手机录音通常是 44.1k 或 48k 立体声，
**不转码接口不报错，但分数会不准** —— 这个错误极其隐蔽。

录音文件按编号命名（`A01.m4a`…`D06.m4a`）放进本目录，然后一条命令：

```bash
"$PY" transcode.py
```

脚本自动完成：转码 → 逐条验证 `16000Hz / mono / 16bit`（不合格直接报错）→
对照 `samples.csv` 列出还缺哪几条。原始文件移入 `raw_audio/` 备份。

### 2. 填样本清单

编辑 `samples.csv`（列名与填写规范写在文件头部的注释里）。

### 3. 跑 AI 评测

密钥已在 0.4 设好，直接跑：

```bash
"$PY" run_eval.py --check       # ★ 自检（无需录音文件）
"$PY" run_eval.py --limit 1     # ★ 有录音后先跑 1 条，确认端到端通
"$PY" run_eval.py               # 全量
"$PY" run_eval.py --dry-run     # 只看参数不花钱
```

> `--check` 和 `--limit 1` 这两步**别跳过**。接口不通（AppID 漏填、服务没开通、音频格式不对）时，
> 早发现比批量跑完才发现好——批量失败一次要白扔资源包次数。

音频路径不用管：脚本会自动兼容 `samples.csv` 里 `A01.wav` 和 `wav16k/A01.wav` 两种写法。

产出 `results.csv`（结构化分数）+ `raw/*.json`（引擎原始返回，务必保留）。

默认对每条样本跑 3 组 `ScoreCoeff`（1.0 / 1.5 / 2.5），30 条样本 = 90 次调用，约 10 分钟，花费不到 1 元。

### 4. 生成人工打分表

```bash
"$PY" make_rating_sheet.py --teacher A   # → rating_A.csv
"$PY" make_rating_sheet.py --teacher B   # → rating_B.csv
```

两位老师拿到的是**不同的随机顺序**，表里不含任何 AI 分数。
老师只需填 3 列：`total_score`（0-100）、`star`（1/2/3）、`weak_phonemes`（音素，无错误填「无」）。

> ⚠️ 音素请用**智聆写法**：`th` `ae` `sh` `ng` `dh`。
> 国际音标的 `æ` 要写成 `ae`，否则匹配不上，命中率会假性为 0。

### 5. 分析

```bash
"$PY" analyze.py
```

输出人类基线、AI 相关性、MAE、Bland-Altman、分层表现、权重拟合、星级一致率、
音素命中率、坏样本报告，并自动给出 Go / No-Go 判定。同时写入 `report.txt`。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| **`录音执行单.md`** | ★ **录音时看这份**：按学生分组、照着念即可，含转码命令与两条纪律 |
| `samples.csv` | 样本清单，已预置 36 条可用内容（一般不用改） |
| `transcode.py` | 一键转码 + 自动验证 16k/mono/16bit + 缺条目对照 |
| `录音执行单.md` | ★ 录音时看这份：按学生分组、照着念即可 |
| `.env` / `.env.example` | 密钥（`.env` 已被 gitignore，不要外传） |
| `soe_new.py` | 新版 SOE（WebSocket）封装，`run_eval.py` 的下层依赖，一般不用直接跑 |
| `_soesdk/` | 官方新版 SDK 源码（PyPI 无包，GitHub 拉取后本地引用，已 gitignore） |
| `run_eval.py` | 批量调 SOE，产出 `results.csv` + `raw/`；支持 `--check` / `--dry-run` / `--limit` |
| `make_rating_sheet.py` | 生成盲评表 `rating_A.csv` / `rating_B.csv` |
| `analyze.py` | 对齐分析，产出 `report.txt` |
| `results.csv` `rating_*.csv` `raw/` `report.txt` | 运行后产生 |

## 常用参数

```bash
# 只试某一组苛刻指数（省时间/省钱）
"$PY" run_eval.py --coeff 1.5

# 自定义星级阈值
"$PY" analyze.py --star3 85 --star2 70

# 音频不在当前目录
"$PY" run_eval.py --audio-dir ../audio
```

## 容易出错的三件事

1. **没转码** → 分数整体偏低或忽高忽低，且接口不报错。`transcode.py` 会自动验证，看到 `✓` 才算过。
2. **老师看了 AI 分再打** → 被锚定，人类基线虚高，整个 Spike 结论作废。严格盲评。
3. **只找一位老师** → 算不出人类基线，MAE 这个数字失去参照意义。至少 2 位。
