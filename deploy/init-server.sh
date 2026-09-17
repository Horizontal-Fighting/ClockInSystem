#!/usr/bin/env bash
# =============================================================================
# 拼拼英语打卡 - 服务器初始化脚本
# 目标系统：Ubuntu 24.04 LTS (x86_64)  干净系统，一次跑完
#
# 用法：
#   交互式执行（推荐）:  sudo bash init-server.sh
#   只体检不修改      :  sudo bash init-server.sh --check
#   非交互（CI/重跑）  :  sudo SSH_PORT=22 SSH_PUBKEY="ssh-ed25519 AAAA..." bash init-server.sh -y
#
# 设计原则：
#   1. 幂等 —— 重复运行不会破坏已有配置，可放心重跑
#   2. 可读 —— 每步打印中文状态，出问题能一眼定位
#   3. 不锁死 —— 改 SSH 前先开防火墙并提示验证，避免把自己关在门外
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------- 可配置项 ---
SSH_PORT="${SSH_PORT:-}"
SSH_PUBKEY="${SSH_PUBKEY:-}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
SWAP_SIZE="${SWAP_SIZE:-4G}"
TZ_NAME="${TZ_NAME:-Asia/Shanghai}"
DOCKER_LOG_MAX_SIZE="${DOCKER_LOG_MAX_SIZE:-10m}"
DOCKER_LOG_MAX_FILE="${DOCKER_LOG_MAX_FILE:-3}"
INSTALL_FAIL2BAN="${INSTALL_FAIL2BAN:-yes}"
# 国内拉取 Docker Hub 慢时，取消下一行注释（腾讯云镜像加速器）
# DOCKER_REGISTRY_MIRROR="https://mirror.ccs.tencentyun.com"
DOCKER_REGISTRY_MIRROR="${DOCKER_REGISTRY_MIRROR:-}"

ASSUME_YES="no"
CHECK_ONLY="no"
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES="yes" ;;
    --check)  CHECK_ONLY="yes" ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $arg （用 --help 查看用法）"; exit 1 ;;
  esac
done

# ------------------------------------------------------------------ 工具函数 ---
C_RESET='\033[0m'; C_GREEN='\033[32m'; C_YELLOW='\033[33m'; C_RED='\033[31m'; C_BLUE='\033[36m'
if [[ "${TERM:-dumb}" == "dumb" || -n "${NO_COLOR:-}" ]]; then
  C_RESET=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_BLUE=''
fi

step()  { printf "\n${C_BLUE}▶ %s${C_RESET}\n" "$1"; }
ok()    { printf "  ${C_GREEN}✔${C_RESET} %s\n" "$1"; }
warn()  { printf "  ${C_YELLOW}!${C_RESET} %s\n" "$1"; }
fail()  { printf "  ${C_RED}✘${C_RESET} %s\n" "$1"; }
die()   { printf "\n${C_RED}中止：%s${C_RESET}\n" "$1"; exit 1; }

ask() { # ask "提示" "默认值" -> 写入全局变量 ASK_RESULT
  local prompt="$1" default="$2" input=""
  if [[ "$ASSUME_YES" == "yes" ]]; then ASK_RESULT="$default"; return 0; fi
  read -r -p "$(printf "  ${C_YELLOW}?${C_RESET} %s [%s]: " "$prompt" "$default")" input || true
  ASK_RESULT="${input:-$default}"
}

need_root() {
  [[ "$(id -u)" -eq 0 ]] || die "请用 root 执行（sudo bash $0）"
}

