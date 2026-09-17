import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { PRISMA, PrismaWithTenant } from '../../common/prisma/prisma.module';

/**
 * 学员服务。
 *
 * ★ 这个文件是「多租户怎么用」的示范：
 *   注意所有查询里**都没有出现 tenantId** —— 它由 Prisma 扩展在底层自动注入。
 *   业务代码里不写 tenantId 才是正确的写法；写了反而说明架构被绕过了。
 */
@Injectable()
export class StudentService {
  constructor(@Inject(PRISMA) private readonly prisma: PrismaWithTenant) {}

  /** 查询列表。自动带上当前租户，无需手写 where.tenantId */
  async list() {
    return this.prisma.student.findMany({
      orderBy: { id: 'desc' },
      select: {
        id: true,
        nickname: true,
        avatarPreset: true,
        status: true,
        levelId: true,
        createdAt: true,
      },
    });
  }

  /** 按 id 查详情。跨租户访问时 findFirst 返回 null → 404（而不是泄露数据） */
  async detail(id: bigint) {
    const student = await this.prisma.student.findFirst({
      where: { id }, // tenantId 由扩展自动补上
    });
    if (!student) {
      throw new NotFoundException('学员不存在');
    }
    return student;
  }

  /**
   * 创建学员。
   *
   * ★ 为什么这里传了 tenantId: 0n 这个"假值"
   * Prisma 的类型系统要求必填关系字段必须在 data 里出现，否则编译不过；
   * 但真实租户只能由请求上下文决定。所以这里给一个占位值，
   * 扩展（injectIntoData）会**用上下文的 tenantId 覆盖它** —— 包括前端伪造 tenantId 的情况。
   * 不要因为看到这行就以为可以在业务层决定租户归属。
   */
  async create(input: { nickname: string; avatarPreset?: string; levelId?: bigint }) {
    return this.prisma.student.create({
      data: {
        tenantId: 0n, // 占位，会被扩展覆盖为当前租户
        nickname: input.nickname,
        avatarPreset: input.avatarPreset,
        levelId: input.levelId,
      },
    });
  }
}
