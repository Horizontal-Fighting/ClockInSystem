import { Inject, Injectable, UnauthorizedException, BadRequestException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import bcrypt from 'bcryptjs';
import { PRISMA, PrismaWithTenant } from '../../common/prisma/prisma.module';

export interface LoginResult {
  token?: string;
  /** 该用户属于多个机构时，需要前端先选机构再重新登录 */
  needChooseTenant?: boolean;
  tenants?: Array<{ id: string; name: string; role: number }>;
}

/**
 * 账号体系。
 *
 * ★ 两个设计点（来自 PRD F1-7 与 02 文档 1.4.3）
 * 1. **不限制登录设备数**：不做设备指纹、token 不互斥，同一账号可多端在线。
 *    场景是孩子用家长旧手机/平板打卡，限制设备会直接打不通。
 * 2. **一个 user 可属于多个 tenant**：家长报了两家机构，登录后要能切换。
 *    所以登录分两种情况处理（见 login 方法注释）。
 */
@Injectable()
export class AuthService {
  constructor(
    @Inject(PRISMA) private readonly prisma: PrismaWithTenant,
    private readonly jwt: JwtService,
  ) {}

  /**
   * 账号密码登录。
   *
   * - 传入 tenantId：校验归属后直接签 token
   * - 未传且只属于一个机构：直接签 token
   * - 未传且属于多个机构：返回机构列表，前端让用户选（needChooseTenant = true）
   *
   * 注意：user 表没有 tenantId（它是全局身份），所以这里刻意**不走**租户隔离扩展，
   * 关联机构通过 user_tenant 显式查询 —— 这是唯一应该绕过自动注入的地方。
   */
  async login(username: string, password: string, tenantId?: bigint): Promise<LoginResult> {
    const user = await this.prisma.user.findFirst({ where: { username } });
    if (!user || !user.password) {
      throw new UnauthorizedException('用户名或密码错误');
    }
    if (user.status !== 1) {
      throw new UnauthorizedException('账号已被禁用');
    }
    if (!(await bcrypt.compare(password, user.password))) {
      throw new UnauthorizedException('用户名或密码错误');
    }

    // user_tenant 有 tenantId 字段，但此时还没有租户上下文（正在登录），
    // 所以用 $unextended 或原生 client 查询。这里用 raw 查询避免触发 requireTenantId。
    // 注意：扩展客户端上 $queryRaw 的泛型推断会退化，这里显式断言
    const rows = (await this.prisma.$queryRaw`
      SELECT t.id AS id, t.name AS name, ut.role AS role
      FROM user_tenant ut
      JOIN tenant t ON t.id = ut.tenantId
      WHERE ut.userId = ${user.id} AND ut.status = 1 AND t.status = 1
    `) as Array<{ id: bigint; name: string; role: number }>;

    if (rows.length === 0) {
      throw new UnauthorizedException('该账号未加入任何机构');
    }

    let target = tenantId ? rows.find((r) => r.id === tenantId) : undefined;

    if (!target) {
      if (tenantId) {
        throw new UnauthorizedException('该账号不属于指定机构');
      }
      if (rows.length > 1) {
        return {
          needChooseTenant: true,
          tenants: rows.map((r) => ({
            id: r.id.toString(),
            name: r.name,
            role: r.role,
          })),
        };
      }
      target = rows[0];
    }

    return { token: this.signToken(user.id, target.id, target.role) };
  }

  /**
   * 微信登录（M3 接入）。接口先留着，避免后期到处改调用点。
   * 注意：只取 openid，不调用 getPhoneNumber —— 合规硬约束（PRD F1-1）。
   */
  async wechatLogin(_code: string): Promise<LoginResult> {
    throw new BadRequestException('微信登录尚未开通，请先使用账号密码登录');
  }

  private signToken(userId: bigint, tenantId: bigint, role: number): string {
    return this.jwt.sign({
      sub: userId.toString(),
      tid: tenantId.toString(),
      role,
    });
  }
}