# =============================================================================
# --check 模式：只体检，不修改任何东西
# =============================================================================
if [[ "$CHECK_ONLY" == "yes" ]]; then
  printf "${C_BLUE}════ 服务器体检（只读） ════${C_RESET}\n"
  printf "  系统     : %s\n" "$(. /etc/os-release && echo "$PRETTY_NAME")"
  printf "  内核     : %s\n" "$(uname -r)"
  printf "  架构     : %s\n" "$(uname -m)"
  printf "  时区     : %s\n" "$(timedatectl show -p Timezone --value 2>/dev/null || echo '?')"
  printf "  内存     : %s\n" "$(free -h | awk '/^Mem:/{print $2}')"
  printf "  Swap     : %s\n" "$(free -h | awk '/^Swap:/{print $2}')"
  printf "  磁盘     : %s\n" "$(df -h / | awk 'NR==2{print $2" 总量 / "$4" 可用 / "$5" 已用"}')"
  printf "  Docker   : %s\n" "$(docker --version 2>/dev/null || echo '未安装')"
  printf "  Compose  : %s\n" "$(docker compose version 2>/dev/null || echo '未安装')"
  printf "  防火墙   : %s\n" "$(ufw status 2>/dev/null | head -1 || echo '未启用')"
  printf "  部署用户 : %s\n" "$(id "$DEPLOY_USER" 2>/dev/null && echo '存在' || echo '不存在')"
  printf "  数据目录 : %s\n" "$(ls -d /srv/app /srv/data /srv/backup 2>/dev/null | tr '\n' ' ' || echo '未创建')"
  printf "\n${C_BLUE}提示${C_RESET}：以上是当前状态。要执行初始化请去掉 --check 参数。\n"
  exit 0
fi

need_root

# =============================================================================
# 0. 前置检查与参数收集
# =============================================================================
step "0/9 前置检查"

[[ -r /etc/os-release ]] || die "无法识别操作系统（未找到 /etc/os-release）"
# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  warn "当前系统是 ${PRETTY_NAME:-未知}，本脚本面向 Ubuntu 24.04，继续风险自负"
  ask "仍要继续？输入 yes 继续" "no"
  [[ "$ASK_RESULT" == "yes" ]] || die "已取消。建议重装为 Ubuntu 24.04 LTS x86_64"
elif [[ "${VERSION_ID:-}" != "24.04" ]]; then
  warn "检测到 Ubuntu ${VERSION_ID}，推荐 24.04 LTS（支持到 2029 年）"
  ask "继续？输入 yes 继续" "yes"
  [[ "$ASK_RESULT" == "yes" ]] || exit 0
fi
ok "系统 ${PRETTY_NAME}"

ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" && "$ARCH" != "amd64" ]]; then
  warn "架构为 $ARCH。部分 npm 原生模块在 ARM 上需重新编译，建议换 x86_64 机型"
  ask "继续？输入 yes 继续" "no"
  [[ "$ASK_RESULT" == "yes" ]] || exit 0
else
  ok "架构 x86_64"
fi

# SSH 端口
if [[ -z "$SSH_PORT" ]]; then
  ask "SSH 端口（改高位端口可减少扫描噪音，也可保持 22 由安全组控制）" "22"
  SSH_PORT="$ASK_RESULT"
fi
[[ "$SSH_PORT" =~ ^[0-9]+$ ]] && [[ "$SSH_PORT" -ge 1 && "$SSH_PORT" -le 65535 ]] || die "SSH 端口非法: $SSH_PORT"

# deploy 用户的 SSH 公钥：优先复用 root 已有的，其次环境变量，最后交互粘贴
if [[ -z "$SSH_PUBKEY" ]]; then
  if [[ -s /root/.ssh/authorized_keys ]]; then
    SSH_PUBKEY="$(grep -E '^(ssh-|ecdsa-|sk-)' /root/.ssh/authorized_keys | head -1 || true)"
    [[ -n "$SSH_PUBKEY" ]] && ok "复用 root 已有 SSH 公钥：$(echo "$SSH_PUBKEY" | cut -d' ' -f1) ..."
  fi
fi
if [[ -z "$SSH_PUBKEY" ]]; then
  printf "  ${C_YELLOW}?${C_RESET} 请粘贴本机 SSH 公钥（ssh-ed25519/ssh-rsa 开头，用于登录 ${DEPLOY_USER}）：\n"
  printf "    > "
  read -r SSH_PUBKEY || true
