/**
 * 开发/演示环境种子脚本（幂等，可重复执行）
 *
 * 用途：新同学 clone 项目、`docker compose up` + `prisma migrate` 之后，
 *       一键灌入一套可登录的演示数据，免去手工建机构/账号。
 *
 * 运行：
 *   cd apps/server
 *   npm run db:seed
 *
 * 数据：
 *   - 一个演示机构 (code = DEMO)
 *   - 一个平台管理员账号 (username = admin，角色 = 平台管理员 4)
 *
 * 说明：
 *   - 所有写入均用 upsert，重复执行不会报错、也不会重复插入。
 *   - 跨租户 e2e 用的 E2E_% 数据由测试自身在 beforeAll 内管理，
 *     本脚本不掺入，避免污染开发/演示库。
 */

import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  if (!process.env.DATABASE_URL) {
    throw new Error('缺少 DATABASE_URL，请先在 apps/server/.env 配置数据库连接。');
  }

  // 默认密码可经环境变量覆盖；首次登录后建议在后台修改
  const adminPassword = process.env.SEED_ADMIN_PASSWORD ?? 'admin123456';
  const passwordHash = await bcrypt.hash(adminPassword, 10);

  const tenant = await prisma.tenant.upsert({
    where: { code: 'DEMO' },
    update: { name: '演示机构', status: 1, quotaStudent: 200 },
    create: {
      name: '演示机构',
      code: 'DEMO',
      status: 1,
      quotaStudent: 200,
    },
  });

  const user = await prisma.user.upsert({
    where: { username: 'admin' },
    update: { password: passwordHash, nickname: '平台管理员', status: 1 },
    create: {
      username: 'admin',
      password: passwordHash,
      nickname: '平台管理员',
      status: 1,
    },
  });

  const membership = await prisma.userTenant.upsert({
    where: { userId_tenantId: { userId: user.id, tenantId: tenant.id } },
    update: { role: 4, status: 1 },
    create: {
      userId: user.id,
      tenantId: tenant.id,
      role: 4,
      status: 1,
    },
  });

  console.log('✅ 种子数据就绪：');
  console.log(`   机构  : code=${tenant.code}  name=${tenant.name}  id=${tenant.id.toString()}`);
  console.log(`   账号  : username=admin  角色=平台管理员(4)  用户id=${user.id.toString()}`);
  console.log(`   归属  : user_tenant id=${membership.id.toString()}`);
  console.log('   登录  : 用户名 admin；初始口令见本脚本顶部注释，建议登录后立即修改。');
}

main()
  .catch((e) => {
    console.error('❌ 种子执行失败：', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
