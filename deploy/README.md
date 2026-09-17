# 服务器初始化说明

配套脚本：`init-server.sh`（Ubuntu 24.04 LTS 一键初始化）
适用范围：拼拼英语打卡项目，2C4G 单机部署（应用 + MySQL + Redis + Nginx 同机）

---

## 一、采购规格（可直接抄进采购申请）

| 项目 | 规格 | 备注 |
|---|---|---|
| 类型 | 云服务器 CVM / 轻量应用服务器 | 两者皆可，轻量更便宜 |
| **地域** | **华南-广州** | ★ 必须。与 COS 存储桶、语音评测 SOE 同地域，走内网不占公网流量 |
| **操作系统** | **Ubuntu Server 24.04 LTS 64位** | ★ 不要用 CentOS / TencentOS / Windows |
| **CPU 架构** | **x86_64（Intel/AMD）** | ★ 不要选 ARM / 倚天。ARM 上部分 npm 原生模块需重新编译 |
| CPU | 2 核 | 本项目峰值 QPS < 1，充足 |
| 内存 | 4 GB | 同机跑 MySQL + Redis + Node 应用，脚本会配 4G swap 兜底 |
| 系统盘 | 70 GB SSD | 只放应用、数据库、日志；**音频全部存 COS**，本地盘压力很小 |
| 带宽 | 6 Mbps | 前提是音频走 COS 直传直下（已在架构约束中写死） |
| 月流量 | 600 GB | 音频走 COS 时实际仅约 2GB/月，余量极大 |
| 公网 IP | 固定 1 个 | 备案与域名解析需要 |
| 安全组 | 初期只开 22，后续按脚本要求开 80/443 | 控制台单独配，脚本内的 ufw 是第二层 |

**采购后建议一并确认的三件事**

1. **域名 + ICP 备案**（1-20 个工作日，纯等待）——下单当天就该提交，这是关键路径
2. **微信小程序教育类目资质**——与服务器无关，但同为上线阻塞项，并行推进
3. **COS 存储桶**：需建两个桶（录音私有桶 / 内容公开桶），地域同样选广州

> 规格依据见 `docs/02-技术架构与数据设计.md` 第 8.2 节（含带宽与内存的完整测算）。

---

## 二、执行前准备

### 1. 准备 SSH 密钥（在自己电脑上执行）

```bash
# 没有密钥就生成一个（一路回车即可）
ssh-keygen -t ed25519 -C "yourname@pinpin"

# 查看公钥，复制备用
cat ~/.ssh/id_ed25519.pub
```

Windows 用户可用 PowerShell：