fi
if [[ -z "$SSH_PUBKEY" ]]; then
  warn "未提供公钥。"
  ask "确定跳过？跳过后将无法通过密钥登录 deploy 用户" "no"
  [[ "$ASK_RESULT" == "yes" ]] || die "请先准备 SSH 公钥（本机执行: cat ~/.ssh/id_ed25519.pub）"
fi
[[ "$SSH_PUBKEY" =~ ^(ssh-|ecdsa-|sk-) ]] || die "公钥格式不对，应以 ssh-ed25519 / ssh-rsa / ecdsa- 开头"

cat <<EOF
  ────────────────────────────────────────
  即将执行：
    系统   Ubuntu 24.04 更新到最新
    用户   创建 ${DEPLOY_USER}（sudo + docker 组）
    SSH    端口 ${SSH_PORT} / 禁 root / 禁密码 / 仅密钥
    防火墙 仅放行 ${SSH_PORT} 80 443
    容器   Docker CE + Compose 插件（日志限 ${DOCKER_LOG_MAX_SIZE}×${DOCKER_LOG_MAX_FILE}）
    内存   swap ${SWAP_SIZE} + swappiness 10
    目录   /srv/{app,data,backup}
    时区   ${TZ_NAME}
  ────────────────────────────────────────
EOF
ask "确认开始？输入 yes" "yes"
[[ "$ASK_RESULT" == "yes" ]] || die "已取消"
ok "参数确认完毕"

# =============================================================================
# 1. 系统更新与基础软件
# =============================================================================
step "1/9 系统更新与基础软件"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get -y -qq upgrade
ok "系统已更新到最新"
# 注意：若内核被更新，脚本末尾会提示重启
apt-get install -y -qq curl ca-certificates gnupg git jq unzip htop ufw
if [[ "$INSTALL_FAIL2BAN" == "yes" ]]; then
  apt-get install -y -qq fail2ban || warn "fail2ban 安装失败，跳过（不影响主流程）"
fi
ok "基础软件已安装（curl/gnupg/git/jq/ufw 等）"

timedatectl set-timezone "$TZ_NAME" && ok "时区已设为 $TZ_NAME"

# =============================================================================
# 2. 创建部署用户
# =============================================================================
step "2/9 创建部署用户 ${DEPLOY_USER}"
if id -u "$DEPLOY_USER" >/dev/null 2>&1; then
  ok "用户已存在，跳过创建"
else
  adduser --disabled-password --gecos "" "$DEPLOY_USER" >/dev/null
  ok "已创建（无密码，仅密钥登录）"
fi
usermod -aG sudo "$DEPLOY_USER"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$DEPLOY_USER" > "/etc/sudoers.d/${DEPLOY_USER}"
chmod 0440 "/etc/sudoers.d/${DEPLOY_USER}"
visudo -c >/dev/null 2>&1 && ok "已加入 sudo（NOPASSWD，便于 CI/脚本部署）"

if [[ -n "$SSH_PUBKEY" ]]; then
  install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
  touch "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  grep -qxF "$SSH_PUBKEY" "/home/${DEPLOY_USER}/.ssh/authorized_keys" || echo "$SSH_PUBKEY" >> "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chmod 0600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chown -R "$DEPLOY_USER:$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
  ok "SSH 公钥已写入"
fi

# =============================================================================
# 3. 防火墙（必须在 SSH 重启之前放行新端口，顺序不能反）
# =============================================================================
step "3/9 防火墙 ufw"
ufw --force reset >/dev/null
ufw default deny incoming  >/dev/null
ufw default allow outgoing >/dev/null
ufw allow "${SSH_PORT}/tcp" comment 'SSH' >/dev/null
ufw allow 80/tcp  comment 'HTTP'  >/dev/null
ufw allow 443/tcp comment 'HTTPS' >/dev/null
ufw --force enable >/dev/null
ufw reload >/dev/null
ok "已放行 ${SSH_PORT} / 80 / 443，其余全部拒绝"
warn "还需在腾讯云安全组做同样配置（控制台 → 安全组），两层防护才算完整"

