# 拼拼英语打卡 · Pinpin English Check-in

面向培训机构的**多租户**英语自然拼读打卡小程序。6-12 岁小学生跟读 → AI 语音评测 → 教师点评 → 成长可见。

设计文档在 [`docs/`](./docs/)，评测验证脚本在 [`spike/`](./spike/)，部署脚本在 [`deploy/`](./deploy/)。

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Node 22 LTS + **NestJS 11** + TypeScript 5 |
| ORM | **Prisma 6**（schema 单一真源） |
| 数据库 | MySQL 8.0（Docker） |
| 缓存/队列 | Redis 7（M2 接入） |
| 小程序 | 原生微信小程序 + TypeScript（M3） |
| 管理后台 | React 18 + Ant Design 5（M3） |
| 语音评测 | 腾讯云智聆口语评测**新版**（产品 1774，WebSocket） |

---

## 目录结构

```
apps/server/            后端（M1 已启动）
  src/common/tenant/    ★ 多租户底座：上下文、Prisma 自动注入扩展、中间件
  src/common/prisma/    Prisma 模块（唯一出口，禁止 new PrismaClient）
  src/modules/          业务模块（auth / student / health）
  prisma/schema.prisma  数据模型（单一真源）
  test/                 e2e：跨租户越权测试（CI 必跑）
docker/dev-compose.yml  本地 MySQL 8 + Redis 7
docs/                   设计文档 01~06
spike/                  评测精度验证脚本
deploy/                 服务器初始化脚本
```

---

## 本地环境准备（一次性）

### 1. Node 22

已就绪：`C:\Users\Horiz\.workbuddy\binaries\node\versions\22.22.2-3\node.exe`

### 2. Docker Desktop（本地 MySQL / Redis）

⚠️ **需要你手动装**，因为要管理员权限 + 开启 WSL2 + 重启：

1. 下载 <https://www.docker.com/products/docker-desktop/>
2. 安装时勾选 **Use WSL 2 instead of Hyper-V**
3. 装完**重启电脑**，启动 Docker Desktop，等托盘图标变绿
4. 验证：`docker --version`

### 3. Git（代码要推 GitHub）

```powershell
winget install -e --id Git.Git
```

装完**重开终端**，验证 `git --version`。

### 4. 起数据库

```bash
docker compose -f docker/dev-compose.yml up -d
docker ps        # 应看到 pinpin-mysql 与 pinpin-redis
```

---

## 启动后端

```bash
# 1. 装依赖
npm install

# 2. 配置环境变量
cp apps/server/.env.example apps/server/.env

# 3. 建表 + 生成 Prisma Client
npm run prisma:migrate --workspace=apps/server

# 4. 开发模式启动
npm run dev
```

验证：`curl http://localhost:3000/health` → `{"status":"ok","db":"up"}`

---

## 多租户怎么用（写业务代码前必读）

**你不需要、也不应该手写 `tenantId`。** 底座自动注入：

```ts
// ✅ 正确：看不到 tenantId，扩展自动补上
await prisma.student.findMany();
await prisma.student.findFirst({ where: { id } });
await prisma.student.create({ data: { nickname: '小明' } });

// ❌ 错误：会抛异常（唯一键查询无法注入租户）
await prisma.student.findUnique({ where: { id } });

// ❌ 错误：绕过隔离
new PrismaClient();
```

三条红线已写进 `docs/05-AI开发项目规则.md`（R11~R14）：
禁止 `new PrismaClient()`、禁用 `findUnique`、禁止手写 `tenantId` 条件、raw SQL 须自带租户过滤。

**新增业务表只需两步**：schema 里加 `tenantId` 字段和索引 → 正常写业务代码。

---

## 当前进度

| 里程碑 | 状态 |
|---|---|
| M0 评测精度 Spike | 🔄 链路已通，待录 36 条真人音频 |
| **M1 后端骨架 + 多租户底座** | 🔄 进行中 |
| M2 评测闭环 | ⬜ |
| M3 内容与任务 | ⬜ |
| M4 教师端 | ⬜ |
| M5 统计与日历 | ⬜ |