```powershell
ssh-keygen -t ed25519
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

### 2. 拿到 root 登录方式

腾讯云购买的机器，首次登录通常是 `ubuntu` 用户 + 密钥，或控制台设置的 root 密码。
脚本需要 root 权限：

```bash
sudo -i          # 若用 ubuntu 用户登录，先切 root
```

---

## 三、执行初始化

### 方式 A：交互式（推荐首次使用）

```bash
# 上传脚本到服务器后执行
bash init-server.sh
```

脚本会依次询问：SSH 端口（默认 22）、SSH 公钥（若 root 已有密钥会自动复用）、确认执行。

### 方式 B：非交互（重跑 / 自动化）

```bash
sudo SSH_PORT=22 SSH_PUBKEY="ssh-ed25519 AAAAC3Nza... yourname" bash init-server.sh -y
```

### 方式 C：只体检不修改

机器到手后先跑一遍看现状，或日后排查用：

```bash
sudo bash init-server.sh --check
```

输出系统版本、架构、内存、swap、磁盘、Docker、防火墙、目录等状态。

### 关于换行符

如果在 Windows 上下载/编辑过脚本，上传后先转格式再执行，否则会报 `bad interpreter`：

```bash
sed -i 's/\r$//' init-server.sh
```

---

## 四、脚本做了什么（9 步）

| 步骤 | 内容 | 关键点 |
|---|---|---|
| 0 | 前置检查 + 参数收集 | 校验 Ubuntu 24.04 / x86_64 / SSH 公钥格式，不符合会拦下 |
| 1 | 系统更新 + 基础软件 | curl、gnupg、git、jq、ufw、fail2ban；时区设为 Asia/Shanghai |
| 2 | 创建 deploy 用户 | sudo + docker 组，NOPASSWD 便于自动部署，**无密码仅密钥** |
| 3 | **防火墙 ufw** | 只放行 SSH / 80 / 443，默认拒绝入站 |
| 4 | **SSH 加固** | 禁 root、禁密码、仅密钥、AllowUsers deploy |
| 5 | Docker CE + Compose | 官方源安装（非系统自带旧版），**日志限制 10m × 3 份** |
| 6 | **swap 4G** | swappiness=10，防止 4G 内存峰值 OOM |
| 7 | 目录约定 | `/srv/app` `/srv/data/{mysql,redis,nginx}` `/srv/backup` |
| 8 | fail2ban | SSH 5 次失败封 1 小时 |
| 9 | 验收自检 | 打印完整初始化报告 + 下一步指引 |

### 三个容易被忽略、但脚本特意处理了的坑

**1. ufw 必须在 SSH 重启之前配好**
顺序反了会把自己锁在服务器外面。脚本严格按「先放行新端口 → 再改 SSH 配置」执行。

**2. Ubuntu 22.10+ 改 SSH 端口必须同时改 `ssh.socket`**
新版本用 socket activation，只改 `sshd_config` 里的 `Port` **不生效**。脚本自动写
`/etc/systemd/system/ssh.socket.d/override.conf`。这是手动配最常见的翻车点。

**3. Docker 日志默认无上限**
json-file 驱动不限制大小，几个月就能吃满 70GB 系统盘。脚本写入 `daemon.json` 限制为
单文件 10MB、保留 3 份。

---

## 五、执行后必做（★ 顺序不能乱）

```bash
# 1. 千万不要关掉当前终端！另开一个窗口验证新配置能登录
ssh -p <端口> deploy@<服务器IP>

# 2. 登录成功后，验证 docker 组权限生效
docker ps                 # 不应出现 permission denied
docker compose version

# 3. 腾讯云控制台 → 安全组，放行 端口 / 80 / 443（与 ufw 一致，双层防护）

# 4. 若脚本更新过内核，重启一次
sudo reboot
```

> **如果第 1 步登录失败**，立刻用原终端（还没断）检查
> `/home/deploy/.ssh/authorized_keys` 是否写入成功。原终端不断开就是你的后悔药。

---

## 六、明确禁止的事

| 禁止 | 原因 |
|---|---|
| **装宝塔面板** | 自身吃 300-500MB 内存（4G 机器上占比过高），且开放额外端口增加攻击面 |
| **在生产机跑前端构建** | `npm build` 吃 2G+ 内存，会直接 OOM 拖垮服务。必须本地/CI 构建好再上传 |
| **数据库备份落本地盘** | 每日全量后期 5GB/次 × 保留 7 天 = 35GB，会把 70GB 撑满导致 MySQL 崩溃。备份直接传 COS |
| **音频经服务器中转** | 6M 带宽下 40 人同时播放就打满。必须 COS 直传直下 |

---

## 七、监控告警最低配置

在腾讯云控制台配置（免费）：

| 指标 | 阈值 | 说明 |
|---|---|---|
| 磁盘使用率 | **> 80%** | ★ 最重要。70GB 机器上，日志和备份最容易悄悄吃满 |
| 内存使用率 | > 85% | |
| CPU 使用率 | > 80% 持续 5 分钟 | |
| 评测队列积压 | > 100 | 后期加 |

---

## 八、后续

初始化完成后，下一步是放置 `docker-compose.yml`（MySQL 限 1G、Redis 限 256M、
Nginx + Node 应用），规范见 `docs/02-技术架构与数据设计.md` 第 8.2.2 节。

配套文档：

- `../docs/02-技术架构与数据设计.md` — 部署架构与资源配置
- `../docs/04-开发启动前检查清单.md` — A3 域名备案、A2 小程序资质等外部依赖
- `../docs/05-AI开发项目规则.md` — AI 开发约束（红线条款）
