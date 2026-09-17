import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import bcrypt from 'bcryptjs';
import { AppModule } from '../src/app.module';
import { PRISMA, PrismaWithTenant } from '../src/common/prisma/prisma.module';

/**
 * ★★★ 跨租户越权自动化测试（docs/02 文档 1.4.2 明确要求进 CI）★★★
 *
 * 验证目标：用 A 租户的资源 id，以 B 租户身份访问，必须全部 404 / 看不到。
 * 这是 SaaS 最致命的事故（风险清单 R8，定级「极高」），必须每次提交都跑。
 *
 * 运行：
 *   1. docker compose -f docker/dev-compose.yml up -d
 *   2. npm run prisma:migrate --workspace=apps/server
 *   3. npm run test:e2e
 */
describe('跨租户数据隔离（越权防护）', () => {
  let app: INestApplication;
  let prisma: PrismaWithTenant;
  let tokenA: string;
  let tokenB: string;
  let studentIdOfA: bigint;
  let tenantAId: bigint;
  let tenantBId: bigint;

  const pwd = 'e2e-password-123';

  beforeAll(async () => {
    if (!process.env.DATABASE_URL) {
      throw new Error(
        '缺少 DATABASE_URL。请先 docker compose -f docker/dev-compose.yml up -d，' +
          '并在 apps/server/.env 里配好 DATABASE_URL。',
      );
    }

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
    await app.init();

    prisma = moduleFixture.get<PrismaWithTenant>(PRISMA);

    // ── 准备数据：两个租户 + 两个用户（用 raw SQL，此时还没有租户上下文）
    await prisma.$executeRaw`DELETE FROM guardian_consent WHERE tenant_id IN (SELECT id FROM tenant WHERE code LIKE 'E2E_%')`;
    await prisma.$executeRaw`DELETE FROM student WHERE tenant_id IN (SELECT id FROM tenant WHERE code LIKE 'E2E_%')`;
    await prisma.$executeRaw`DELETE FROM user_tenant WHERE tenant_id IN (SELECT id FROM tenant WHERE code LIKE 'E2E_%')`;
    await prisma.$executeRaw`DELETE FROM tenant WHERE code LIKE 'E2E_%'`;
    await prisma.$executeRaw`DELETE FROM user WHERE username LIKE 'e2e_%'`;

    const hash = await bcrypt.hash(pwd, 10);
    await prisma.$executeRaw`
      INSERT INTO tenant (name, code, status, quota_student) VALUES
        ('E2E 机构A', 'E2E_A', 1, 100), ('E2E 机构B', 'E2E_B', 1, 100)
    `;
    await prisma.$executeRaw`
      INSERT INTO user (username, password, nickname, status) VALUES
        ('e2e_user_a', ${hash}, '用户A', 1), ('e2e_user_b', ${hash}, '用户B', 1)
    `;

    const tenants = await prisma.$queryRaw<Array<{ id: bigint; code: string }>>`
      SELECT id, code FROM tenant WHERE code LIKE 'E2E_%'
    `;
    tenantAId = tenants.find((t) => t.code === 'E2E_A')!.id;
    tenantBId = tenants.find((t) => t.code === 'E2E_B')!.id;

    const users = await prisma.$queryRaw<Array<{ id: bigint; username: string }>>`
      SELECT id, username FROM user WHERE username LIKE 'e2e_%'
    `;
    const userAId = users.find((u) => u.username === 'e2e_user_a')!.id;
    const userBId = users.find((u) => u.username === 'e2e_user_b')!.id;

    await prisma.$executeRaw`
      INSERT INTO user_tenant (user_id, tenant_id, role, status) VALUES
        (${userAId}, ${tenantAId}, 3, 1), (${userBId}, ${tenantBId}, 3, 1)
    `;

    // ── 登录拿 token
    tokenA = await login('e2e_user_a', tenantAId);
    tokenB = await login('e2e_user_b', tenantBId);

    async function login(username: string, _tenantId: bigint) {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({ username, password: pwd })
        .expect(201);
      return res.body.token as string;
    }
  }, 60000);

  afterAll(async () => {
    if (prisma) {
      await prisma.$executeRaw`DELETE FROM student WHERE tenant_id IN (SELECT id FROM tenant WHERE code LIKE 'E2E_%')`;
      await prisma.$executeRaw`DELETE FROM user_tenant WHERE tenant_id IN (SELECT id FROM tenant WHERE code LIKE 'E2E_%')`;
      await prisma.$executeRaw`DELETE FROM tenant WHERE code LIKE 'E2E_%'`;
      await prisma.$executeRaw`DELETE FROM user WHERE username LIKE 'e2e_%'`;
    }
    if (app) {
      await app.close();
    }
  });

  it('A 租户可以创建并查到自己的学员', async () => {
    const created = await request(app.getHttpServer())
      .post('/api/v1/students')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({ nickname: 'A机构小明', avatarPreset: 'cat_01' })
      .expect(201);

    studentIdOfA = BigInt(created.body.id);
    expect(studentIdOfA).toBeGreaterThan(0n);

    const detail = await request(app.getHttpServer())
      .get(`/api/v1/students/${studentIdOfA}`)
      .set('Authorization', `Bearer ${tokenA}`)
      .expect(200);
    expect(detail.body.nickname).toBe('A机构小明');
  });

  it('★ B 租户拿 A 的学员 id 查详情，必须 404（不能泄露数据）', async () => {
    const res = await request(app.getHttpServer())
      .get(`/api/v1/students/${studentIdOfA}`)
      .set('Authorization', `Bearer ${tokenB}`)
      .expect(404);
    expect(res.body.message).toContain('学员不存在');
  });

  it('★ B 租户的列表里看不到 A 租户的学员', async () => {
    const list = await request(app.getHttpServer())
      .get('/api/v1/students')
      .set('Authorization', `Bearer ${tokenB}`)
      .expect(200);

    const ids = (list.body as Array<{ id: number | string }>).map((s) => String(s.id));
    expect(ids).not.toContain(studentIdOfA.toString());
  });

  it('★ 创建时伪造 tenantId 无效 —— 数据仍落在调用方自己的租户下', async () => {
    // 字段被 ValidationPipe 剥离（whitelist），请求应当正常成功
    await request(app.getHttpServer())
      .post('/api/v1/students')
      .set('Authorization', `Bearer ${tokenB}`)
      // 故意伪造：试图把学员建到 A 租户
      .send({ nickname: '伪造租户的学生', tenantId: tenantAId.toString() })
      .expect(201);

    // 关键断言：即使伪造字段被剥离了，落库也必须是 B 租户（由上下文注入）
    const rows = (await prisma.$queryRaw`
      SELECT tenant_id FROM student WHERE nickname = '伪造租户的学生'
    `) as Array<{ tenant_id: bigint }>;

    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((r) => expect(r.tenant_id).toBe(tenantBId));
  });

  it('★ 未登录访问租户数据必须 401', async () => {
    await request(app.getHttpServer()).get('/api/v1/students').expect(401);
  });

  it('★ findUnique 被禁用（防止绕过租户隔离）', async () => {
    // 扩展客户端上 findUnique 的类型仍然存在，但运行时会抛错 —— 这正是要断言的行为
    await expect(
      prisma.student.findUnique({ where: { id: studentIdOfA } }),
    ).rejects.toThrow(/禁止对 Student 使用 findUnique/);
  });

  it('健康检查可用', async () => {
    const res = await request(app.getHttpServer()).get('/health').expect(200);
    expect(res.body.status).toBe('ok');
  });
});