# =============================================================================
# 4. SSH 加固
# =============================================================================
step "4/9 SSH 加固"
CONF_DIR=/etc/ssh/sshd_config.d
install -d -m 0755 "$CONF_DIR"
grep -q "sshd_config.d" /etc/ssh/sshd_config 2>/dev/null || \
  echo "Include /etc/ssh/sshd_config.d/*.conf" >> /etc/ssh/sshd_config

cat > "${CONF_DIR}/99-hardening.conf" <<EOF
# 由 init-server.sh 生成，可安全重跑覆盖
Port ${SSH_PORT}
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
UsePAM yes
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers ${DEPLOY_USER}
EOF
ok "已写入 ${CONF_DIR}/99-hardening.conf"

# Ubuntu 22.10+ 用 ssh.socket 做 socket activation，
# 只改 sshd_config 的 Port 不生效 —— 必须同步改 socket 的监听端口。
if systemctl list-unit-files 2>/dev/null | grep -q '^ssh.socket'; then
  install -d -m 0755 /etc/systemd/system/ssh.socket.d
  cat > /etc/systemd/system/ssh.socket.d/override.conf <<EOF
[Socket]
ListenStream=
ListenStream=${SSH_PORT}
EOF
  systemctl daemon-reload
  ok "已同步 ssh.socket 监听端口（Ubuntu socket activation 必需）"
fi

sshd -t && ok "sshd 配置语法校验通过" || die "sshd 配置有误，已回滚前请检查上方输出"

# =============================================================================
# 5. Docker CE + Compose
# =============================================================================
step "5/9 安装 Docker CE + Compose 插件"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "已安装：$(docker --version)"
else
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-noble}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
                         docker-buildx-plugin docker-compose-plugin
  ok "Docker 安装完成：$(docker --version)"
fi
usermod -aG docker "$DEPLOY_USER"
ok "${DEPLOY_USER} 已加入 docker 组（重新登录后生效）"

# daemon.json：日志轮转是重点 —— 默认无上限，几个月能吃满 70GB
install -d -m 0755 /etc/docker
if [[ -n "$DOCKER_REGISTRY_MIRROR" ]]; then
  cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "${DOCKER_LOG_MAX_SIZE}", "max-file": "${DOCKER_LOG_MAX_FILE}" },
  "live-restore": true,
  "registry-mirrors": ["${DOCKER_REGISTRY_MIRROR}"]
}
EOF
else
  cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "${DOCKER_LOG_MAX_SIZE}", "max-file": "${DOCKER_LOG_MAX_FILE}" },
  "live-restore": true
}
EOF
fi
systemctl enable --now docker >/dev/null 2>&1 || true
systemctl restart docker >/dev/null 2>&1 || true
ok "Docker 日志已限制为 ${DOCKER_LOG_MAX_SIZE} × ${DOCKER_LOG_MAX_FILE}（防磁盘被日志吃满）"

# =============================================================================
# 6. Swap（4G 内存跑 MySQL + Node，没 swap 峰值一到就 OOM）
# =============================================================================
step "6/9 配置 swap ${SWAP_SIZE}"
if swapon --show 2>/dev/null | grep -q '/swapfile'; then
  ok "swap 已存在，跳过"
else
  if ! fallocate -l "$SWAP_SIZE" /swapfile 2>/dev/null; then
    warn "fallocate 失败，改用 dd（较慢，请稍候）"
    dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none
  fi
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "swap 已启用并写入 fstab（重启后自动挂载）"
fi
cat > /etc/sysctl.d/99-app.conf <<'EOF'
# 尽量用内存，真吃紧时才动 swap
vm.swappiness = 10
vm.vfs_cache_pressure = 50
# 防止单容器把宿主机拖死时无法登录排障
vm.panic_on_oom = 0
EOF
sysctl --system >/dev/null 2>&1 || sysctl -p /etc/sysctl.d/99-app.conf >/dev/null
ok "swappiness=10（优先用内存，保底不崩）"

# =============================================================================
# 7. 目录约定
# =============================================================================
step "7/9 创建目录"
install -d -m 0755 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /srv/app /srv/backup
install -d -m 0755 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /srv/data/mysql /srv/data/redis /srv/data/nginx
ok "/srv/app（应用）、/srv/data（数据库卷）、/srv/backup（临时备份，最终传 COS）"
warn "备份产物务必传到 COS，不要长期留在本地盘（70GB 会被撑满）"

# =============================================================================
# 8. fail2ban（可选）
# =============================================================================
step "8/9 fail2ban"
if [[ "$INSTALL_FAIL2BAN" == "yes" ]] && command -v fail2ban-server >/dev/null 2>&1; then
  cat > /etc/fail2ban/jail.local <<EOF
[sshd]
enabled  = true
port     = ${SSH_PORT}
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 5
findtime = 600
bantime  = 3600
EOF
  systemctl enable --now fail2ban >/dev/null 2>&1 || true
  ok "已启用（5 次失败封 1 小时）"
else
  warn "跳过（未安装或已关闭）"
fi

# =============================================================================
# 9. 验收自检
# =============================================================================
step "9/9 验收自检"
printf "\n${C_BLUE}══════════ 初始化报告 ══════════${C_RESET}\n"
printf "  %-12s %s\n" "系统"     "$(. /etc/os-release && echo "$PRETTY_NAME")"
printf "  %-12s %s\n" "架构"     "$(uname -m)"
printf "  %-12s %s\n" "时区"     "$(timedatectl show -p Timezone --value)"
printf "  %-12s %s\n" "内存"     "$(free -h | awk '/^Mem:/{print $2}')"
printf "  %-12s %s\n" "Swap"     "$(free -h | awk '/^Swap:/{print $2}')"
printf "  %-12s %s\n" "磁盘"     "$(df -h / | awk 'NR==2{print $4" 可用 / "$5" 已用"}')"
printf "  %-12s %s\n" "SSH 端口" "${SSH_PORT}（禁 root / 禁密码 / 仅密钥）"
printf "  %-12s %s\n" "防火墙"   "$(ufw status | grep -m1 'Status' | awk '{print $2}')"
printf "  %-12s %s\n" "Docker"   "$(docker --version 2>/dev/null | cut -d, -f1)"
printf "  %-12s %s\n" "Compose"  "$(docker compose version 2>/dev/null | awk '{print $1" "$4}')"
printf "  %-12s %s\n" "部署用户" "${DEPLOY_USER}（sudo + docker）"
printf "  %-12s %s\n" "目录"     "/srv/app /srv/data /srv/backup"
printf "${C_BLUE}════════════════════════════════${C_RESET}\n\n"

cat <<EOF
${C_YELLOW}★ 下一步（重要，请照做）${C_RESET}

1) ${C_RED}不要关闭当前终端${C_RESET}。另开一个窗口，用新端口验证能登录：
     ssh -p ${SSH_PORT} ${DEPLOY_USER}@<服务器IP>
   确认登录成功后，再断开原连接。否则万一密钥没配上，你会把自己锁在外面。

2) 到腾讯云控制台配置安全组，只放行 ${SSH_PORT} / 80 / 443（与 ufw 保持一致）。

3) 内核若被更新过，重启一次让新内核生效：
     sudo reboot

4) 用 deploy 用户重新登录后，验证 docker 组生效：
     docker ps          # 不应报 permission denied
     docker compose version

5) 后续在 /srv/app 下放置 docker-compose.yml 启动服务。
   MySQL 建议容器内存限制 1g、Redis 256m（2C4G 机器上的分配基线）。

${C_YELLOW}★ 强烈提醒：不要装宝塔面板${C_RESET}
   它自身占用 300-500MB 内存（4G 机器上占比很高），并开放额外端口增加攻击面。
   有 docker-compose.yml + 云监控已足够。
EOF
